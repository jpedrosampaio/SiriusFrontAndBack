"""Transactional outbox, persisted retry deadlines and bounded worker claims."""
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select, update, func, or_, case
from sqlalchemy.dialects.postgresql import insert
from db.models.agent import Event, EventDelivery, Insight, Preferences as StoredPreferences
from db.models.telegram import TelegramLink
from db.models.identity import User
from db.repositories.identity import IdentityRepository
from db.repositories.agent import AgentRepository
from db.session import unit_of_work
from ai.actions import Preferences
from event_contracts import EventCandidate, CATALOG, Rule, TRANSITIONS


def utc_now():return datetime.now(timezone.utc)


def quiet_at(instant, user, prefs):
    local=instant.astimezone(ZoneInfo(user.timezone)); policy=prefs.event_automation
    start=policy.quiet_start or f'{prefs.quiet_start:02}:00'
    end=policy.quiet_end or f'{prefs.quiet_end:02}:00'
    value=local.strftime('%H:%M')
    return start<=value<end if start<end else value>=start or value<end if start!=end else False


def next_allowed(instant, user, prefs):
    # Walk actual UTC instants: nonexistent/repeated civil hours do not fabricate a deadline.
    value=instant
    for _ in range(2881):
        if not quiet_at(value,user,prefs):return value
        value+=timedelta(minutes=1)
    raise ValueError('Quiet-hours bound exceeded')


def period_key(day, frequency):
    return str(day-timedelta(days=day.weekday())) if frequency=='weekly' else str(day)


async def enqueue(session, uid, item, day, frequency='daily', priority='medium'):
    occurrence=period_key(day,frequency) if item.entity_type in ('routine','nutrition') else item.occurrence
    period=period_key(day,frequency)
    if item.event_type in TRANSITIONS:occurrence=period='once'
    digest=hashlib.sha256(f'{uid}:{item.event_type}:{item.entity_type}:{item.entity_id}:{occurrence}:{period}'.encode()).hexdigest()
    await session.execute(insert(Event).values(user_id=uid,event_type=item.event_type,entity_type=item.entity_type,
        entity_id=item.entity_id,dedup_key=digest,payload={'schema':'domain-event/2','candidate':item.model_dump(mode='json'),
            'period':period,'observed_date':str(day),'priority':priority})
        .on_conflict_do_nothing(index_elements=['user_id','dedup_key']))


async def ensure_scan(session, uid, *, restart=False):
    values={'user_id':uid,'event_type':'system.scan','dedup_key':'event-engine-scan/2','payload':{'cursors':{}},'available_at':utc_now()}
    statement=insert(Event).values(**values)
    if restart:
        statement=statement.on_conflict_do_update(index_elements=['user_id','dedup_key'],set_={
            'status':'pending','attempts':0,'available_at':utc_now(),'lease_token':None,'lease_until':None})
    else:statement=statement.on_conflict_do_nothing(index_elements=['user_id','dedup_key'])
    await session.execute(statement)


async def bootstrap():
    """Opted-in historical accounts acquire a persisted scan; no process-local cursor."""
    async with unit_of_work() as session:
        present=select(Event.id).where(Event.user_id==StoredPreferences.user_id,Event.dedup_key=='event-engine-scan/2').exists()
        owners=(await session.scalars(select(StoredPreferences.user_id).where(
            StoredPreferences.settings['automations'].as_boolean().is_(True),~present).order_by(StoredPreferences.user_id).limit(10))).all()
        for uid in owners:await ensure_scan(session,uid)
        return len(owners)


async def claim(user_id=None, *, now=None):
    instant=now or utc_now()
    async with unit_of_work() as session:
        expired=select(Event.id).where(Event.status=='processing',Event.lease_until<=instant,Event.attempts>=5).limit(40).with_for_update(skip_locked=True)
        await session.execute(update(Event).where(Event.id.in_(expired)).values(status='failed',
            last_error='worker_attempts_exhausted',lease_token=None,lease_until=None))
        query=select(Event).where(Event.available_at<=instant,Event.attempts<5,
            or_(Event.status=='pending',(Event.status=='processing')&(Event.lease_until<=instant)))
        if user_id is not None:query=query.where(Event.user_id==UUID(str(user_id)))
        priority=case((Event.event_type=='system.scan',0),(Event.payload['priority'].astext=='high',1),
            (Event.payload['priority'].astext=='low',3),else_=2)
        row=await session.scalar(query.order_by(priority,Event.available_at,Event.created_at,Event.id).limit(1).with_for_update(skip_locked=True))
        if row is None:return None
        row.status='processing';row.attempts+=1;row.lease_token=uuid4();row.lease_until=instant+timedelta(minutes=3)
        return {'event_id':str(row.id),'user_id':str(row.user_id),'type':row.event_type,'lease_token':str(row.lease_token),
            'payload':row.payload,'entity_type':row.entity_type,'entity_id':str(row.entity_id) if row.entity_id else None}


