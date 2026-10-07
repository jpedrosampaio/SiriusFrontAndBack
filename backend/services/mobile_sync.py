"""Explicit typed native sync for four domains; never arbitrary table/document access."""
import hashlib
import json
from datetime import date,datetime,timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field,ValidationError,field_validator
from sqlalchemy import select,delete
from sqlalchemy.exc import IntegrityError
from db.activity import run_activity
from db.session import unit_of_work
from db.models.planning import Task,TaskInstance,Habit,HabitCheck,Goal,GoalCheck
from db.models.finance import FinancialTransaction
from services.auth_routes import account
from services.planning import apply_xp
from services.planning_routes import habit_json
from services.goals_routes import public as goal_json
from services.finance import public as finance_json
from services.finance_routes import DecimalRoute,TransactionBody
from services.time import local_today

router=APIRouter(prefix='/sync',route_class=DecimalRoute)


class SyncPayload(BaseModel):
    model_config=ConfigDict(extra='forbid')
    record_id: UUID
    operation: Literal['INSERT','UPDATE','DELETE']
    data: dict
    timestamp: datetime


class Metadata(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    synced_at: datetime | None = None


class TaskInput(Metadata):
    task_id: UUID | None = None
    title: str = Field(min_length=1,max_length=200)
    description: str | None = Field(default=None,max_length=4000)
    date: date
    priority: Literal['low','medium','high'] = 'medium'
    recurrence: Literal['once','daily','weekly','monthly'] = 'once'
    completed: bool = False
    status: Literal['todo','in_progress','done'] | None = None
    xp_reward: int = 10 # Server-derived, accepted only for compatibility.
    is_template: bool = True
    instance_id: UUID | None = None


class HabitInput(Metadata):
    habit_id: UUID | None = None
    name: str = Field(min_length=1,max_length=200)
    description: str | None = Field(default=None,max_length=4000)
    color: str = Field(default='#007AFF',pattern=r'^#[0-9a-fA-F]{6}$')
    completions: list[date] = Field(default_factory=list,max_length=10000)
    streak: int = 0
    best_streak: int = 0

    @field_validator('completions',mode='before')
    @classmethod
    def array(cls,value):return json.loads(value) if isinstance(value,str) else value


class GoalInput(Metadata):
    goal_id: UUID | None = None
    title: str = Field(min_length=1,max_length=200)
    description: str | None = Field(default=None,max_length=4000)
    target_date: date
    progress: float = Field(default=0,ge=0,le=100,allow_inf_nan=False)
    sprint_duration: int = Field(default=60,ge=1,le=3650)
    daily_checks: list[date] = Field(default_factory=list,max_length=10000)
    sprints: list = Field(default_factory=list,max_length=0)

    @field_validator('daily_checks','sprints',mode='before')
    @classmethod
    def array(cls,value):return json.loads(value) if isinstance(value,str) else value


class TransactionInput(Metadata,TransactionBody):
    transaction_id: UUID | None = None


def config(kind):
    mapping={'tasks':(Task,TaskInput,'task_id'),'habits':(Habit,HabitInput,'habit_id'),
        'goals':(Goal,GoalInput,'goal_id'),'transactions':(FinancialTransaction,TransactionInput,'transaction_id')}
    if kind not in mapping:raise HTTPException(403,'Table is not available for sync')
    return mapping[kind]


async def public(session,row,kind,user):
    if kind=='tasks':
        instance=await session.scalar(select(TaskInstance).where(TaskInstance.user_id==user.id,TaskInstance.task_id==row.id,TaskInstance.date==row.date))
        return {'task_id':str(row.id),'user_id':str(row.user_id),'title':row.title,'description':row.description,
            'date':row.date.isoformat(),'priority':row.priority,'recurrence':row.recurrence,'xp_reward':row.xp_reward,
            'is_template':True,'completed':bool(instance and instance.completed),'status':instance.status if instance else 'todo','created_at':row.created_at.isoformat()}
    if kind=='habits':
        dates=(await session.scalars(select(HabitCheck.date).where(HabitCheck.user_id==user.id,HabitCheck.habit_id==row.id).order_by(HabitCheck.date))).all()
        return habit_json(row,dates,local_today(user.timezone))
    if kind=='goals':
        dates=(await session.scalars(select(GoalCheck.date).where(GoalCheck.user_id==user.id,GoalCheck.goal_id==row.id).order_by(GoalCheck.date))).all()
        return goal_json(row,dates)
    value=finance_json(row)
    return {key:value[key] for key in ('transaction_id','user_id','type','amount','category','description','date','created_at')}


async def replace_checks(session,user,model,parent_key,parent_id,dates,reward):
    old=(await session.scalars(select(model).where(model.user_id==user.id,getattr(model,parent_key)==parent_id))).all()
    existing={r.date for r in old};wanted=set(dates)
    for row in old:
        if row.date not in wanted:await session.delete(row)
    for day in wanted-existing:
        values={'user_id':user.id,parent_key:parent_id,'date':day}
        if model is HabitCheck:values['checked_at']=datetime.now(timezone.utc)
        session.add(model(**values))
    apply_xp(user,(len(wanted-existing)-len(existing-wanted))*reward)


@router.post('/{table_name}')
async def sync(request:Request,table_name:str,body:SyncPayload):
    auth=await account(request);uid=UUID(auth['user_id']);model,schema,id_key=config(table_name);data=body.data
    if data.get('user_id',str(uid))!=str(uid):raise HTTPException(403,'Not authorized')
    if data.get(id_key,str(body.record_id))!=str(body.record_id):raise HTTPException(422,'Record identifier does not match')
    if set(data)-set(schema.model_fields):raise HTTPException(422,'Unsupported sync fields')
    fingerprint=['sync',table_name,body.model_dump(mode='json')]
    key=request.headers.get('Idempotency-Key') or 'sync_'+hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()
    async def apply(session,user):
        row=await session.scalar(select(model).where(model.user_id==uid,model.id==body.record_id))
        if row is not None and getattr(row,'archived_at',None) is not None:
            if body.operation=='DELETE':return {'success':True}
            raise HTTPException(409,'Record is archived')
        if body.operation=='DELETE':
            if row is not None:
                if isinstance(row,FinancialTransaction):
                    if row.bill_id or row.purchase_id:raise HTTPException(409,'Manage linked transactions in Finance')
                    await session.delete(row)
                else:row.archived_at=datetime.now(timezone.utc)
            return {'success':True}
        if row is None:
            if body.operation=='UPDATE':raise HTTPException(404,'Record not found')
            if await session.get(model,body.record_id):raise HTTPException(409,'Record identifier unavailable')
        previous=await public(session,row,table_name,user) if row else {}
        try:parsed=schema.model_validate({**previous,**data})
        except (ValidationError,ValueError,TypeError):raise HTTPException(422,'Invalid sync record') from None
        if table_name=='tasks' and 'status' in data and parsed.status is None:raise HTTPException(422,'Invalid task status')
        if row is None:
            row=model(id=body.record_id,user_id=uid);session.add(row)
        if table_name=='tasks':
            for field in ('title','description','date','priority','recurrence'):setattr(row,field,getattr(parsed,field))
            if row.xp_reward is None:row.xp_reward={'low':5,'medium':10,'high':15}[parsed.priority]
            await session.flush()
            instance=await session.scalar(select(TaskInstance).where(TaskInstance.user_id==uid,TaskInstance.task_id==row.id,TaskInstance.date==row.date))
            was=bool(instance and instance.completed)
            status=parsed.status if 'status' in data else 'done' if parsed.completed else 'todo'
            target=status=='done'
            if instance is None:instance=TaskInstance(user_id=uid,task_id=row.id,date=row.date);session.add(instance)
            instance.completed=target;instance.status=status;instance.completed_at=datetime.now(timezone.utc) if target else None
            apply_xp(user,(int(target)-int(was))*row.xp_reward)
        elif table_name=='habits':
            for field in ('name','description','color'):setattr(row,field,getattr(parsed,field))
            await session.flush();await replace_checks(session,user,HabitCheck,'habit_id',row.id,parsed.completions,8)
        elif table_name=='goals':
            for field in ('title','description','target_date','progress','sprint_duration'):setattr(row,field,getattr(parsed,field))
            await session.flush();await replace_checks(session,user,GoalCheck,'goal_id',row.id,parsed.daily_checks,5)
        else:
            if row.bill_id or row.purchase_id:raise HTTPException(409,'Manage linked transactions in Finance')
            for field in ('type','amount','category','description','date'):setattr(row,field,getattr(parsed,field))
        await session.flush()
        return {'success':True,'record_id':str(row.id)}
    try:return await run_activity(uid,key,fingerprint,apply)
    except IntegrityError:raise HTTPException(409,'Sync conflict') from None


@router.get('/{table_name}/{user_id}')
async def pull(request:Request,table_name:str,user_id:str):
    auth=await account(request);model,_,_=config(table_name)
    if auth['user_id']!=user_id:raise HTTPException(403,'Not authorized')
    from db.models.identity import User
    async with unit_of_work() as session:
        user=await session.get(User,UUID(user_id));query=select(model).where(model.user_id==user.id)
        if model is not FinancialTransaction:query=query.where(model.archived_at.is_(None))
        rows=(await session.scalars(query.order_by(model.created_at,model.id))).all()
        result=[]
        for row in rows:
            value=await public(session,row,table_name,user);value.update(updated_at=row.updated_at.isoformat(),synced_at=row.updated_at.isoformat());result.append(value)
        return result
