"""Owned durable in-app presentation attempts, independent from read receipts."""
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, case, or_, and_
from db.session import unit_of_work
from db.models.agent import Event, EventDelivery, Insight
from db.repositories.agent import AgentRepository
from db.repositories.identity import IdentityRepository
from ai.actions import Preferences
from event_contracts import CATALOG, Rule, EventCandidate
from services.event_queue import utc_now, quiet_at, insight_rule

ROUTINE = frozenset(('brief.daily','review.night','coach.weekly'))
ATTEMPT = 'presentation_claimed'
GROUPED = 'presentation_grouped'
RENDERED = 'presented'


def history(row):
    return [entry for entry in row.history or [] if isinstance(entry,dict)]


def presentation_state(row):
    entries=history(row)
    claim=next((e for e in entries if e.get('outcome')==ATTEMPT),None)
    shown=next((e for e in entries if e.get('outcome')==RENDERED),None)
    grouped=next((e for e in entries if e.get('outcome')==GROUPED),None)
    return {'state':'presented' if shown else 'claimed' if claim else 'grouped' if grouped else 'not_presented',
        'attempted_at':claim.get('at') if claim else None,'presented_at':shown.get('at') if shown else None}


def public_history(row):
    return [{k:v for k,v in entry.items() if k!='presentation_key'} for entry in history(row)]


def instant(value):
    try:
        parsed=datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else None
    except (ValueError,TypeError):return None


def preview(item):
    # A short notice, not a full multi-line daily report inside a toast.
    if item.event_type in ROUTINE:return 'Seu resumo está disponível na central de Notificações.'
    return ' '.join(' '.join(item.reasons).split())[:140]


def payload(row,event,item,grouped=0):
    return {'delivery_id':str(row.id),'event_type':event.event_type,'title':CATALOG[event.event_type][1],
        'preview':preview(item),'link':'/notifications','grouped_count':grouped,'presentation':presentation_state(row)}


async def current_candidate(session,uid,user,event,now):
    try:item=EventCandidate.model_validate(event.payload.get('candidate'))
    except (ValueError,TypeError,AttributeError):return None
    if item.event_type!=event.event_type:return None
    if item.event_type in ROUTINE:
        try:origin=date.fromisoformat(item.occurrence)
        except ValueError:return None
        if origin!=now.astimezone(ZoneInfo(user.timezone)).date():return None
    else:
        from services.event_sources import collect
        fresh,_,_=await collect(uid,now=now,target=item,transaction=session)
        if not fresh:return None
        item=fresh[0]
    day=now.astimezone(ZoneInfo(user.timezone)).date()
    feedback=await session.scalar(select(Insight.id).where(Insight.user_id==uid,Insight.rule==insight_rule(item),
        or_(Insight.feedback=='never',and_(Insight.feedback=='snooze',Insight.snoozed_until>now),
            and_(Insight.date==day,Insight.feedback.in_(('dismiss','snooze'))))).limit(1))
    return None if feedback else item


