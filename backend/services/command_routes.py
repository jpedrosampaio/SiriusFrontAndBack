"""Authenticated control surfaces; simulations/exports cannot apply domain writes."""
from uuid import UUID
from fastapi import APIRouter, Request, Query, HTTPException
from sqlalchemy import select, tuple_
from db.activity import run_activity
from db.session import unit_of_work
from db.models.command import CommandAudit
from db.models.agent import ActionAudit, Action
from command_contracts import Undo, GlobalScenario, MemoryChange, CommandHome
from ai.memory import MemoryInput
from services.auth_routes import account
from services.command_center import home
from services.command_audit import public, undo
from services.agent_memory import Memories
from services.life_state import daily
from services.finance_intelligence import FinanceEngine, exact_wire

router=APIRouter(prefix='/command')


def key(request):
    value=request.headers.get('Idempotency-Key')
    if not value:raise HTTPException(428,'Idempotency-Key obrigatório.')
    return value


@router.get('/home',response_model=CommandHome)
async def get_home(request:Request):
    user=await account(request)
    return await home(user['user_id'])


@router.get('/audit')
async def audit(request:Request,cursor:UUID|None=None,limit:int=Query(20,ge=1,le=50),source:str='command'):
    user=await account(request);uid=UUID(user['user_id'])
    if source not in ('command','agent'):raise HTTPException(422,'Fonte inválida.')
    model=CommandAudit if source=='command' else ActionAudit
    async with unit_of_work() as session:
        query=select(model).where(model.user_id==uid)
        if cursor:
            previous=await session.scalar(select(model).where(model.user_id==uid,model.id==cursor))
            if previous is None:raise HTTPException(422,'Página indisponível nesta conta.')
            query=query.where(tuple_(model.created_at,model.id)<tuple_(previous.created_at,previous.id))
        rows=(await session.scalars(query.order_by(model.created_at.desc(),model.id.desc()).limit(limit+1))).all()
        values=[]
        if source=='command':values=[public(row) for row in rows[:limit]]
        else:
            ids=[r.action_id for r in rows[:limit]]
            actions={r.id:r for r in (await session.scalars(select(Action).where(Action.user_id==uid,Action.id.in_(ids)))).all()}
            for row in rows[:limit]:
                action=actions.get(row.action_id)
                values.append({'id':str(row.id),'actor':'agent','event':row.tool,'action':row.status,
                    'created_at':row.created_at.isoformat(),'entity_type':'agent_action','entity_id':str(row.action_id),
                    'undo_available':False,'why':{'source':'ai_action_audit','evidence':(action.evidence or [])[:12] if action else [],
                        'constraints':['Ação sujeita às permissões e confirmações existentes.'],
                        'limitations':['Registro original do Agent; não oferece desfazer de efeitos externos ou financeiros.']}})
    return {'items':values,'next_cursor':str(rows[limit-1].id) if len(rows)>limit else None,'source':source,'timezone':user['timezone']}


@router.post('/audit/{audit_id}/undo')
async def undo_action(request:Request,audit_id:UUID,body:Undo):
    user=await account(request)
    return await run_activity(UUID(user['user_id']),key(request),['command.undo',str(audit_id)],
        lambda session,user:undo(session,user,audit_id))


@router.get('/memory')
async def memories(request:Request):
    user=await account(request);return await Memories().list(user['user_id'])


@router.post('/memory')
async def add_memory(request:Request,body:MemoryChange):
    user=await account(request)
    if body.expected_version:raise HTTPException(422,'Criação não aceita versão anterior.')
    return await Memories().save(user['user_id'],MemoryInput(**body.model_dump(exclude={'expected_version'})),request_key=key(request))


@router.put('/memory/{memory_id}')
async def edit_memory(request:Request,memory_id:UUID,body:MemoryChange):
    user=await account(request)
    if not body.expected_version:raise HTTPException(428,'Versão atual obrigatória.')
    return await Memories().save(user['user_id'],MemoryInput(**body.model_dump(exclude={'expected_version'})),memory_id,
        request_key=key(request),expected_version=body.expected_version)


@router.delete('/memory/{memory_id}')
async def remove_memory(request:Request,memory_id:UUID,version:str=Query(pattern=r'^[a-f0-9]{64}$')):
    user=await account(request)
    return await Memories().remove(user['user_id'],memory_id,request_key=key(request),expected_version=version)


@router.post('/scenarios')
async def scenario(request:Request,body:GlobalScenario):
    user=await account(request)
    routine=await daily(user['user_id'],day=body.routine.date,scenario=body.routine)
    finance=await FinanceEngine().simulate(UUID(user['user_id']),body.finance) if body.finance else None
    return {'routine':routine,'finance':exact_wire(finance) if finance else None,'read_only':True,
        'limitations':['Cenários são hipóteses; dinheiro hipotético não altera duração ou prioridades automaticamente.',
            'Aplicação exige revisão e confirmação no Calendário; nenhuma transação financeira é executada.']}
