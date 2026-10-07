from decimal import Decimal
from uuid import UUID
from datetime import datetime,timezone
from fastapi import APIRouter,Request,Query,HTTPException
from pydantic import BaseModel,Field,StrictBool,field_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.models.health import WorkoutSession,SessionExercise,WorkoutSet
from db.repositories.health import HealthRepository
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services import workouts

router=APIRouter(prefix='/workout-sessions')


class Start(BaseModel):
    plan_id: UUID
    day_index: int=Field(default=0,ge=0,strict=True)
    rest_timer_seconds: int=Field(default=60,ge=0,le=3600,strict=True)


class SetData(BaseModel):
    reps: int | None=Field(default=None,ge=0,le=999)
    weight: Decimal | None=Field(default=None,ge=0,le=9999999,max_digits=10,decimal_places=3)
    rpe: float | None=Field(default=None,ge=0,le=10,allow_inf_nan=False)
    completed: StrictBool=False

    @field_validator('reps','weight','rpe',mode='before')
    @classmethod
    def optional_number(cls,value): return None if value=='' else value


class Update(BaseModel):
    revision: int | None=Field(default=None,ge=0,strict=True)
    completed: StrictBool | None=None
    sets_completed: int | None=Field(default=None,ge=0,strict=True)
    sets_data: list[SetData] | None=Field(default=None,max_length=100)
    time_spent_seconds: int | None=Field(default=None,ge=0,le=86400,strict=True)
    weight: str | None=Field(default=None,max_length=100)
    current_exercise_idx: int | None=Field(default=None,ge=0,strict=True)


class Feedback(BaseModel):
    difficulty: int=Field(default=3,ge=1,le=5)
    feeling: str=Field(default='',max_length=300)
    notes: str=Field(default='',max_length=10000)


@router.post('/start')
async def start(request: Request,body: Start):
    user=await account(request)
    return await workouts.start_session(UUID(user['user_id']),body.plan_id,body.day_index,body.rest_timer_seconds,request.headers.get('Idempotency-Key'))


@router.get('/active')
async def active(request: Request):
    user=await account(request)
    async with unit_of_work() as session:
        repo=HealthRepository(session); row=await repo.active_session(UUID(user['user_id']))
        if not row: return {'active':False,'session':None}
        row=await repo.workout_session(row.user_id,row.id)
        return {'active':True,'session':workouts.session_json(row)}


@router.get('')
async def history(request: Request,limit: int=Query(20,ge=1,le=100)):
    user=await account(request)
    async with unit_of_work() as session:
        rows=(await session.scalars(select(WorkoutSession).where(WorkoutSession.user_id==UUID(user['user_id']),WorkoutSession.status.in_(['completed','abandoned']))
            .options(selectinload(WorkoutSession.exercises).selectinload(SessionExercise.actual_sets)).order_by(WorkoutSession.started_at.desc()).limit(limit))).all()
        return [workouts.session_json(row) for row in rows]


@router.patch('/{session_id}/exercise/{exercise_idx}')
async def update(request: Request,session_id: UUID,exercise_idx: int,body: Update):
    user=await account(request)
    async def apply(session,owner):
        row=await HealthRepository(session).workout_session(owner.id,session_id)
        if row is None or row.status!='active': raise HTTPException(404,'Sessão não encontrada ou já finalizada.')
        if body.revision is not None and body.revision!=row.revision: raise HTTPException(409,'O treino mudou em outra tela. Atualize antes de registrar.')
        if not 0<=exercise_idx<len(row.exercises): raise HTTPException(422,'Índice de exercício inválido.')
        ex=row.exercises[exercise_idx]
        if body.sets_completed is not None and body.sets_completed>ex.sets: raise HTTPException(422,'Quantidade de séries inválida.')
        if body.current_exercise_idx is not None and body.current_exercise_idx>=len(row.exercises): raise HTTPException(422,'Índice de exercício inválido.')
        for name in ('completed','sets_completed','time_spent_seconds','weight'):
            value=getattr(body,name)
            if value is not None: setattr(ex,name,value)
        if body.sets_data is not None:
            if len(body.sets_data)>ex.sets: raise HTTPException(422,'Quantidade de séries inválida.')
            for old in ex.actual_sets: await session.delete(old)
            await session.flush()
            session.add_all([WorkoutSet(user_id=owner.id,exercise_id=ex.id,position=index,**value.model_dump()) for index,value in enumerate(body.sets_data)])
            ex.sets_completed=sum(value.completed for value in body.sets_data)
        if body.current_exercise_idx is not None: row.current_exercise_idx=body.current_exercise_idx
        row.revision+=1
        await session.flush(); await session.refresh(ex,['actual_sets'])
        return workouts.session_json(row)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),
        ['update-workout-exercise',str(session_id),exercise_idx,body.model_dump(mode='json',exclude_unset=True)],apply)


@router.post('/{session_id}/complete')
async def complete(request: Request,session_id: UUID,body: Feedback):
    user=await account(request)
    return await workouts.complete_session(UUID(user['user_id']),session_id,body.model_dump(),
        request.headers.get('Idempotency-Key') or f'workout-complete-{session_id}')


@router.post('/{session_id}/abandon')
async def abandon(request: Request,session_id: UUID):
    user=await account(request)
    async def apply(session,owner):
        row=await HealthRepository(session).workout_session(owner.id,session_id)
        if row is None or row.status!='active': raise HTTPException(404,'Sessão não encontrada.')
        row.status='abandoned'; row.completed_at=datetime.now(timezone.utc)
        return {'message':'Sessão abandonada'}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['abandon-workout',str(session_id)],apply)
