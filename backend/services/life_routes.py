"""Explicit preview/apply boundary; no AI, payment, completion or XP writes."""
from datetime import datetime, time, timedelta
from datetime import timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, HTTPException
from pydantic import Field
from sqlalchemy import select
from life_contracts import Contract, Availability, Scenario, Allocation, LifeState
from services.auth_routes import account
from services.life_state import snapshot, collect, daily, preview
from db.activity import run_activity
from db.models.health import WorkoutPlan
from db.models.planning import CalendarEvent

router=APIRouter(prefix='/life')


@router.get('/state',response_model=LifeState)
async def state(request:Request, date: str|None=None):
    from datetime import date as CivilDate
    user=await account(request)
    try:day=CivilDate.fromisoformat(date) if date else None
    except ValueError:raise HTTPException(422,'Data inválida.')
    return (await snapshot(user['user_id'],day=day)).model_dump(mode='json')


@router.post('/simulate')
async def simulate(request:Request,body:Scenario):
    user=await account(request)
    return await daily(user['user_id'],day=body.date,scenario=body)


@router.put('/availability')
async def availability(request:Request,body:Availability):
    user=await account(request); key=request.headers.get('Idempotency-Key')
    if not key:raise HTTPException(428,'Idempotency-Key obrigatório.')
    async def apply(session,user):
        if body.training_plan_id:
            row=await session.scalar(select(WorkoutPlan.id).where(WorkoutPlan.user_id==user.id,
                WorkoutPlan.id==body.training_plan_id,WorkoutPlan.archived_at.is_(None)))
            if row is None:raise HTTPException(404,'Plano de treino não encontrado.')
        prefs=dict(user.preferences or {});prefs['life_availability']=body.model_dump(mode='json');user.preferences=prefs
        return {'availability':body.model_dump(mode='json')}
    return await run_activity(UUID(user['user_id']),key,['life_availability',body.model_dump(mode='json')],apply)


class Accept(Contract):
    scenario:Scenario
    fingerprint:str=Field(pattern=r'^[a-f0-9]{64}$')
    blocks:list[Allocation]=Field(max_length=800)
    confirmed:bool


@router.post('/accept')
async def accept(request:Request,body:Accept):
    user=await account(request);key=request.headers.get('Idempotency-Key')
    if not key:raise HTTPException(428,'Idempotency-Key obrigatório.')
    if body.confirmed is not True:raise HTTPException(422,'Confirmação explícita obrigatória.')
    async def apply(session,user):
        current=await collect(session,user.id,day=body.scenario.date,user=user)
        if current.fingerprint!=body.fingerprint:raise HTTPException(409,'Os dados mudaram. Simule novamente antes de confirmar.')
        plan=preview(current,body.scenario)
        if not current.planning_safe:raise HTTPException(409,'Restrições incompletas; alocação suspensa.')
        # Scenarios with fabricated availability are never committed as real time.
        if body.scenario.windows is not None:raise HTTPException(422,'Salve a disponibilidade real antes de confirmar este cenário.')
        if [b.model_dump(mode='json') for b in body.blocks]!=plan['blocks']:raise HTTPException(409,'O plano mudou ou foi editado. Simule novamente.')
        midnight=datetime.combine(current.date,time(),ZoneInfo(current.timezone))
        saved=[]
        for block in plan['blocks']:
            row=CalendarEvent(user_id=user.id,title=block['title'],start_at=midnight+timedelta(minutes=block['start_minute']),
                end_at=midnight+timedelta(minutes=block['end_minute']),source_type='global_plan',source_id=UUID(block['source_id']),
                details={'candidate_id':block['candidate_id'],'domain':block['domain'],'link':block['link'],
                    'duration_origin':block['duration_origin'],'reasons':block['reasons'],'version':'global-planner/1'})
            session.add(row);await session.flush();saved.append(str(row.id))
        return {'event_ids':saved,'date':str(current.date),'xp_earned':0,'fixed_moved':False}
    return await run_activity(UUID(user['user_id']),key,['global_plan',body.model_dump(mode='json')],apply)


@router.delete('/allocations/{event_id}')
async def release(request:Request,event_id:UUID,confirmed:bool=False):
    user=await account(request);key=request.headers.get('Idempotency-Key')
    if not key:raise HTTPException(428,'Idempotency-Key obrigatório.')
    if not confirmed:raise HTTPException(422,'Confirme a liberação deste horário flexível.')
    async def apply(session,user):
        row=await session.scalar(select(CalendarEvent).where(CalendarEvent.user_id==user.id,
            CalendarEvent.id==event_id,CalendarEvent.source_type=='global_plan').with_for_update())
        if row is None:raise HTTPException(404,'Alocação flexível não encontrada.')
        if row.start_at<=datetime.now(timezone.utc):raise HTTPException(409,'Horários iniciados permanecem no histórico.')
        # Fixed commitments are never selected; original domain records are untouched.
        await session.delete(row)
        return {'released_event_id':str(event_id),'xp_earned':0,'fixed_moved':False}
    return await run_activity(UUID(user['user_id']),key,['release_global_allocation',str(event_id)],apply)
