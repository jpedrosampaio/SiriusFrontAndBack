"""Durable generation reservation; never hold database locks during provider calls."""
import hashlib
import json
import logging
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from db.models.identity import ActivityReceipt
from db.repositories.identity import IdentityRepository
from db.session import unit_of_work
from services import exam_catalog

LEASE_KEY='_question_generation_lease'


async def generate_once(user_id,key,fingerprint,generate,xp=5,persist=None):
    uid=exam_catalog.identity(user_id)
    if key is None:
        document,questions=await generate()
        if persist:
            from db.activity import run_activity
            async def apply(session,user):return await persist(session,user,document,questions)
            return await run_activity(uid,None,fingerprint,apply)
        return await exam_catalog.create(user_id,None,fingerprint,document,questions,xp=xp)
    if not 8<=len(key)<=128 or not all(c.isascii() and (c.isalnum() or c in '-_') for c in key):
        raise HTTPException(422,'Invalid Idempotency-Key')
    digest=hashlib.sha256(json.dumps(fingerprint,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    token=str(uuid4());now=datetime.now(timezone.utc)
    async with unit_of_work() as session:
        user=await IdentityRepository(session).by_id(uid,lock=True)
        if user is None:raise HTTPException(404,'User not found')
        receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==uid,ActivityReceipt.request_key==key))
        if receipt:
            if receipt.fingerprint!=digest:raise HTTPException(409,'Idempotency-Key already used for another action')
            lease=receipt.result.get(LEASE_KEY)
            if not lease:return {**receipt.result,'replayed':True}
            if datetime.fromisoformat(lease['until'])>now:
                raise HTTPException(409,{'code':'question_generation_in_progress','message':'Esta geração ainda está em andamento. Aguarde e tente novamente com a mesma solicitação.'})
        else:
            receipt=ActivityReceipt(user_id=uid,request_key=key,fingerprint=digest)
            session.add(receipt)
        receipt.result={LEASE_KEY:{'token':token,'until':(now+timedelta(minutes=15)).isoformat()}}
    completed=False
    try:
        document,questions=await generate()
        async with unit_of_work() as session:
            user=await IdentityRepository(session).by_id(uid,lock=True)
            receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==uid,ActivityReceipt.request_key==key))
            if user is None or receipt is None or receipt.result.get(LEASE_KEY,{}).get('token')!=token:
                raise HTTPException(409,'A geração perdeu sua reserva. Consulte os simulados e tente novamente.')
            result=await persist(session,user,document,questions) if persist else await exam_catalog.create_in_session(session,user,document,questions,xp=xp)
            receipt.result=result
        completed=True
        return result
    finally:
        if not completed:
            # A crashed worker leaves a bounded reservation. A normal failure releases only its own lease.
            try:
                async with unit_of_work() as session:
                    await IdentityRepository(session).by_id(uid,lock=True)
                    receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==uid,ActivityReceipt.request_key==key))
                    if receipt and receipt.result.get(LEASE_KEY,{}).get('token')==token:await session.delete(receipt)
            except Exception as exc:
                logging.warning('Question generation reservation cleanup: %s',type(exc).__name__)
