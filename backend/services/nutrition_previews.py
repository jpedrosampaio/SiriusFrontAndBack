"""Owned upload receipts: no plan/meal/target/XP writes until one confirmation."""
import hashlib
import json
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select,text
from db.activity import run_activity
from db.models.identity import ActivityReceipt
from db.session import unit_of_work


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


@asynccontextmanager
async def upload_analysis(user_id,upload_digest):
    key=int.from_bytes(hashlib.sha256(f'nutrition-import:{UUID(str(user_id))}:{upload_digest}'.encode()).digest()[:8],'big',signed=True)
    async with unit_of_work() as session:
        if not await session.scalar(text('SELECT pg_try_advisory_xact_lock(:key)'),{'key':key}):
            raise HTTPException(409,'Este documento já está sendo analisado. Aguarde e tente novamente para reutilizar a prévia.',headers={'Retry-After':'2'})
        yield session


async def create_preview(user_id,plan,upload_digest,*,session=None):
    key='nutrition-preview-'+upload_digest[:32]
    async def apply(session,owner):
        previous=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==owner.id,ActivityReceipt.request_key==key))
        if previous:
            if previous.result.get('kind')!='nutrition_upload_preview' or previous.result.get('upload_digest')!=upload_digest:
                raise HTTPException(409,'Identidade de upload conflitante.')
            if previous.result.get('consumed_digest') or datetime.fromisoformat(previous.result['expires_at'])>=datetime.now(timezone.utc):
                return preview_response(previous.result)
        result={'kind':'nutrition_upload_preview','preview_id':key,'preview':plan.model_dump(mode='json'),
            'upload_digest':upload_digest,'expires_at':(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat(),
            'composition_source':'estimated_from_ai','requires_confirmation':True,'saved':False}
        if previous:previous.result=result
        else:session.add(ActivityReceipt(user_id=owner.id,request_key=key,fingerprint=digest(['nutrition-upload-preview',upload_digest]),result=result))
        return preview_response(result)
    if session is not None:
        from db.repositories.identity import IdentityRepository
        owner=await IdentityRepository(session).by_id(UUID(str(user_id)),lock=True)
        if owner is None:raise HTTPException(404,'Usuário não encontrado.')
        result=await apply(session,owner);await session.flush();return result
    return await run_activity(UUID(str(user_id)),None,['nutrition-upload-preview',upload_digest],apply)


def preview_response(result):
    public={k:v for k,v in result.items() if k not in ('consumed_digest','saved_result')}
    if result.get('consumed_digest'):
        public.update(already_confirmed=True,requires_confirmation=False,plan=result['saved_result']['plan'],xp_earned=0)
    return public


async def existing_preview(user_id,upload_digest,*,session=None):
    async def read(session):
        receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==UUID(str(user_id)),
            ActivityReceipt.request_key=='nutrition-preview-'+upload_digest[:32]))
        if receipt and receipt.result.get('kind')=='nutrition_upload_preview' and receipt.result.get('upload_digest')==upload_digest and (receipt.result.get('consumed_digest') or
                datetime.fromisoformat(receipt.result['expires_at'])>=datetime.now(timezone.utc)):
            return preview_response(receipt.result)
        return None
    if session is not None:return await read(session)
    async with unit_of_work() as session:return await read(session)


def immutable_shape(plan):
    value=deepcopy(plan)
    value.pop('name',None);value.pop('start_date',None)
    for day in value['days']:
        for meal in day['meals']:
            for key in ('calories','protein','carbs','fat'):meal.pop(key,None)
            for food in meal['foods']:
                for key in ('quantity','calories','protein','carbs','fat','known_macros'):food.pop(key,None)
    return value


async def validate_preview(session,owner,preview_id,plan):
    receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==owner.id,
        ActivityReceipt.request_key==preview_id))
    if receipt is None or receipt.result.get('kind')!='nutrition_upload_preview':
        raise HTTPException(404,'Prévia de upload própria não encontrada.')
    proposed=plan.model_dump(mode='json');result=receipt.result
    if immutable_shape(proposed)!=immutable_shape(result['preview']):
        raise HTTPException(409,'A estrutura/origem da prévia mudou; analise novamente o documento.')
    confirmation_digest=digest(proposed)
    if result.get('consumed_digest'):
        if result['consumed_digest']!=confirmation_digest:
            raise HTTPException(409,'Esta prévia já foi confirmada com outros dados.')
        return receipt,confirmation_digest,{**result['saved_result'],'replayed':True}
    if datetime.fromisoformat(result['expires_at'])<datetime.now(timezone.utc):
        raise HTTPException(409,'Prévia expirada; analise novamente o documento.')
    return receipt,confirmation_digest,None
