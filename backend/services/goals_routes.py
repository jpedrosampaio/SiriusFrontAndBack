from datetime import date as Date, datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from db.activity import run_activity
from db.session import unit_of_work
from db.models.planning import Goal, GoalCheck
from services.auth_routes import account
from services.planning import apply_xp

router = APIRouter()


class GoalBody(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    description: str | None = Field(default=None,max_length=4000)
    target_date: Date
    sprint_duration: int = Field(default=60,ge=1,le=3650)


def public(row,checks=()):
    return {'goal_id':str(row.id),'user_id':str(row.user_id),'title':row.title,'description':row.description,
        'target_date':row.target_date.isoformat(),'progress':row.progress,'sprint_duration':row.sprint_duration,
        'daily_checks':[day.isoformat() for day in checks],'sprints':[],'created_at':row.created_at.isoformat()}


async def owned(session,user_id,goal_id):
    row=await session.scalar(select(Goal).where(Goal.user_id==user_id,Goal.id==goal_id,Goal.archived_at.is_(None)))
    if row is None: raise HTTPException(404,'Goal not found')
    return row


async def mutate(request,fingerprint,apply):
    user=await account(request)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),fingerprint,apply)


@router.get('/goals')
async def goals(request: Request):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        rows=(await session.scalars(select(Goal).where(Goal.user_id==uid,Goal.archived_at.is_(None)).order_by(Goal.created_at,Goal.id))).all()
        checks=(await session.execute(select(GoalCheck.goal_id,GoalCheck.date).join(Goal,
            (Goal.id==GoalCheck.goal_id)&(Goal.user_id==GoalCheck.user_id)).where(GoalCheck.user_id==uid,Goal.archived_at.is_(None))
            .order_by(GoalCheck.date))).all()
        dates={}
        for goal_id,day in checks: dates.setdefault(goal_id,[]).append(day)
        return [public(row,dates.get(row.id,[])) for row in rows]


@router.post('/goals')
async def create(request: Request,body: GoalBody):
    async def apply(session,user):
        row=Goal(user_id=user.id,**body.model_dump()); session.add(row); await session.flush()
        return public(row)
    return await mutate(request,['goal_create',body.model_dump(mode='json')],apply)


@router.patch('/goals/{goal_id}')
async def update(request: Request,goal_id: UUID,progress: float = Query(ge=0,le=100,allow_inf_nan=False)):
    async def apply(session,user):
        row=await owned(session,user.id,goal_id); row.progress=progress
        return {'message':'Goal updated'}
    return await mutate(request,['goal_update',str(goal_id),progress],apply)


@router.delete('/goals/{goal_id}')
async def delete(request: Request,goal_id: UUID):
    async def apply(session,user):
        row=await owned(session,user.id,goal_id); row.archived_at=datetime.now(timezone.utc)
        return {'message':'Goal deleted'}
    return await mutate(request,['goal_delete',str(goal_id)],apply)


@router.post('/goals/{goal_id}/check')
async def check(request: Request,goal_id: UUID,date: Date,completed: bool | None = None):
    async def apply(session,user):
        await owned(session,user.id,goal_id)
        row=await session.scalar(select(GoalCheck).where(GoalCheck.user_id==user.id,GoalCheck.goal_id==goal_id,GoalCheck.date==date))
        target=not bool(row) if completed is None else completed
        delta=(int(target)-int(row is not None))*5
        if target and row is None: session.add(GoalCheck(user_id=user.id,goal_id=goal_id,date=date))
        elif not target and row is not None: await session.delete(row)
        apply_xp(user,delta)
        return {'message':'Day checked' if target else 'Day unchecked','completed':target,'xp_earned':delta,'new_xp':user.xp}
    return await mutate(request,['goal_check',str(goal_id),date.isoformat(),completed],apply)
