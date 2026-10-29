#!/usr/bin/env python3
"""Standalone read-only verifier. Imports no MuseBreak backend/producer code.

Needs a separately trusted Ed25519 public key AND an independently obtained
SQLite snapshot/live read. The receipt's embedded key identifier is not trusted.
"""
import argparse
import base64
import hashlib
import json
import sqlite3
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def sha(v):return hashlib.sha256(canonical(v)).hexdigest()

def integer(v,minimum=0,maximum=2**53-1):
    if type(v) is not int or not minimum<=v<=maximum:raise ValueError('Invalid integer value')
    return v

def signed(envelope,key,domain):
    if envelope['domain']!=domain or envelope['algorithm']!='Ed25519':raise ValueError('Signature context mismatch')
    raw=key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    if envelope['key_id']!=hashlib.sha256(raw).hexdigest():raise ValueError('Untrusted signing key identifier')
    key.verify(base64.b64decode(envelope['signature'],validate=True),domain.encode()+b'\0'+canonical(envelope['body']))
    return envelope['body']

def verify(receipt,public_key_path,db_path):
    key=serialization.load_pem_public_key(Path(public_key_path).read_bytes())
    if not isinstance(key,Ed25519PublicKey):raise ValueError('Pinned Ed25519 public key required')
    b=signed(receipt,key,'musebreak.invoice-receipt.v1');invoice=b['invoice'];a=signed(b['approval'],key,'musebreak.approval.v1');r=b['result']
    if b['schema']!='musebreak.invoice-receipt.v1' or invoice['schema']!='musebreak.invoice.v1' or invoice['operation']!='issue_invoice':raise ValueError('Unsupported receipt or operation')
    if invoice['currency']!='INR' or sha(invoice)!=b['payload_hash']:raise ValueError('Invoice hash/currency mismatch')
    owner=invoice['owner'];iid=invoice['invoice_id']
    if not owner or not isinstance(owner,str) or a['owner']!=owner or a['actor']!=owner or a['invoice_id']!=iid or a['payload_hash']!=b['payload_hash'] or a['scope']!='issue_invoice:once':raise ValueError('Decision not bound to this invoice and owner')
    if not isinstance(a['nonce'],str) or not a['nonce']:raise ValueError('Missing approval nonce')
    start=integer(a['approved_at']);end=integer(a['expires_at']);issued=integer(r['issued_at'])
    if not start<=issued<end or end-start!=300 or r['status']!='issued':raise ValueError('Invalid approval window/result')
    items=invoice['items']
    if not isinstance(items,list) or not 1<=len(items)<=20 or len({i['product_id'] for i in items})!=len(items):raise ValueError('Invalid or duplicated invoice lines')
    subtotal=tax=0
    for line in items:
        qty=integer(line['quantity'],1,10**6);price=integer(line['unit_price_minor'],0,10**9);rate=integer(line['tax_bps'],0,10000)
        net=qty*price;line_tax=(net*rate+5000)//10000
        if line['net_minor']!=net or line['tax_minor']!=line_tax:raise ValueError('Line arithmetic mismatch')
        subtotal+=net;tax+=line_tax
    if integer(invoice['subtotal_minor'])!=subtotal or integer(invoice['tax_minor'])!=tax or integer(invoice['total_minor'])!=subtotal+tax:raise ValueError('Invoice total mismatch')
    uri=Path(db_path).resolve().as_uri()+'?mode=ro'
    db=sqlite3.connect(uri,uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        row=db.execute('SELECT * FROM biz_invoices WHERE id=? AND owner=?',(iid,owner)).fetchone()
        if row is None or row['status']!='issued' or row['issued_at']!=issued or row['payload_hash']!=b['payload_hash'] or json.loads(row['payload_json'])!=invoice or json.loads(row['approval_json'])!=b['approval'] or json.loads(row['receipt_json'])!=receipt:raise ValueError('Authoritative invoice record does not match receipt')
        movements=db.execute('SELECT * FROM biz_movements WHERE invoice_id=?',(iid,)).fetchall()
        if len(movements)!=len(items) or len(r['movements'])!=len(items):raise ValueError('Missing or duplicate stock movements')
        signed_moves={m['product_id']:m for m in r['movements']}
        if len(signed_moves)!=len(items):raise ValueError('Duplicate receipt movements')
        for line in items:
            matching=[m for m in movements if m['product_id']==line['product_id']]
            if len(matching)!=1:raise ValueError('Product movement missing')
            m=matching[0];sm=signed_moves[line['product_id']]
            expected=dict(id=m['id'],product_id=m['product_id'],delta=m['delta'],before_stock=m['before_stock'],after_stock=m['after_stock'])
            if sm!=expected or m['owner']!=owner or m['delta']!=-line['quantity'] or m['after_stock']!=m['before_stock']+m['delta'] or m['after_stock']<0:raise ValueError('Stock movement mismatch')
            product=db.execute('SELECT * FROM biz_products WHERE owner=? AND id=?',(owner,line['product_id'])).fetchone()
            if product is None:raise ValueError('Product is missing')
            balance=integer(product['opening_stock'])
            for change in db.execute('SELECT * FROM biz_movements WHERE owner=? AND product_id=? ORDER BY rowid',(owner,line['product_id'])):
                if change['before_stock']!=balance or change['delta']>=0:raise ValueError('Inventory continuity mismatch')
                balance+=change['delta']
                if balance<0 or change['after_stock']!=balance:raise ValueError('Inventory became negative or diverged')
            if product['stock']!=balance:raise ValueError('Current inventory does not reconcile')
        events=db.execute('SELECT * FROM biz_events WHERE invoice_id=? AND kind=?',(iid,'invoice.issued')).fetchall()
        if len(events)!=1:raise ValueError('Exactly one issuance event required')
        e=events[0];event=json.loads(e['body_json'])
        expected_event=dict(id=r['event_id'],invoice_id=iid,owner=owner,kind='invoice.issued',payload_hash=b['payload_hash'],issued_at=issued,movements=r['movements'])
        if event!=expected_event or e['id']!=r['event_id'] or e['owner']!=owner or e['body_hash']!=sha(event) or r['event_hash']!=sha(event):raise ValueError('Decision/result evidence event mismatch')
    finally:db.close()
    return dict(verified=True,invoice_id=iid,payload_hash=b['payload_hash'],checks=['pinned-key signatures','exact-payload decision','integer totals','approval valid at issuance','issued database record','one movement per line','inventory reconciliation','one matching issuance event'],scope='Selected local invoice and supplied database snapshot. Not payment, delivery, external truth, ZK or whole-history completeness.')

def no_duplicates(pairs):
    value={}
    for k,v in pairs:
        if k in value:raise ValueError('Duplicate JSON key')
        value[k]=v
    return value

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--receipt',required=True);parser.add_argument('--public-key',required=True);parser.add_argument('--database',required=True)
    args=parser.parse_args()
    try:
        raw=Path(args.receipt).read_bytes()
        if len(raw)>1000000:raise ValueError('Receipt is too large')
        result=verify(json.loads(raw,object_pairs_hook=no_duplicates),args.public_key,args.database)
    except Exception as e:
        print(json.dumps(dict(verified=False,reason=f'{type(e).__name__}: {e}')));return 1
    print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
