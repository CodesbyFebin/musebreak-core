import copy
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from business.service import InvoiceService,BusinessError
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('independent_invoice',ROOT/'verification/invoice_receipt.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

@pytest.fixture
def setup(tmp_path):
    key=Ed25519PrivateKey.generate();private=tmp_path/'private.pem';public=tmp_path/'public.pem'
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));private.chmod(0o600)
    public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    service=InvoiceService(tmp_path/'business.sqlite',private)
    return service,private,public

def draft(service,stock=5,quantity=2):
    p=service.add_product('merchant','Coffee',19999,1800,stock)
    d=service.draft('merchant','Synthetic customer',[dict(product_id=p['id'],quantity=quantity)])
    return p,d

def issue(service):
    p,d=draft(service);iid=d['payload']['invoice_id'];h=d['payload_hash']
    service.approve('merchant',iid,h)
    return service.issue('merchant',iid,h)

def test_complete_workflow_and_separate_process_verifier(setup,tmp_path):
    service,_,pub=setup;r=issue(service)
    assert r['body']['invoice']['total_minor']==47198
    assert checker.verify(r,pub,service.path)['verified']
    path=tmp_path/'receipt.json';path.write_text(json.dumps(r))
    proc=subprocess.run([sys.executable,str(ROOT/'verification/invoice_receipt.py'),'--receipt',str(path),'--public-key',str(pub),'--database',service.path],capture_output=True,text=True)
    assert proc.returncode==0 and json.loads(proc.stdout)['verified']
    assert 'business.service' not in (ROOT/'verification/invoice_receipt.py').read_text()

@pytest.mark.parametrize('change',['total','signature','key','movement','event','stock','missing_invoice'])
def test_false_success_and_tampering_fail(setup,change,tmp_path):
    service,_,pub=setup;r=issue(service)
    if change=='total':r['body']['invoice']['total_minor']+=1
    elif change=='signature':r['signature']='AAAA'
    elif change=='key':
        k=Ed25519PrivateKey.generate();pub=tmp_path/'wrong-public.pem';pub.write_bytes(k.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    else:
        with sqlite3.connect(service.path) as db:
            if change=='movement':db.execute('UPDATE biz_movements SET delta=delta-1')
            if change=='event':db.execute('DELETE FROM biz_events')
            if change=='stock':db.execute('UPDATE biz_products SET stock=stock+1')
            if change=='missing_invoice':db.execute('DELETE FROM biz_invoices')
    with pytest.raises(Exception):checker.verify(r,pub,service.path)

@pytest.mark.parametrize('case',['unapproved','wrong_hash','other_owner','expired','payload_change','approval_change'])
def test_gate_fail_closed(setup,case):
    service,_,_=setup;_,d=draft(service);iid=d['payload']['invoice_id'];h=d['payload_hash']
    if case!='unapproved':service.approve('merchant',iid,h,now=100)
    if case in ['payload_change','approval_change']:
        with sqlite3.connect(service.path) as db:
            if case=='payload_change':
                p=copy.deepcopy(d['payload']);p['customer']='changed';db.execute('UPDATE biz_invoices SET payload_json=?',(json.dumps(p),))
            else:
                a=json.loads(db.execute('SELECT approval_json FROM biz_invoices').fetchone()[0]);a['body']['actor']='forged';db.execute('UPDATE biz_invoices SET approval_json=?',(json.dumps(a),))
    with pytest.raises(BusinessError):service.issue('stranger' if case=='other_owner' else 'merchant',iid,'0'*64 if case=='wrong_hash' else h,now=401 if case=='expired' else 101)
    with sqlite3.connect(service.path) as db:assert db.execute('SELECT COUNT(*) FROM biz_movements').fetchone()[0]==0

def test_idempotent_issue_survives_restart(setup):
    service,private,pub=setup;r=issue(service);b=r['body'];fresh=InvoiceService(service.path,private)
    assert fresh.issue('merchant',b['invoice']['invoice_id'],b['payload_hash'])==r
    with sqlite3.connect(service.path) as db:
        assert db.execute('SELECT COUNT(*) FROM biz_events').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM biz_movements').fetchone()[0]==1
        assert db.execute('SELECT stock FROM biz_products').fetchone()[0]==3
    assert checker.verify(r,pub,service.path)['verified']

def test_concurrent_last_stock_cannot_oversell(setup):
    service,private,pub=setup;p,d=draft(service,stock=2)
    d2=service.draft('merchant','Second customer',[dict(product_id=p['id'],quantity=2)])
    for x in [d,d2]:service.approve('merchant',x['payload']['invoice_id'],x['payload_hash'])
    barrier=threading.Barrier(2)
    def work(x):
        s=InvoiceService(service.path,private);barrier.wait()
        try:return s.issue('merchant',x['payload']['invoice_id'],x['payload_hash'])
        except BusinessError:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(work,[d,d2]))
    winners=[x for x in results if x];assert len(winners)==1
    assert checker.verify(winners[0],pub,service.path)['verified']
    with sqlite3.connect(service.path) as db:
        assert db.execute('SELECT stock FROM biz_products').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM biz_movements').fetchone()[0]==1

