from datetime import date as Date,timedelta
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field,StrictBool,model_validator
from sqlalchemy import select,func,delete
from sqlalchemy.orm import selectinload
from db.models.health import WorkoutLog,WorkoutLogExercise,WorkoutSet,WorkoutSession,SessionExercise
from db.repositories.health import HealthRepository
from db.activity import run_activity
from db.session import unit_of_work
from services.auth_routes import account
from services.workout_plan_routes import Exercise
from services.workout_session_routes import SetData
from services.workouts import exercise_json
from services.planning import apply_xp,streaks
from services.time import local_today

router=APIRouter()


class LoggedExercise(Exercise):
    completed: StrictBool=False
    sets_completed: int=Field(default=0,ge=0)
    time_spent_seconds: int=Field(default=0,ge=0,le=86400)
    sets_data: list[SetData]=Field(default_factory=list,max_length=100)

    @model_validator(mode='after')
    def validate_sets(self):
        if len(self.sets_data)>self.sets or self.sets_completed>self.sets: raise ValueError('Quantidade de séries inválida.')
        if self.sets_data:self.sets_completed=sum(s.completed for s in self.sets_data)
        return self


class LogBody(BaseModel):
    plan_id: UUID | None=None
    activity_type: str=Field(min_length=1,max_length=100)
    name: str=Field(min_length=1,max_length=300)
    duration_minutes: int=Field(default=0,ge=0,le=1440)
    distance_km: float | None=Field(default=None,ge=0,le=2000,allow_inf_nan=False)
    calories: int | None=Field(default=None,ge=0,le=50000)
    exercises_completed: list[LoggedExercise]=Field(default_factory=list,max_length=500)
    notes: str | None=Field(default=None,max_length=20000)
    date: Date


def log_json(row,exercises):
    result={c.key:getattr(row,c.key) for c in row.__table__.columns}
    result['log_id']=result.pop('id'); result['exercises_completed']=[exercise_json(ex) for ex in exercises]
    return jsonable_encoder(result)


async def serialize_logs(session,uid,rows):
    sessions=(await session.scalars(select(WorkoutSession).where(WorkoutSession.user_id==uid,
        WorkoutSession.id.in_([r.session_id for r in rows if r.session_id])).options(
            selectinload(WorkoutSession.exercises).selectinload(SessionExercise.actual_sets)))).all()
    by_session={s.id:s.exercises for s in sessions}
    manual=(await session.scalars(select(WorkoutLogExercise).where(WorkoutLogExercise.user_id==uid,
        WorkoutLogExercise.log_id.in_([r.id for r in rows if r.session_id is None])).options(selectinload(WorkoutLogExercise.actual_sets))
        .order_by(WorkoutLogExercise.position))).all()
    by_log={}
    for ex in manual:by_log.setdefault(ex.log_id,[]).append(ex)
    return [log_json(row,by_session.get(row.session_id,[]) if row.session_id else by_log.get(row.id,[])) for row in rows]


async def add_log(session,user,body,xp):
    if body.plan_id and await HealthRepository(session).plan(user.id,body.plan_id) is None: raise HTTPException(404,'Plano não encontrado.')
    row=WorkoutLog(user_id=user.id,**body.model_dump(exclude={'exercises_completed'}),completed=True,xp_earned=xp)
    session.add(row); await session.flush()
    for position,data in enumerate(body.exercises_completed):
        ex=WorkoutLogExercise(user_id=user.id,log_id=row.id,position=position,**data.model_dump(exclude={'sets_data'}))
        session.add(ex); await session.flush()
        session.add_all([WorkoutSet(user_id=user.id,log_exercise_id=ex.id,position=index,**value.model_dump()) for index,value in enumerate(data.sets_data)])
    apply_xp(user,xp); await session.flush()
    return (await serialize_logs(session,user.id,[row]))[0]


@router.get('/workouts')
async def logs(request: Request,date: Date | None=None):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        query=select(WorkoutLog).where(WorkoutLog.user_id==uid)
        if date:query=query.where(WorkoutLog.date==date)
        rows=(await session.scalars(query.order_by(WorkoutLog.created_at.desc()).limit(100))).all()
        return await serialize_logs(session,uid,rows)


