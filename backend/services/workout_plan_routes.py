from datetime import datetime,timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.models.health import WorkoutPlan,WorkoutDay,WorkoutLog
from db.repositories.health import HealthRepository
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.time import local_today

router=APIRouter()


class Exercise(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    sets: int=Field(default=3,ge=1,le=100)
    reps: str=Field(default='12',max_length=100)
    weight: str=Field(default='',max_length=100)
    rest_seconds: int=Field(default=60,ge=0,le=3600)
    muscle_group: str=Field(default='',max_length=300)
    tutorial: str=Field(default='',max_length=20000)
    video_url: str=Field(default='',max_length=2000)
    notes: str=Field(default='',max_length=20000)

    @field_validator('reps','weight',mode='before')
    @classmethod
    def text_number(cls,value): return str(value) if isinstance(value,(int,float)) else value


class Day(BaseModel):
    day_name: str=''
    day_label: str=''
    week: int=Field(default=1,ge=1,le=52)
    split_label: str=''
    progression_focus: str=''
    progression_notes: str=''
    exercises: list[Exercise]=Field(default_factory=list,max_length=100)


class PlanBody(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    description: str | None=None
    exercises: list[Exercise]=Field(default_factory=list,max_length=100)
    plan_duration: str=Field(default='dia',max_length=30)
    days: list[Day] | None=Field(default=None,max_length=366)


def plan_json(row):
    days=[]
    for d in row.days:
        exercises=[{key:getattr(ex,key) for key in Exercise.model_fields} for ex in d.exercises]
        days.append({'day_name':d.name,'day_label':d.label,'week':d.week,'split_label':d.split_label,
            'progression_focus':d.progression_focus,'progression_notes':d.progression_notes,'exercises':exercises})
    return jsonable_encoder({**row.generation_parameters,'plan_id':row.id,'user_id':row.user_id,'name':row.name,'description':row.description,
        'plan_duration':row.plan_duration,'objective':row.objective,'level':row.level,'generated_by_ai':row.generated_by_ai,
        'created_at':row.created_at,'days':days,'exercises':[ex for d in days for ex in d['exercises']]})


@router.get('/workout-plans')
async def plans(request: Request):
    user=await account(request)
    async with unit_of_work() as session:
        rows=(await session.scalars(select(WorkoutPlan).where(WorkoutPlan.user_id==UUID(user['user_id']),WorkoutPlan.archived_at.is_(None))
            .options(selectinload(WorkoutPlan.days).selectinload(WorkoutDay.exercises)).order_by(WorkoutPlan.created_at.desc()).limit(100))).all()
        return [plan_json(row) for row in rows]


@router.post('/workout-plans')
async def create(request: Request,body: PlanBody):
    user=await account(request)
    async def apply(session,owner):
        repo=HealthRepository(session); row=await repo.create_plan(owner.id,**body.model_dump())
        return plan_json(await repo.plan(owner.id,row.id))
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['create-workout-plan',body.model_dump(mode='json')],apply)


@router.patch('/workout-plans/{plan_id}')
async def update(request: Request,plan_id: UUID,body: PlanBody):
    user=await account(request)
    async def apply(session,owner):
        repo=HealthRepository(session); row=await repo.plan(owner.id,plan_id)
        if row is None: raise HTTPException(404,'Plano de treino não encontrado.')
        row.name=body.name; row.description=body.description; row.plan_duration=body.plan_duration
        await repo.replace_days(row,[d.model_dump() for d in body.days] if body.days else None,[ex.model_dump() for ex in body.exercises])
        return {'message':'Workout plan updated'}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['update-workout-plan',str(plan_id),body.model_dump(mode='json')],apply)


@router.delete('/workout-plans/{plan_id}')
async def archive(request: Request,plan_id: UUID):
    user=await account(request)
    async def apply(session,owner):
        row=await HealthRepository(session).plan(owner.id,plan_id)
        if row is None: raise HTTPException(404,'Plano de treino não encontrado.')
        row.archived_at=datetime.now(timezone.utc)
        return {'message':'Workout plan deleted'}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['archive-workout-plan',str(plan_id)],apply)


@router.get('/workouts/today-schedule')
async def today_schedule(request: Request):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        row=await session.scalar(select(WorkoutPlan).where(WorkoutPlan.user_id==uid,WorkoutPlan.archived_at.is_(None))
            .options(selectinload(WorkoutPlan.days).selectinload(WorkoutDay.exercises)).order_by(WorkoutPlan.created_at.desc()).limit(1))
        if row is None or not row.days: return {'scheduled':False,'message':'Nenhum plano de treino encontrado'}
        plan=plan_json(row); index=max(0,(today-row.created_at.astimezone(ZoneInfo(user['timezone'])).date()).days)%len(row.days)
        day=plan['days'][index]
        logged=await session.scalar(select(WorkoutLog.id).where(WorkoutLog.user_id==uid,WorkoutLog.plan_id==row.id,
            WorkoutLog.date==today,WorkoutLog.completed.is_(True)).limit(1))
        return {'scheduled':True,'plan_id':str(row.id),'plan_name':row.name,**day,'day_index':index,'total_days':len(row.days),
            'exercise_count':len(day['exercises']),'already_completed':logged is not None}