async def claim(user_id,key):
    try:key=str(UUID(key))
    except (ValueError,TypeError,AttributeError):raise HTTPException(422,'Apresentação exige Idempotency-Key UUID.')
    uid=UUID(str(user_id));now=utc_now();cutoff=now-timedelta(days=1)
    async with unit_of_work() as session:
        user=await IdentityRepository(session).by_id(uid,lock=True)
        if user is None:raise HTTPException(401,'Conta indisponível.')
        prefs=Preferences.model_validate(await AgentRepository(session).preferences(uid))
        if not prefs.automations or prefs.daily_cap==0 or quiet_at(now,user,prefs):return {'item':None}
        kinds=[kind for kind in CATALOG if (kind not in ROUTINE or prefs.event_automation.routine_popups)
            and prefs.event_automation.rules.get(kind,Rule()).enabled
            and 'in_app' in prefs.event_automation.rules.get(kind,Rule()).channels]
        if not kinds:return {'item':None}
        eligible=(EventDelivery.user_id==uid,EventDelivery.channel=='in_app',EventDelivery.status=='available',
            EventDelivery.created_at>=cutoff,EventDelivery.available_at<=now,Event.event_type.in_(kinds),
            or_(Event.event_type.not_in(ROUTINE),Event.payload['candidate']['occurrence'].astext==now.astimezone(ZoneInfo(user.timezone)).date().isoformat()))
        joined=select(EventDelivery,Event).join(Event,(Event.user_id==EventDelivery.user_id)&(Event.id==EventDelivery.event_id))
        # Recover a lost response briefly, but never replay a rendered/obsolete popup.
        prior=(await session.execute(joined.where(*eligible,EventDelivery.history.contains([
            {'outcome':ATTEMPT,'presentation_key':key}])).limit(1))).first()
        if prior:
            row,event=prior;meta=next(e for e in history(row) if e.get('presentation_key')==key)
            at=instant(meta.get('at'))
            if presentation_state(row)['state']!='claimed' or at is None or now-at>timedelta(seconds=30):return {'item':None}
            item=await current_candidate(session,uid,user,event,now)
            return {'item':payload(row,event,item,meta.get('grouped_count',0)) if item else None, 'replayed':True}
        recent=(await session.scalars(select(EventDelivery.history).where(EventDelivery.user_id==uid,
            EventDelivery.channel=='in_app',EventDelivery.created_at>=cutoff,
            EventDelivery.history.contains([{'outcome':ATTEMPT}])).limit(100))).all()
        if any((at:=instant(e.get('at'))) and now-at<timedelta(seconds=60)
            for entries in recent for e in entries if isinstance(e,dict) and e.get('outcome')==ATTEMPT):return {'item':None}
        priority=case({kind:{'high':3,'medium':2,'low':1}[prefs.event_automation.rules.get(kind,Rule()).priority] for kind in kinds},value=Event.event_type,else_=0)
        rows=(await session.execute(joined.where(*eligible,
            ~EventDelivery.history.contains([{'outcome':ATTEMPT}]),~EventDelivery.history.contains([{'outcome':GROUPED}]))
            .order_by(priority.desc(),Event.created_at.desc(),Event.id.desc()).limit(20).with_for_update(of=EventDelivery))).all()
        selected=None;remaining=[]
        for row,event in rows:
            item=await current_candidate(session,uid,user,event,now)
            if item is None:continue
            if selected is None:
                selected=(row,event,item)
            else:remaining.append(row)
        if selected is None:return {'item':None}
        row,event,item=selected
        row.history=[*history(row),{'at':now.isoformat(),'outcome':ATTEMPT,'presentation_key':key,'grouped_count':len(remaining)}]
        for other in remaining:
            other.history=[*history(other),{'at':now.isoformat(),'outcome':GROUPED,'presentation_key':key}]
        return {'item':payload(row,event,item,len(remaining))}


async def acknowledge(user_id,identity,key):
    uid=UUID(str(user_id));key=str(key)
    async with unit_of_work() as session:
        # Same owner -> delivery lock order as read/dismiss and claims.
        user=await IdentityRepository(session).by_id(uid,lock=True)
        row=await session.scalar(select(EventDelivery).where(EventDelivery.user_id==uid,EventDelivery.id==identity).with_for_update())
        if user is None or row is None:raise HTTPException(404,'Entrega não encontrada.')
        entries=history(row)
        if row.channel!='in_app' or not any(e.get('outcome')==ATTEMPT and e.get('presentation_key')==key for e in entries):
            raise HTTPException(409,'Apresentação não reservada por esta tentativa.')
        if not any(e.get('outcome')==RENDERED for e in entries):
            row.history=[*entries,{'at':utc_now().isoformat(),'outcome':RENDERED,'presentation_key':key}]
        return presentation_state(row)