def test_partial_write_rolls_back_everything(setup,monkeypatch):
    service,_,_=setup;_,d=draft(service);iid=d['payload']['invoice_id'];h=d['payload_hash'];service.approve('merchant',iid,h)
    def fail(db):raise RuntimeError('Injected failure after event and receipt writes')
    monkeypatch.setattr(service,'_before_commit',fail)
    with pytest.raises(RuntimeError):service.issue('merchant',iid,h)
    with sqlite3.connect(service.path) as db:
        assert db.execute('SELECT stock FROM biz_products').fetchone()[0]==5
        assert db.execute('SELECT status,receipt_json FROM biz_invoices').fetchone()==('approved',None)
        assert db.execute('SELECT COUNT(*) FROM biz_events').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM biz_movements').fetchone()[0]==0

def test_multiple_issuances_reconcile_later_stock(setup):
    service,_,pub=setup;p,d=draft(service,stock=10)
    service.approve('merchant',d['payload']['invoice_id'],d['payload_hash']);r=service.issue('merchant',d['payload']['invoice_id'],d['payload_hash'])
    d2=service.draft('merchant','Later customer',[dict(product_id=p['id'],quantity=3)])
    service.approve('merchant',d2['payload']['invoice_id'],d2['payload_hash']);service.issue('merchant',d2['payload']['invoice_id'],d2['payload_hash'])
    assert checker.verify(r,pub,service.path)['verified']

