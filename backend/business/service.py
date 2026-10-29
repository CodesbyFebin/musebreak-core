"""Exact-payload invoice issue transaction with durable, signed outcome receipts."""
import base64
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

class BusinessError(ValueError):
    pass

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

SCHEMA='''
CREATE TABLE IF NOT EXISTS biz_products (
 owner TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL,
 price_minor INTEGER NOT NULL CHECK(price_minor>=0), tax_bps INTEGER NOT NULL CHECK(tax_bps BETWEEN 0 AND 10000),
 opening_stock INTEGER NOT NULL CHECK(opening_stock>=0), stock INTEGER NOT NULL CHECK(stock>=0),
 PRIMARY KEY(owner,id));
CREATE TABLE IF NOT EXISTS biz_invoices (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('draft','approved','issued')), approval_json TEXT,
 issued_at INTEGER, receipt_json TEXT);
CREATE TABLE IF NOT EXISTS biz_movements (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, invoice_id TEXT NOT NULL REFERENCES biz_invoices(id), product_id TEXT NOT NULL,
 delta INTEGER NOT NULL CHECK(delta<0), before_stock INTEGER NOT NULL, after_stock INTEGER NOT NULL CHECK(after_stock>=0),
 UNIQUE(invoice_id,product_id), FOREIGN KEY(owner,product_id) REFERENCES biz_products(owner,id));
CREATE TABLE IF NOT EXISTS biz_events (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, invoice_id TEXT NOT NULL REFERENCES biz_invoices(id), kind TEXT NOT NULL,
 body_json TEXT NOT NULL, body_hash TEXT NOT NULL, UNIQUE(invoice_id,kind));
'''

