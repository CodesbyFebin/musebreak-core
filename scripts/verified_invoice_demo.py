#!/usr/bin/env python3
"""Synthetic API demo. No model calls, real payments, physical hardware or existing DB use."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True,help='New directory for public receipt, public key and synthetic SQLite snapshot')
    args=parser.parse_args();out=Path(args.out).absolute();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='musebreak-invoice-') as private_dir:
        private=Path(private_dir)
        os.environ.update(BUSINESS_DB_PATH=str(private/'business.sqlite'),BUSINESS_SIGNING_KEY_PATH=str(private/'signing-private.pem'),BUSINESS_OPERATOR_SUBJECT='synthetic-merchant',BUSINESS_ALLOWED_KEY_IDS='metakey-demo-001',BUSINESS_ALLOW_DEMO_AUTH='true',DEMO_USER='synthetic-merchant',DEMO_PASSWORD=secrets.token_hex(24),JWT_SECRET=secrets.token_hex(32),AUDIT_PATH=str(private/'audit.jsonl'),ZKVM_HEARTBEAT_DISABLE='1',USE_OPEN_SOURCE_ONLY='false')
        # Disallow reusing the operator's live Redis/session configuration in this synthetic demo.
        for name in ['REDIS_URL','METAKEY_ID','METAKEY_SECRET','METAKEY_PUBKEY_PEM','ENROLL_TOKEN','META_MODEL_API_URL','META_MODEL_API_KEY','GUARD_LLM_URL','GUARD_LLM_KEY']:
            os.environ.pop(name,None)
        os.environ['MUSE_MODELS']=json.dumps({'receipt-fixture':'blue'})
        from cryptography.hazmat.primitives import serialization,hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        signing=Ed25519PrivateKey.generate()
        key_path=private/'signing-private.pem';key_path.write_bytes(signing.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));key_path.chmod(0o600)
        (out/'signing-public.pem').write_bytes(signing.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
        sys.path.insert(0,str(ROOT/'backend'))
        from fastapi.testclient import TestClient
        import main as gateway
        import crypto
        client=TestClient(gateway.app)
        def post(path,body,headers=None):
            r=client.post(path,json=body,headers=headers or {})
            if r.status_code!=200:raise RuntimeError(f'{path}: HTTP {r.status_code}')
            return r.json()
        fp='synthetic-demo-device'
        g1=post('/login',dict(username=gateway.DEMO_USER,password=gateway.DEMO_PASSWORD,device_fingerprint=fp))
        headers={'Authorization':'Bearer '+g1['gate1_token'],'X-Device-Fingerprint':fp}
        model=next(iter(gateway.MODELS));kid='metakey-demo-001'
        ch=post('/challenge',dict(key_id=kid,model=model),headers);q=ch['qr_payload'];counter=1
        public_demo_key=serialization.load_pem_private_key((ROOT/'hardware/demo_metakey_private.pem').read_bytes(),None)
        mac=crypto.compute_hmac(gateway.KEYS[kid]['hmac_secret'],crypto.nfc_message(bytes.fromhex(ch['challenge']),crypto.fingerprint_hash(fp),kid,counter))
        signature=public_demo_key.sign(crypto.qr_message(q['cid'],q['nonce'],q['model']),ec.ECDSA(hashes.SHA256())).hex()
        g2=post('/authorize',dict(challenge_id=ch['challenge_id'],key_id=kid,nfc_hmac=mac,qr_signature=signature,counter=counter),headers)
        headers['Authorization']='Bearer '+g2['wonder_token']
        product=post('/business/products',dict(name='Synthetic coffee',price_minor=19999,tax_bps=1800,stock=5),headers)
        draft=post('/business/invoices',dict(customer='Synthetic receipt demo customer',items=[dict(product_id=product['id'],quantity=2)]),headers)
        iid=draft['payload']['invoice_id'];binding=dict(payload_hash=draft['payload_hash'])
        denied=client.post(f'/business/invoices/{iid}/issue',headers=headers,json=binding)
        assert denied.status_code==409
        post(f'/business/invoices/{iid}/approve',binding,headers)
        receipt=post(f'/business/invoices/{iid}/issue',binding,headers)
        assert post(f'/business/invoices/{iid}/issue',binding,headers)==receipt
        receipt_path=out/'receipt.json';receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        with sqlite3.connect(private/'business.sqlite') as src,sqlite3.connect(out/'business-snapshot.sqlite') as target:src.backup(target)
        check=subprocess.run([sys.executable,str(ROOT/'verification/invoice_receipt.py'),'--receipt',str(receipt_path),'--public-key',str(out/'signing-public.pem'),'--database',str(out/'business-snapshot.sqlite')],capture_output=True,text=True,check=True)
        verdict=json.loads(check.stdout)
        (out/'verification.json').write_text(json.dumps(verdict,indent=2)+'\n')
        print(json.dumps(dict(synthetic=True,physical_hardware=False,model_called=False,output_directory=str(out),total_minor=receipt['body']['invoice']['total_minor'],verification=verdict),indent=2))
if __name__=='__main__':main()