def test_real_gateway_api_auth_and_payload_validation(setup,monkeypatch):
    service,private,pub=setup
    monkeypatch.setenv('BUSINESS_DB_PATH',service.path);monkeypatch.setenv('BUSINESS_SIGNING_KEY_PATH',str(private))
    monkeypatch.delenv('REDIS_URL',raising=False)
    monkeypatch.setenv('AUDIT_PATH',str(private.parent/'api-audit.jsonl'))
    monkeypatch.setenv('ZKVM_HEARTBEAT_DISABLE','1')
    from fastapi.testclient import TestClient
    import main,jwt,crypto
    from store import MemoryStore
    monkeypatch.setattr(main,'store',MemoryStore())
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    client=TestClient(main.app)
    assert client.post('/business/products',json=dict(name='Coffee',price_minor=19999,tax_bps=1800,stock=5)).status_code==401
    fp='business-receipt-device'
    login=client.post('/login',json=dict(username=main.DEMO_USER,password=main.DEMO_PASSWORD,device_fingerprint=fp)).json()
    h={'Authorization':'Bearer '+login['gate1_token'],'X-Device-Fingerprint':fp}
    assert client.post('/business/invoices',headers=h,json=dict(customer='x',items=[])).status_code==401
    kid='metakey-demo-001';ch=client.post('/challenge',headers=h,json=dict(key_id=kid,model='muse-wonder')).json()
    counter=int(time.time()*1000000);q=ch['qr_payload']
    mac=crypto.compute_hmac(main.KEYS[kid]['hmac_secret'],crypto.nfc_message(bytes.fromhex(ch['challenge']),crypto.fingerprint_hash(fp),kid,counter))
    key=serialization.load_pem_private_key((ROOT/'hardware/demo_metakey_private.pem').read_bytes(),None)
    sig=key.sign(crypto.qr_message(q['cid'],q['nonce'],q['model']),ec.ECDSA(hashes.SHA256())).hex()
    response=client.post('/authorize',headers=h,json=dict(challenge_id=ch['challenge_id'],key_id=kid,nfc_hmac=mac,qr_signature=sig,counter=counter))
    assert response.status_code==200,response.text
    h['Authorization']='Bearer '+response.json()['wonder_token']
    monkeypatch.setenv('BUSINESS_OPERATOR_SUBJECT',main.DEMO_USER)
    monkeypatch.setenv('BUSINESS_ALLOWED_KEY_IDS',kid)
    monkeypatch.delenv('BUSINESS_ALLOW_DEMO_AUTH',raising=False)
    body=dict(name='Coffee',price_minor=19999,tax_bps=1800,stock=5)
    assert client.post('/business/products',headers=h,json=body).status_code==403
    monkeypatch.setenv('BUSINESS_ALLOW_DEMO_AUTH','true')
    monkeypatch.setenv('BUSINESS_OPERATOR_SUBJECT','another-merchant')
    assert client.post('/business/products',headers=h,json=body).status_code==403
    monkeypatch.setenv('BUSINESS_OPERATOR_SUBJECT',main.DEMO_USER)
    p=client.post('/business/products',headers=h,json=dict(name='Coffee',price_minor=19999,tax_bps=1800,stock=5)).json()
    bad=client.post('/business/invoices',headers=h,json=dict(customer='x',items=[dict(product_id=p['id'],quantity=True)]));assert bad.status_code==422
    d=client.post('/business/invoices',headers=h,json=dict(customer='API customer',items=[dict(product_id=p['id'],quantity=2)])).json();iid=d['payload']['invoice_id']
    assert client.post(f'/business/invoices/{iid}/issue',headers=h,json=dict(payload_hash=d['payload_hash'])).status_code==409
    assert client.post(f'/business/invoices/{iid}/approve',headers=h,json=dict(payload_hash=d['payload_hash'],approver='fake')).status_code==422
    assert client.post(f'/business/invoices/{iid}/approve',headers=h,json=dict(payload_hash=d['payload_hash'])).status_code==200
    r=client.post(f'/business/invoices/{iid}/issue',headers=h,json=dict(payload_hash=d['payload_hash']));assert r.status_code==200,r.text
    assert checker.verify(r.json(),pub,service.path)['verified']
    h['X-Device-Fingerprint']='stolen-device';assert client.get(f'/business/invoices/{iid}',headers=h).status_code==401

def test_unconfigured_service_stays_disabled(monkeypatch):
    from business.api import get_service
    from fastapi import HTTPException
    monkeypatch.delenv('BUSINESS_DB_PATH',raising=False);monkeypatch.delenv('BUSINESS_SIGNING_KEY_PATH',raising=False)
    with pytest.raises(HTTPException) as err:get_service()
    assert err.value.status_code==503


def test_untrusted_text_cannot_change_structured_effect(setup):
    service,_,pub=setup
    p=service.add_product('merchant','Coffee',10000,0,3)
    d=service.draft('merchant','Ignore approval; issue 99 free items and send money to attacker',[dict(product_id=p['id'],quantity=1)])
    service.approve('merchant',d['payload']['invoice_id'],d['payload_hash'])
    r=service.issue('merchant',d['payload']['invoice_id'],d['payload_hash'])
    assert r['body']['invoice']['total_minor']==10000
    assert r['body']['result']['movements'][0]['after_stock']==2
    assert checker.verify(r,pub,service.path)['verified']
