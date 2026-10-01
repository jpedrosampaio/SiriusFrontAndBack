from datetime import date,datetime,timezone
from uuid import UUID
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field,StrictBool,field_validator
from sqlalchemy import select,func,or_
from db.models.studies import StudyTask,StudyTaskCheck,Notebook
from db.session import unit_of_work
from services.auth_routes import account
from services.study_activity_routes import mutate
from services.studies_catalog import owned
from services.time import local_today
from services.planning import apply_xp

router=APIRouter(prefix='/study/tasks')


class TaskBody(BaseModel):
    notebook_id: UUID | None=None
    title: str = Field(min_length=1,max_length=300)
    description: str | None=None
    task_type: Literal['reading','exercise','review','project','exam']='reading'
    recurrence: Literal['once','daily','weekly','monthly']='once'
    deadline: date | None=None
    reminder: datetime | None=None
    priority: Literal['low','medium','high']='medium'
    estimated_minutes: int = Field(default=30,ge=0,le=10080)

    @field_validator('deadline','reminder',mode='before')
    @classmethod
    def empty_date(cls,value): return None if value=='' else value


class UpdateBody(BaseModel):
    title: str | None=Field(default=None,min_length=1,max_length=300)
    description: str | None=None
    recurrence: Literal['once','daily','weekly','monthly'] | None=None
    deadline: date | None=None
    reminder: datetime | None=None
    priority: Literal['low','medium','high'] | None=None
    estimated_minutes: int | None=Field(default=None,ge=0,le=10080)
    actual_minutes: int | None=Field(default=None,ge=0,le=10080)
    notes: str | None=None
    completed: StrictBool | None=None

    @field_validator('deadline','reminder',mode='before')
    @classmethod
    def empty_date(cls,value): return None if value=='' else value


def public(row,latest,today):
    result={c.key:getattr(row,c.key) for c in row.__table__.columns if c.key!='archived_at'}
    result['task_id']=result.pop('id')
    result['completed']=bool(latest and row.recurrence=='once')
    result['completed_today']=bool(latest and (row.recurrence=='once' or latest.date==today))
    result['completed_at']=latest.completed_at if latest else None
    result['last_completed_date']=latest.date if latest and row.recurrence!='once' else None
    return jsonable_encoder(result)


async def rows(session,uid,today,notebook_id=None,completed=None,limit=1000):
    query=select(StudyTask).outerjoin(Notebook,(Notebook.id==StudyTask.notebook_id)&(Notebook.user_id==StudyTask.user_id))
    query=query.where(StudyTask.user_id==uid,StudyTask.archived_at.is_(None),or_(StudyTask.notebook_id.is_(None),Notebook.archived_at.is_(None)))
    if notebook_id: query=query.where(StudyTask.notebook_id==notebook_id)
    exists=select(StudyTaskCheck.id).where(StudyTaskCheck.user_id==uid,StudyTaskCheck.task_id==StudyTask.id).exists()
    done=(StudyTask.recurrence=='once')&exists
    if completed is not None: query=query.where(done if completed else ~done)
    tasks=(await session.scalars(query.order_by(StudyTask.created_at,StudyTask.id).limit(limit))).all()
    checks=(await session.scalars(select(StudyTaskCheck).where(StudyTaskCheck.user_id==uid,StudyTaskCheck.task_id.in_([t.id for t in tasks]))
        .distinct(StudyTaskCheck.task_id).order_by(StudyTaskCheck.task_id,StudyTaskCheck.date.desc()))).all()
    latest={c.task_id:c for c in checks}
    return [public(t,latest.get(t.id),today) for t in tasks]


@router.get('')
async def list_tasks(request: Request,notebook_id: UUID | None=None,completed: bool | None=None):
    user=await account(request)
    async with unit_of_work() as session:
        return await rows(session,UUID(user['user_id']),local_today(user['timezone']),notebook_id,completed)


@router.post('')
async def create_task(request: Request,body: TaskBody):
    async def apply(session,user):
        if body.notebook_id: await owned(session,Notebook,user.id,body.notebook_id)
        data=body.model_dump()
        if data['reminder'] and data['reminder'].tzinfo is None: data['reminder']=data['reminder'].replace(tzinfo=ZoneInfo(user.timezone))
        row=StudyTask(user_id=user.id,**data,xp_reward={'low':5,'medium':10,'high':15}[body.priority])
        session.add(row); await session.flush()
        return public(row,None,local_today(user.timezone))
    return await mutate(request,['create-study-task',body.model_dump(mode='json')],apply)


@router.patch('/{task_id}')
async def update_task(request: Request,task_id: UUID,body: UpdateBody):
    async def apply(session,user):
        row=await owned(session,StudyTask,user.id,task_id)
        if row.notebook_id: await owned(session,Notebook,user.id,row.notebook_id)
        data=body.model_dump(exclude_unset=True); desired=data.pop('completed',None)
        if data.get('recurrence') and data['recurrence']!=row.recurrence:
            history=await session.scalar(select(StudyTaskCheck.id).where(StudyTaskCheck.user_id==user.id,StudyTaskCheck.task_id==row.id).limit(1))
            if history:
                raise HTTPException(409,'Crie outra tarefa para mudar a recorrência de uma tarefa com conclusões registradas.')
        for key,value in data.items():
            if value is None and key in ('title','recurrence','priority','estimated_minutes','actual_minutes'):
                raise HTTPException(422,'Campo obrigatório não pode ser nulo.')
            if key=='reminder' and value and value.tzinfo is None: value=value.replace(tzinfo=ZoneInfo(user.timezone))
            setattr(row,key,value)
        today=local_today(user.timezone)
        query=select(StudyTaskCheck).where(StudyTaskCheck.user_id==user.id,StudyTaskCheck.task_id==row.id)
        if row.recurrence!='once': query=query.where(StudyTaskCheck.date==today)
        check=await session.scalar(query.order_by(StudyTaskCheck.date.desc()).limit(1))
        if desired is True and check is None:
            check=StudyTaskCheck(user_id=user.id,task_id=row.id,date=today,completed_at=datetime.now(timezone.utc),xp_earned=row.xp_reward)
            session.add(check); apply_xp(user,row.xp_reward)
        elif desired is False and check:
            apply_xp(user,-check.xp_earned); await session.delete(check); check=None
        await session.flush(); await session.refresh(row)
        latest=await session.scalar(select(StudyTaskCheck).where(StudyTaskCheck.user_id==user.id,StudyTaskCheck.task_id==row.id)
            .order_by(StudyTaskCheck.date.desc()).limit(1))
        return public(row,latest,today)
    return await mutate(request,['update-study-task',str(task_id),body.model_dump(mode='json',exclude_unset=True)],apply)


@router.delete('/{task_id}')
async def delete_task(request: Request,task_id: UUID):
    async def apply(session,user):
        row=await owned(session,StudyTask,user.id,task_id); row.archived_at=datetime.now(timezone.utc)
        return {'message':'Task deleted'}
    return await mutate(request,['delete-study-task',str(task_id)],apply)
