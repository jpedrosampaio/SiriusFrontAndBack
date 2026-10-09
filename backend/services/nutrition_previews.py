"""Owned upload receipts: no plan/meal/target/XP writes until one confirmation."""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select
from db.activity import run_activity
from db.models.identity import ActivityReceipt


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


async def create_preview(user_id,plan,upload_digest):
    key='nutrition-preview-'+uuid4().hex
    async def apply(session,owner):
        return {'kind':'nutrition_upload_preview','preview_id':key,'preview':plan.model_dump(mode='json'),
            'upload_digest':upload_digest,'expires_at':(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat(),
            'composition_source':'estimated_from_ai','requires_confirmation':True,'saved':False}
    return await run_activity(UUID(str(user_id)),key,['nutrition-upload-preview',upload_digest],apply)


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
