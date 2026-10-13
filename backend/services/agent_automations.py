"""SQL suggestion queue, leases, opt-in policy and per-user daily limits."""
import hashlib
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func, update, or_
from sqlalchemy.dialects.postgresql import insert
from ai.actions import Preferences
from db.models.agent import Event, Insight
from db.models.identity import User
from db.repositories.identity import IdentityRepository
from db.repositories.agent import AgentRepository
from db.session import unit_of_work


def identity(value):
    try:return UUID(str(value))
    except (ValueError, TypeError, AttributeError):raise HTTPException(404,'Sugestão não encontrada.') from None


def public(row):
    return jsonable_encoder({'insight_id':row.id,'user_id':row.user_id,'rule':row.rule,'title':row.title,'evidence':row.evidence,
        'link':row.link,'date':row.date,'created_at':row.created_at,'feedback':row.feedback,'snoozed_until':row.snoozed_until,'dry_run':row.dry_run})


async def emit(user_id,event,source,version='1',session=None):
    uid=identity(user_id)
    digest=hashlib.sha256(f'{uid}:{event}:{source}:{version}'.encode()).hexdigest()
    async def write(transaction):
        await transaction.execute(insert(Event).values(user_id=uid,event_type=event,dedup_key=digest,payload={'source':str(source),'version':str(version)})
            .on_conflict_do_nothing(index_elements=['user_id','dedup_key']))
    if session is not None:await write(session)
    else:
        async with unit_of_work() as transaction:await write(transaction)


async def claim(user_id=None):
    from services.event_queue import claim as durable_claim
    return await durable_claim(user_id)


async def finish(event):
    from services.event_queue import finish as durable_finish
    return await durable_finish(event)


async def local_now(user_id):
    async with unit_of_work() as session:
        user=await session.get(User,identity(user_id))
        if user is None:return None
        return datetime.now(ZoneInfo(user.timezone))


async def suggest(user_id,rule,title,evidence,link,now,dry_run):
    from ai.automations import quiet
    uid=identity(user_id)
    async with unit_of_work() as session:
        user=await IdentityRepository(session).by_id(uid,lock=True)
        if user is None:return None
        local=now.astimezone(ZoneInfo(user.timezone))
        prefs=Preferences.model_validate(await AgentRepository(session).preferences(uid))
        if not prefs.automations or quiet(local,prefs.quiet_start,prefs.quiet_end):return None
        blocked=await session.scalar(select(Insight.id).where(Insight.user_id==uid,Insight.rule==rule,Insight.feedback=='never').limit(1))
        if blocked:return None
        day=local.date()
        previous=await session.scalar(select(Insight.id).where(Insight.user_id==uid,Insight.rule==rule,Insight.date==day))
        if previous:return None
        count=await session.scalar(select(func.count()).select_from(Insight).where(Insight.user_id==uid,Insight.date==day))
        if count>=prefs.daily_cap:return None
        row=Insight(user_id=uid,rule=rule,title=title,evidence=jsonable_encoder(evidence),link=link,date=day,dry_run=dry_run)
        session.add(row);await session.flush()
        return public(row)


async def list_insights(user_id):
    uid=identity(user_id)
    async with unit_of_work() as session:
        await session.execute(update(Insight).where(Insight.user_id==uid,Insight.feedback=='snooze',
            Insight.snoozed_until<=datetime.now(timezone.utc)).values(feedback=None,snoozed_until=None))
        rows=(await session.scalars(select(Insight).where(Insight.user_id==uid,Insight.feedback.is_(None))
            .order_by(Insight.date.desc(),Insight.created_at.desc(),Insight.id).limit(10))).all()
        return [public(row) for row in rows]


async def feedback(user_id,insight_id,value):
    uid,sid=identity(user_id),identity(insight_id)
    async with unit_of_work() as session:
        await IdentityRepository(session).by_id(uid,lock=True)
        row=await session.scalar(select(Insight).where(Insight.user_id==uid,Insight.id==sid))
        if row is None:raise HTTPException(404,'Sugestão não encontrada.')
        row.feedback=value
        row.snoozed_until=datetime.now(timezone.utc)+timedelta(days=1) if value=='snooze' else None
        return {'feedback':value,**({'snoozed_until':row.snoozed_until.isoformat()} if row.snoozed_until else {})}