@router.post('/workouts')
async def create(request: Request,body: LogBody):
    user=await account(request)
    async def apply(session,owner):
        result=await add_log(session,owner,body,10+(body.duration_minutes//15)*5)
        return {**result,'new_xp':owner.xp,'new_rank':owner.rank}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['log-workout',body.model_dump(mode='json')],apply)


async def owned_log(session,uid,log_id):
    row=await session.scalar(select(WorkoutLog).where(WorkoutLog.user_id==uid,WorkoutLog.id==log_id))
    if row is None:raise HTTPException(404,'Treino não encontrado.')
    return row


@router.patch('/workouts/{log_id}/toggle')
async def toggle(request: Request,log_id: UUID):
    user=await account(request)
    async def apply(session,owner):
        row=await owned_log(session,owner.id,log_id); row.completed=not row.completed
        change=row.xp_earned if row.completed else -row.xp_earned; apply_xp(owner,change)
        return {'message':'Workout toggled','completed':row.completed,'xp_change':change,'new_xp':owner.xp,'new_rank':owner.rank}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['toggle-workout',str(log_id)],apply)


@router.delete('/workouts/{log_id}')
async def remove(request: Request,log_id: UUID):
    user=await account(request)
    async def apply(session,owner):
        row=await owned_log(session,owner.id,log_id)
        if row.completed:apply_xp(owner,-row.xp_earned)
        await session.execute(delete(WorkoutLog).where(WorkoutLog.user_id==owner.id,WorkoutLog.id==log_id))
        return {'message':'Workout deleted'}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['delete-workout',str(log_id)],apply)


@router.get('/workout-stats')
async def stats(request: Request,period: str='week'):
    user=await account(request); today=local_today(user['timezone']); start=today-timedelta(days={'week':7,'month':30}.get(period,365))
    async with unit_of_work() as session:
        where=(WorkoutLog.user_id==UUID(user['user_id']),WorkoutLog.completed.is_(True),WorkoutLog.date>=start,WorkoutLog.date<=today)
        count,minutes,distance,calories,xp=(await session.execute(select(func.count(),func.coalesce(func.sum(WorkoutLog.duration_minutes),0),
            func.coalesce(func.sum(WorkoutLog.distance_km),0),func.coalesce(func.sum(WorkoutLog.calories),0),func.coalesce(func.sum(WorkoutLog.xp_earned),0)).where(*where))).one()
        types=dict((await session.execute(select(WorkoutLog.activity_type,func.count()).where(*where).group_by(WorkoutLog.activity_type))).all())
        return {'period':period,'total_workouts':count,'total_duration_minutes':minutes,'total_distance_km':round(distance,2),
            'total_calories':calories,'total_xp_earned':xp,'by_activity_type':types}


@router.get('/workout-stats/detailed')
async def detailed(request: Request):
    user=await account(request); today=local_today(user['timezone']); start=today-timedelta(days=29)
    async with unit_of_work() as session:
        groups=(await session.execute(select(WorkoutLog.date,func.sum(WorkoutLog.duration_minutes),func.coalesce(func.sum(WorkoutLog.calories),0),func.count())
            .where(WorkoutLog.user_id==UUID(user['user_id']),WorkoutLog.completed.is_(True),WorkoutLog.date>=start,WorkoutLog.date<=today).group_by(WorkoutLog.date))).all()
    by_day={day:(minutes,calories,count) for day,minutes,calories,count in groups}; weekly={}; daily=[]
    for index in range(30):
        day=start+timedelta(days=index); minutes,calories,count=by_day.get(day,(0,0,0)); week=day.isocalendar().week
        weekly[week]=weekly.get(week,0)+int(count>0)
        daily.append({'date':day.isoformat(),'duration':minutes,'calories':calories,'count':count})
    current,best=streaks(by_day,today); trained=len(by_day)
    return {'daily_data':daily,'current_streak':current,'best_streak':best,'trained_days':trained,'total_days':30,
        'consistency_percentage':round(trained/30*100,1),'avg_duration_minutes':round(sum(v[0] for v in by_day.values())/max(trained,1),1),
        'avg_calories':round(sum(v[1] for v in by_day.values())/max(trained,1),1),'weekly_consistency':weekly}
