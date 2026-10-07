from datetime import datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field
from sqlalchemy import select,delete
from db.models.health import DailyWorkoutStatus,DailyWorkoutCheck,WorkoutLog,WorkoutPlan
from db.repositories.health import HealthRepository
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.time import local_today
from services.planning import apply_xp
from services.workout_plan_routes import plan_json
from services.workout_logs import LogBody,add_log,serialize_logs

router=APIRouter(prefix='/daily-workout-status')


class Completion(BaseModel):
    duration_minutes: int=Field(default=30,ge=0,le=1440)
    calories: int | None=Field(default=None,ge=0,le=50000)
    notes: str=Field(default='',max_length=20000)


async def state(session,uid,pid,today,create=False):
    plan=await HealthRepository(session).plan(uid,pid)
    if plan is None:raise HTTPException(404,'Plano não encontrado.')
    row=await session.scalar(select(DailyWorkoutStatus).where(DailyWorkoutStatus.user_id==uid,DailyWorkoutStatus.plan_id==pid,DailyWorkoutStatus.date==today))
    if row is None and create:
        row=DailyWorkoutStatus(user_id=uid,plan_id=pid,date=today);session.add(row);await session.flush()
    checks=(await session.scalars(select(DailyWorkoutCheck).where(DailyWorkoutCheck.user_id==uid,DailyWorkoutCheck.status_id==row.id))).all() if row else []
    return plan,row,checks


async def public(session,row,checks):
    if row is None:return {'exercises_status':{},'completed':False}
    completed=await session.scalar(select(WorkoutLog.completed).where(WorkoutLog.user_id==row.user_id,WorkoutLog.id==row.log_id)) if row.log_id else False
    return jsonable_encoder({'status_id':row.id,'user_id':row.user_id,'plan_id':row.plan_id,'date':row.date,
        'exercises_status':{str(check.exercise_index):True for check in checks},'completed':bool(completed),
        'created_at':row.created_at,'updated_at':row.updated_at})


@router.get('')
async def batch(request: Request):
    user=await account(request)
    uid=UUID(user['user_id']);today=local_today(user['timezone'])
    async with unit_of_work() as session:
        # A projection, not a plan graph load. Two queries independent of plan count.
        rows=(await session.execute(select(WorkoutPlan.id,DailyWorkoutStatus.id,DailyWorkoutStatus.created_at,
            DailyWorkoutStatus.updated_at,WorkoutLog.completed).outerjoin(DailyWorkoutStatus,
            (DailyWorkoutStatus.plan_id==WorkoutPlan.id)&(DailyWorkoutStatus.user_id==uid)&(DailyWorkoutStatus.date==today))
            .outerjoin(WorkoutLog,(WorkoutLog.id==DailyWorkoutStatus.log_id)&(WorkoutLog.user_id==uid))
            .where(WorkoutPlan.user_id==uid,WorkoutPlan.archived_at.is_(None)))).all()
        checks=(await session.execute(select(DailyWorkoutCheck.status_id,DailyWorkoutCheck.exercise_index)
            .join(DailyWorkoutStatus,(DailyWorkoutStatus.id==DailyWorkoutCheck.status_id)&(DailyWorkoutStatus.user_id==uid))
            .where(DailyWorkoutCheck.user_id==uid,DailyWorkoutStatus.date==today))).all()
        grouped={}
        for sid,index in checks:grouped.setdefault(sid,{})[str(index)]=True
        return jsonable_encoder({str(pid):{'exercises_status':grouped.get(sid,{}),'completed':bool(done),
            'date':today,'status_id':sid,'created_at':created,'updated_at':updated}
            for pid,sid,created,updated,done in rows})


@router.get('/{plan_id}')
async def get(request: Request,plan_id: UUID):
    user=await account(request)
    async with unit_of_work() as session:
        _,row,checks=await state(session,UUID(user['user_id']),plan_id,local_today(user['timezone']))
        return await public(session,row,checks)


@router.post('/{plan_id}/toggle/{exercise_idx}')
async def toggle(request: Request,plan_id: UUID,exercise_idx: int):
    user=await account(request)
    async def apply(session,owner):
        plan,row,checks=await state(session,owner.id,plan_id,local_today(owner.timezone),True)
        if not 0<=exercise_idx<sum(len(d.exercises) for d in plan.days):raise HTTPException(422,'Índice de exercício inválido.')
        check=next((c for c in checks if c.exercise_index==exercise_idx),None)
        if check:await session.delete(check);checks.remove(check)
        else:
            check=DailyWorkoutCheck(user_id=owner.id,status_id=row.id,exercise_index=exercise_idx);session.add(check);checks.append(check)
        row.updated_at=datetime.now(timezone.utc);await session.flush()
        return await public(session,row,checks)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['toggle-daily-workout',str(plan_id),exercise_idx,local_today(user['timezone']).isoformat()],apply)


@router.post('/{plan_id}/complete')
async def complete(request: Request,plan_id: UUID,body: Completion):
    user=await account(request)
    async def apply(session,owner):
        today=local_today(owner.timezone);plan,row,checks=await state(session,owner.id,plan_id,today,True)
        if row.log_id:
            previous=await session.scalar(select(WorkoutLog).where(WorkoutLog.user_id==owner.id,WorkoutLog.id==row.log_id))
            result=(await serialize_logs(session,owner.id,[previous]))[0]
            if not previous.completed:previous.completed=True;apply_xp(owner,previous.xp_earned)
            result['completed']=True
            count=sum(ex['completed'] for ex in result['exercises_completed'])
            total=len(result['exercises_completed'])
        else:
            selected={c.exercise_index for c in checks};document=plan_json(plan)
            exercises=[{**ex,'completed':index in selected} for index,ex in enumerate(document['exercises'])]
            count=sum(ex['completed'] for ex in exercises);total=len(exercises)
            xp=10+(int(count/total*30) if total else 0)+(body.duration_minutes//15)*5
            data=LogBody(plan_id=plan_id,name=plan.name,activity_type='weightlifting',date=today,duration_minutes=body.duration_minutes,
                calories=body.calories if body.calories is not None else body.duration_minutes*6,notes=body.notes,exercises_completed=exercises)
            result=await add_log(session,owner,data,xp);row.log_id=UUID(result['log_id'])
        return {**result,'new_xp':owner.xp,'new_rank':owner.rank,'exercises_completed_count':count,'total_exercises':total}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),
        ['complete-daily-workout',str(plan_id),local_today(user['timezone']).isoformat(),body.model_dump(mode='json')],apply)


@router.post('/{plan_id}/reset')
async def reset(request: Request,plan_id: UUID):
    user=await account(request)
    async def apply(session,owner):
        today=local_today(owner.timezone);_,row,_=await state(session,owner.id,plan_id,today)
        if row:
            await session.execute(delete(DailyWorkoutCheck).where(DailyWorkoutCheck.user_id==owner.id,DailyWorkoutCheck.status_id==row.id))
            if row.log_id:
                log=await session.scalar(select(WorkoutLog).where(WorkoutLog.user_id==owner.id,WorkoutLog.id==row.log_id))
                if log and log.completed:apply_xp(owner,-log.xp_earned)
                log_id=row.log_id;row.log_id=None;await session.flush()
                await session.execute(delete(WorkoutLog).where(WorkoutLog.user_id==owner.id,WorkoutLog.id==log_id))
            row.updated_at=datetime.now(timezone.utc)
        return {'message':'Daily workout status reset','date':today.isoformat()}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['reset-daily-workout',str(plan_id),local_today(user['timezone']).isoformat()],apply)