def leased(event, instant):
    return (Event.user_id==UUID(event['user_id']),Event.id==UUID(event['event_id']),Event.status=='processing',
        Event.lease_token==UUID(event['lease_token']),Event.lease_until>instant)


async def finish(event, *, delay=None, payload=None, error=None):
    instant=utc_now()
    async with unit_of_work() as session:
        row=await session.scalar(select(Event).where(*leased(event,instant)).with_for_update())
        if row is None:return False
        if error:
            row.last_error=error
            row.status='failed' if row.attempts>=5 else 'pending'
            row.available_at=instant+timedelta(seconds=min(3600,30*2**row.attempts))
        elif delay is not None:
            row.status='pending';row.available_at=instant+delay;row.attempts=0
        else:row.status='processed';row.processed_at=instant
        if payload is not None:row.payload=payload
        row.lease_token=None;row.lease_until=None
        return True


async def defer(event, instant):
    return await finish(event,delay=max(timedelta(seconds=30),instant-utc_now()))


async def publish(event, item, *, dry_run):
    """Validate the current source under the owner lock before producing any alert."""
    from services.event_sources import collect
    instant=utc_now();uid=UUID(event['user_id'])
    async with unit_of_work() as session:
        user=await IdentityRepository(session).by_id(uid,lock=True)
        row=await session.scalar(select(Event).where(*leased(event,instant)).with_for_update())
        if user is None or row is None:return 'lost',None
        prefs=Preferences.model_validate(await AgentRepository(session).preferences(uid))
        rule=prefs.event_automation.rules.get(item.event_type,Rule())
        if not prefs.automations or not rule.enabled:return 'cancelled',None
        if prefs.daily_cap==0:return 'cancelled',None
        if quiet_at(instant,user,prefs):return 'defer',next_allowed(instant,user,prefs)
        local=instant.astimezone(ZoneInfo(user.timezone));day=local.date()
        if item.event_type in ('brief.daily','review.night','coach.weekly'):
            from services.event_reports import briefing
            mode={'brief.daily':'morning','review.night':'night','coach.weekly':'weekly'}[item.event_type]
            origin=datetime.fromisoformat(item.occurrence).date()
            if not day-timedelta(days=1)<=origin<=day:return 'resolved',None
            report=await briefing(uid,mode=mode,day=origin,now=instant,transaction=session)
            item=item.model_copy(update={'facts':report.model_dump(mode='json')})
        else:
            fresh,_,_=await collect(uid,now=instant,target=item,transaction=session)
            if not fresh:return 'resolved',None
            item=fresh[0]
        # Historical generic budget insights and typed events share a single cooldown.
        source_key=f'{item.event_type}:{item.entity_type}:{item.entity_id}:{item.occurrence}'
        rule_id='budget:'+item.facts['category'] if item.event_type.startswith('budget.') else 'event:'+hashlib.sha256(source_key.encode()).hexdigest()
        previous=await session.scalar(select(Insight).where(Insight.user_id==uid,Insight.rule==rule_id,Insight.date==day))
        blocked=await session.scalar(select(Insight.id).where(Insight.user_id==uid,Insight.rule==rule_id,
            (Insight.feedback=='never')|((Insight.feedback=='snooze')&(Insight.snoozed_until>instant))).limit(1))
        if blocked or (previous and previous.feedback in ('dismiss','never','snooze')):return 'cancelled',None
        if previous and previous.evidence.get('event_id')!=str(row.id):return 'duplicate',None
        count=await session.scalar(select(func.count()).select_from(Insight).where(Insight.user_id==uid,Insight.date==day))
        if previous is None and count>=prefs.daily_cap:
            tomorrow=datetime.combine(day+timedelta(days=1),datetime.min.time(),ZoneInfo(user.timezone)).astimezone(timezone.utc)
            return 'defer',next_allowed(tomorrow,user,prefs)
        _,title,link=CATALOG[item.event_type]
        if previous is None:
            previous=Insight(user_id=uid,rule=rule_id,title=title,evidence={**item.facts,'event_id':str(row.id),
                'reasons':item.reasons,'source_type':item.entity_type,'source_id':str(item.entity_id) if item.entity_id else None},
                link=link,date=day,dry_run=dry_run)
            session.add(previous);await session.flush()
        # Replaying a source cannot create a second channel delivery.
        row.payload={**row.payload,'candidate':item.model_dump(mode='json'),'insight_id':str(previous.id),'priority':rule.priority}
        pairing=await session.scalar(select(TelegramLink).where(TelegramLink.user_id==uid))
        for channel in rule.channels:
            values={'user_id':uid,'event_id':row.id,'channel':channel}
            if channel=='in_app':values['status']='available'
            elif dry_run:values.update(status='cancelled',last_error='simulation_only')
            elif pairing is None:values.update(status='failed',last_error='not_paired')
            else:values.update(recipient_link_id=pairing.id,recipient_chat_id=pairing.chat_id)
            await session.execute(insert(EventDelivery).values(**values).on_conflict_do_nothing(index_elements=['user_id','event_id','channel']))
        return 'published',None
