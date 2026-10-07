from datetime import timedelta
from uuid import UUID
from fastapi import APIRouter,Request,Query,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field
from sqlalchemy import select,delete,func
from db.models.health import BodyMeasurement,WorkoutInsight,WorkoutLog
from db.models.identity import User
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.body_measurement_dto import MeasurementBody
from services.time import local_today

router=APIRouter()


def measurement_json(row):
    if row is None:return None
    data={c.key:getattr(row,c.key) for c in row.__table__.columns};data['measurement_id']=data.pop('id')
    data['bmi']=round(row.weight_kg/(row.height_cm/100)**2,1) if row.weight_kg is not None and row.height_cm else None
    return jsonable_encoder(data)


async def measurement_rows(session,uid,limit=30,start=None,end=None):
    query=select(BodyMeasurement).where(BodyMeasurement.user_id==uid)
    if start:query=query.where(BodyMeasurement.date>=start)
    if end:query=query.where(BodyMeasurement.date<=end)
    rows=(await session.scalars(query.order_by(BodyMeasurement.date.desc(),BodyMeasurement.created_at.desc()).limit(limit))).all()
    return [measurement_json(row) for row in rows]


@router.get('/body-measurements')
async def measurements(request: Request,limit: int=Query(30,ge=1,le=1000)):
    user=await account(request)
    async with unit_of_work() as session:return await measurement_rows(session,UUID(user['user_id']),limit)


@router.get('/body-measurements/latest')
async def latest(request: Request):
    user=await account(request)
    async with unit_of_work() as session:
        values=await measurement_rows(session,UUID(user['user_id']),1)
        return values[0] if values else None


@router.get('/body-measurements/evolution')
async def evolution(request: Request,months: int=Query(6,ge=1,le=120)):
    user=await account(request);today=local_today(user['timezone'])
    async with unit_of_work() as session:
        values=list(reversed(await measurement_rows(session,UUID(user['user_id']),1000,today-timedelta(days=months*30),today)))
    changes={}
    if len(values)>=2:
        for field in ('weight_kg','body_fat_percentage','muscle_mass_kg','waist_cm','bmi'):
            if values[0].get(field) is not None and values[-1].get(field) is not None:changes[field]=round(values[-1][field]-values[0][field],2)
    return {'measurements':values,'changes':changes,'total_records':len(values)}


@router.post('/body-measurements')
async def create(request: Request,body: MeasurementBody):
    user=await account(request)
    async def apply(session,owner):
        row=BodyMeasurement(user_id=owner.id,**body.model_dump());session.add(row);await session.flush()
        return measurement_json(row)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['body-measurement',body.model_dump(mode='json')],apply)


async def remove_owned(session,model,uid,identity):
    result=await session.execute(delete(model).where(model.user_id==uid,model.id==identity))
    if not result.rowcount:raise HTTPException(404,'Registro não encontrado.')


@router.delete('/body-measurements/{measurement_id}')
async def remove(request: Request,measurement_id: UUID):
    user=await account(request)
    async with unit_of_work() as session:await remove_owned(session,BodyMeasurement,UUID(user['user_id']),measurement_id)
    return {'message':'Measurement deleted'}


class BasedOn(BaseModel):
    total_workouts: int=Field(default=0,ge=0)
    has_measurements: bool=False
    workout_types: dict[str,int]=Field(default_factory=dict)


class InsightBody(BaseModel):
    title: str=Field(default='Sugestão de Treino',min_length=1,max_length=300)
    content: str=Field(default='',max_length=200000)
    based_on: BasedOn=Field(default_factory=BasedOn)


def insight_json(row):
    return jsonable_encoder({'insight_id':row.id,'user_id':row.user_id,'title':row.title,'content':row.content,'created_at':row.created_at,
        'based_on':{'total_workouts':row.total_workouts,'has_measurements':row.has_measurements,'workout_types':row.workout_types}})


@router.post('/workout-suggestions/save')
async def save_insight(request: Request,body: InsightBody):
    user=await account(request)
    async def apply(session,owner):
        row=WorkoutInsight(user_id=owner.id,title=body.title,content=body.content,**body.based_on.model_dump())
        session.add(row);await session.flush();return insight_json(row)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['workout-insight',body.model_dump(mode='json')],apply)


@router.get('/workout-suggestions/saved')
async def insights(request: Request):
    user=await account(request)
    async with unit_of_work() as session:
        rows=(await session.scalars(select(WorkoutInsight).where(WorkoutInsight.user_id==UUID(user['user_id'])).order_by(WorkoutInsight.created_at.desc()).limit(50))).all()
        return [insight_json(row) for row in rows]


@router.delete('/workout-suggestions/saved/{insight_id}')
async def delete_insight(request: Request,insight_id: UUID):
    user=await account(request)
    async with unit_of_work() as session:await remove_owned(session,WorkoutInsight,UUID(user['user_id']),insight_id)
    return {'message':'Insight removido'}


async def suggestion_context(uid):
    uid=UUID(uid)
    async with unit_of_work() as session:
        owner=await session.get(User,uid);today=local_today(owner.timezone)
        types=dict((await session.execute(select(WorkoutLog.activity_type,func.count()).where(WorkoutLog.user_id==uid,
            WorkoutLog.date>=today-timedelta(days=30),WorkoutLog.date<=today).group_by(WorkoutLog.activity_type))).all())
        values=await measurement_rows(session,uid,1)
        return types,sum(types.values()),values[0] if values else None


async def recommendation_context(uid):
    uid=UUID(uid)
    async with unit_of_work() as session:
        measurements=await measurement_rows(session,uid,5)
        logs=(await session.scalars(select(WorkoutLog).where(WorkoutLog.user_id==uid).order_by(WorkoutLog.date.desc(),WorkoutLog.created_at.desc()).limit(10))).all()
        return measurements,[{'name':row.name,'activity_type':row.activity_type,'duration_minutes':row.duration_minutes} for row in logs]