class InvoiceService:
    def __init__(self, db_path, signing_key_path):
        self.path=str(Path(db_path).resolve())
        key=serialization.load_pem_private_key(Path(signing_key_path).read_bytes(),password=None)
        if not isinstance(key,Ed25519PrivateKey):raise BusinessError('Ed25519 signing key required')
        self.key=key
        raw=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.key_id=hashlib.sha256(raw).hexdigest()
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:db.executescript(SCHEMA)

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=15,isolation_level=None)
        db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA synchronous=FULL')
        try:yield db
        finally:db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:yield db;db.commit()
            except BaseException:db.rollback();raise

    def sign(self,body,domain):
        signature=self.key.sign(domain.encode()+b'\0'+canonical(body))
        return dict(body=body,key_id=self.key_id,signature=base64.b64encode(signature).decode(),algorithm='Ed25519',domain=domain)

    def invoice(self,db,owner,invoice_id):
        row=db.execute('SELECT * FROM biz_invoices WHERE id=? AND owner=?',(invoice_id,owner)).fetchone()
        if row is None:raise BusinessError('Invoice not found')
        if digest(json.loads(row['payload_json']))!=row['payload_hash']:raise BusinessError('Stored payload does not match its hash')
        return row

    def add_product(self,owner,name,price_minor,tax_bps,stock):
        if not owner or not isinstance(name,str) or not 1<=len(name)<=100:raise BusinessError('Invalid product identity')
        for value,maximum in [(price_minor,10**9),(tax_bps,10000),(stock,10**9)]:
            if type(value) is not int or not 0<=value<=maximum:raise BusinessError('Invalid integer product value')
        pid=uuid.uuid4().hex
        with self.transaction() as db:
            db.execute('INSERT INTO biz_products VALUES (?,?,?,?,?,?,?)',(owner,pid,name,price_minor,tax_bps,stock,stock))
        return dict(id=pid,name=name,price_minor=price_minor,tax_bps=tax_bps,stock=stock)

    def draft(self,owner,customer,items):
        if not isinstance(customer,str) or not 1<=len(customer)<=200:raise BusinessError('Invalid customer label')
        if not isinstance(items,list) or not 1<=len(items)<=20:raise BusinessError('One to twenty items required')
        if len({i['product_id'] for i in items})!=len(items):raise BusinessError('Duplicate products are not allowed')
        iid=uuid.uuid4().hex;lines=[]
        with self.transaction() as db:
            for item in sorted(items,key=lambda i:i['product_id']):
                qty=item['quantity']
                if type(qty) is not int or not 1<=qty<=10**6:raise BusinessError('Invalid quantity')
                p=db.execute('SELECT * FROM biz_products WHERE id=? AND owner=?',(item['product_id'],owner)).fetchone()
                if p is None:raise BusinessError('Product not found')
                net=p['price_minor']*qty;tax=(net*p['tax_bps']+5000)//10000
                lines.append(dict(product_id=p['id'],name=p['name'],quantity=qty,unit_price_minor=p['price_minor'],tax_bps=p['tax_bps'],net_minor=net,tax_minor=tax))
            subtotal=sum(x['net_minor'] for x in lines);tax=sum(x['tax_minor'] for x in lines)
            if subtotal+tax>2**53-1:raise BusinessError('Total exceeds the supported integer range')
            payload=dict(schema='musebreak.invoice.v1',invoice_id=iid,owner=owner,operation='issue_invoice',customer=customer,currency='INR',items=lines,subtotal_minor=subtotal,tax_minor=tax,total_minor=subtotal+tax)
            h=digest(payload)
            db.execute('INSERT INTO biz_invoices(id,owner,payload_json,payload_hash,status) VALUES (?,?,?,?,?)',(iid,owner,canonical(payload).decode(),h,'draft'))
        return dict(payload=payload,payload_hash=h,status='draft')

    def approve(self,owner,iid,expected_hash,now=None):
        now=int(time.time()) if now is None else now
        with self.transaction() as db:
            row=self.invoice(db,owner,iid)
            if row['status']!='draft':raise BusinessError('Only a draft can be approved')
            if expected_hash!=row['payload_hash']:raise BusinessError('Approval hash does not match the exact draft')
            approval=self.sign(dict(invoice_id=iid,owner=owner,actor=owner,scope='issue_invoice:once',payload_hash=expected_hash,nonce=uuid.uuid4().hex,approved_at=now,expires_at=now+300),'musebreak.approval.v1')
            db.execute("UPDATE biz_invoices SET status='approved',approval_json=? WHERE id=?",(canonical(approval).decode(),iid))
        return approval

    def _before_commit(self,db):
        """Fault-injection seam used only in rollback tests. Production is a no-op."""

    def issue(self,owner,iid,expected_hash,now=None):
        now=int(time.time()) if now is None else now
        with self.transaction() as db:
            row=self.invoice(db,owner,iid)
            if row['payload_hash']!=expected_hash:raise BusinessError('Issue hash does not match approved payload')
            if row['status']=='issued':return json.loads(row['receipt_json'])
            if row['status']!='approved':raise BusinessError('Explicit authenticated approval required')
            approval=json.loads(row['approval_json']);a=approval['body']
            if approval['domain']!='musebreak.approval.v1' or approval['key_id']!=self.key_id or approval['algorithm']!='Ed25519':raise BusinessError('Approval signing context mismatch')
            try:self.key.public_key().verify(base64.b64decode(approval['signature'],validate=True),b'musebreak.approval.v1\0'+canonical(a))
            except Exception as e:raise BusinessError('Approval signature does not verify') from e
            if a['payload_hash']!=expected_hash or a['invoice_id']!=iid or a['owner']!=owner or a['actor']!=owner or a['scope']!='issue_invoice:once':raise BusinessError('Approval binding mismatch')
            if not a['approved_at']<=now<a['expires_at']:raise BusinessError('Approval expired or not yet valid')
            payload=json.loads(row['payload_json']);movements=[]
            for line in payload['items']:
                p=db.execute('SELECT stock FROM biz_products WHERE owner=? AND id=?',(owner,line['product_id'])).fetchone()
                if p is None or p['stock']<line['quantity']:raise BusinessError('Insufficient stock at commit')
                after=p['stock']-line['quantity'];mid=uuid.uuid4().hex
                db.execute('UPDATE biz_products SET stock=? WHERE owner=? AND id=?',(after,owner,line['product_id']))
                db.execute('INSERT INTO biz_movements VALUES (?,?,?,?,?,?,?)',(mid,owner,iid,line['product_id'],-line['quantity'],p['stock'],after))
                movements.append(dict(id=mid,product_id=line['product_id'],delta=-line['quantity'],before_stock=p['stock'],after_stock=after))
            event=dict(id=uuid.uuid4().hex,invoice_id=iid,owner=owner,kind='invoice.issued',payload_hash=expected_hash,issued_at=now,movements=movements)
            db.execute('INSERT INTO biz_events VALUES (?,?,?,?,?,?)',(event['id'],owner,iid,event['kind'],canonical(event).decode(),digest(event)))
            body=dict(schema='musebreak.invoice-receipt.v1',invoice=payload,payload_hash=expected_hash,approval=approval,result=dict(status='issued',issued_at=now,movements=movements,event_id=event['id'],event_hash=digest(event)))
            receipt=self.sign(body,'musebreak.invoice-receipt.v1')
            db.execute("UPDATE biz_invoices SET status='issued',issued_at=?,receipt_json=? WHERE id=?",(now,canonical(receipt).decode(),iid))
            self._before_commit(db)
        return receipt

    def get(self,owner,iid):
        with self.connection() as db:
            row=self.invoice(db,owner,iid)
            return dict(payload=json.loads(row['payload_json']),payload_hash=row['payload_hash'],status=row['status'],receipt=json.loads(row['receipt_json']) if row['receipt_json'] else None)
