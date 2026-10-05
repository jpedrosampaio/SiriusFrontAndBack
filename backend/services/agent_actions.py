import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from pydantic import Field
from ai.actions import Preferences, autonomy
from ai.registry import TOOLS, ExpenseArgs, validate_call
from db.activity import run_activity
from db.repositories.agent import AgentRepository
from db.session import unit_of_work
from services.core_writes import CoreWrites
from db.models.agent import Action, Preferences as StoredPreferences


def identity(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(404, 'Proposta não encontrada.') from None


class ExactExpenseArgs(ExpenseArgs):
    amount: Decimal = Field(gt=0,le=1000000000,max_digits=12,decimal_places=2)


def validated_arguments(name,arguments):
    if name == 'record_expense':
        return ExactExpenseArgs.model_validate(arguments).model_dump(mode='json')
    return validate_call(name,arguments)


def public_action(row):
    return {'action_id':str(row.id),'user_id':str(row.user_id),'tool':row.tool,'version':row.version,
        'arguments':row.arguments,'summary':row.summary,'reason':row.reason,'evidence':row.evidence,
        'autonomy':row.autonomy,'status':row.status,'expires_at':row.expires_at.isoformat(),
        'created_at':row.created_at.isoformat(),'result':row.result}


class Actions:
    def __init__(self,writer=None):
        self.writer = writer or CoreWrites()

    async def preferences(self, user_id):
        async with unit_of_work() as session:
            return Preferences.model_validate(await AgentRepository(session).preferences(identity(user_id)))

    async def save_preferences(self, user_id, body):
        if any(name not in TOOLS for name in body.blocked_tools):
            raise HTTPException(422, 'Ferramenta desconhecida.')
        async def apply(session, user):
            await session.execute(insert(StoredPreferences).values(user_id=user.id, settings=body.model_dump())
                .on_conflict_do_update(index_elements=['user_id'], set_={'settings': body.model_dump()}))
            return body.model_dump()
        return await run_activity(identity(user_id), None, ['agent_preferences'], apply)

    async def expire(self, user_id):
        async with unit_of_work() as session:
            await session.execute(update(Action).where(Action.user_id == identity(user_id), Action.status == 'pending',
                Action.expires_at <= datetime.now(timezone.utc)).values(status='expired'))

    async def list(self, user_id):
        await self.expire(user_id)
        async with unit_of_work() as session:
            rows = (await session.scalars(select(Action).where(Action.user_id == identity(user_id))
                .order_by(Action.created_at.desc(), Action.id).limit(30))).all()
            return [public_action(row) for row in rows]

    async def by_ids(self, user_id, action_ids):
        ids = []
        for value in action_ids:
            try: ids.append(UUID(str(value)))
            except (ValueError, TypeError, AttributeError): continue
        if not ids: return []
        await self.expire(user_id)
        async with unit_of_work() as session:
            rows = (await session.scalars(select(Action).where(Action.user_id == identity(user_id), Action.id.in_(ids)))).all()
            return [public_action(row) for row in rows]

    async def propose(self,user_id,request_id,index,name,arguments,reason,evidence=None):
        user_id = identity(user_id)
        tool = TOOLS.get(name)
        if not tool or tool.permission != 'write':
            raise HTTPException(422,'Ação inválida.')
        args = validated_arguments(name,arguments)
        fingerprint = hashlib.sha256(json.dumps([str(user_id),request_id,index,name,args],sort_keys=True).encode()).hexdigest()
        async with unit_of_work() as session:
            repo = AgentRepository(session)
            level = autonomy(tool,Preferences.model_validate(await repo.preferences(user_id)))
            if level == 'BLOCKED':
                raise HTTPException(403,'Esta ferramenta está bloqueada nas preferências.')
            row = await repo.propose(user_id,fingerprint,{'tool':name,'version':tool.version,'arguments':args,
                'summary':tool.description,'reason':str(reason)[:500],'evidence':(evidence or [])[:5],
                'autonomy':level,'status':'pending','expires_at':datetime.now(timezone.utc)+timedelta(minutes=20)})
            return public_action(row)

    async def confirm(self,user_id,action_id):
        user_id, action_id = identity(user_id), identity(action_id)
        await self.expire(user_id)
        async def apply(session,user):
            repo = AgentRepository(session)
            row = await repo.action(user.id,action_id)
            if row is None:
                raise HTTPException(404,'Proposta não encontrada.')
            if row.status == 'executed':
                return {'action_id':str(row.id),'status':'executed','result':row.result,'replayed':True}
            if row.status != 'pending' or row.expires_at <= datetime.now(timezone.utc):
                raise HTTPException(409,'Proposta indisponível ou expirada.')
            tool = TOOLS.get(row.tool)
            if tool is None or row.version != tool.version:
                raise HTTPException(409,'Ferramenta atualizada. Solicite uma nova proposta.')
            if autonomy(tool,Preferences.model_validate(await repo.preferences(user.id))) == 'BLOCKED':
                raise HTTPException(403,'Ferramenta bloqueada.')
            args = validated_arguments(row.tool,row.arguments)
            row.status,row.confirmed_at = 'confirmed',datetime.now(timezone.utc)
            result = await self.writer.execute(row.tool,user,args,session)
            row.status,row.executed_at,row.result = 'executed',datetime.now(timezone.utc),result
            repo.audit(user.id,row)
            return {'action_id':str(row.id),'status':'executed','result':result}
        return await run_activity(user_id,'agent_'+str(action_id),['agent',str(action_id)],apply)

    async def cancel(self,user_id,action_id):
        user_id, action_id = identity(user_id), identity(action_id)
        await self.expire(user_id)
        async def apply(session,user):
            row = await AgentRepository(session).action(user.id,action_id)
            if row is None or row.status != 'pending':
                raise HTTPException(409,'Proposta indisponível ou já processada.')
            row.status = 'cancelled'
            return {'action_id':str(row.id),'status':'cancelled'}
        return await run_activity(user_id,None,['cancel_agent',str(action_id)],apply)
