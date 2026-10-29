"""Opt-in endpoints; all routes require the existing two-gate Wonder credential."""
import os
from functools import lru_cache
from typing import Callable
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,StrictInt
from .service import InvoiceService,BusinessError

class StrictRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
class ProductRequest(StrictRequest):
    name:str=Field(min_length=1,max_length=100)
    price_minor:StrictInt=Field(ge=0,le=10**9)
    tax_bps:StrictInt=Field(ge=0,le=10000)
    stock:StrictInt=Field(ge=0,le=10**9)
class Line(StrictRequest):
    product_id:str=Field(min_length=1,max_length=64)
    quantity:StrictInt=Field(ge=1,le=10**6)
class DraftRequest(StrictRequest):
    customer:str=Field(min_length=1,max_length=200)
    items:list[Line]=Field(min_length=1,max_length=20)
class HashRequest(StrictRequest):
    payload_hash:str=Field(pattern=r'^[0-9a-f]{64}$')

@lru_cache(maxsize=1)
def configured_service(db,key):return InvoiceService(db,key)

def get_service():
    db=os.getenv('BUSINESS_DB_PATH','');key=os.getenv('BUSINESS_SIGNING_KEY_PATH','')
    if not db or not key:raise HTTPException(503,'Invoice workflow not configured: database and persistent signing key required')
    try:return configured_service(db,key)
    except Exception as e:raise HTTPException(503,'Invoice persistence/signing configuration unavailable') from e

def create_router(auth:Callable, production_key_check:Callable):
    router=APIRouter(prefix='/business',tags=['verified-invoice'])
    def business_actor(actor:dict=Depends(auth)):
        subject=os.getenv('BUSINESS_OPERATOR_SUBJECT','')
        allowed={x.strip() for x in os.getenv('BUSINESS_ALLOWED_KEY_IDS','').split(',') if x.strip()}
        if not subject or not allowed:raise HTTPException(503,'Business operator and MetaKey allowlist must be configured')
        if actor.get('sub')!=subject or actor.get('key_id') not in allowed:raise HTTPException(403,'Credential is not authorized for this business')
        if os.getenv('BUSINESS_ALLOW_DEMO_AUTH','').lower()!='true' and not production_key_check(actor['key_id']):
            raise HTTPException(403,'Public demo MetaKey material is not allowed for business operations')
        return actor
    def perform(callback):
        try:return callback()
        except BusinessError as e:raise HTTPException(409,str(e)) from e
    @router.post('/products')
    def product(body:ProductRequest,actor:dict=Depends(business_actor),service:InvoiceService=Depends(get_service)):
        return perform(lambda:service.add_product(actor['sub'],**body.model_dump()))
    @router.post('/invoices')
    def draft(body:DraftRequest,actor:dict=Depends(business_actor),service:InvoiceService=Depends(get_service)):
        return perform(lambda:service.draft(actor['sub'],body.customer,[i.model_dump() for i in body.items]))
    @router.get('/invoices/{invoice_id}')
    def get(invoice_id:str,actor:dict=Depends(business_actor),service:InvoiceService=Depends(get_service)):
        return perform(lambda:service.get(actor['sub'],invoice_id))
    @router.post('/invoices/{invoice_id}/approve')
    def approve(invoice_id:str,body:HashRequest,actor:dict=Depends(business_actor),service:InvoiceService=Depends(get_service)):
        return perform(lambda:service.approve(actor['sub'],invoice_id,body.payload_hash))
    @router.post('/invoices/{invoice_id}/issue')
    def issue(invoice_id:str,body:HashRequest,actor:dict=Depends(business_actor),service:InvoiceService=Depends(get_service)):
        return perform(lambda:service.issue(actor['sub'],invoice_id,body.payload_hash))
    return router
