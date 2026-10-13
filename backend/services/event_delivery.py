"""Claim -> revalidate -> send -> receipt. Ambiguous transport outcomes never auto-retry."""
from datetime import timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select, or_
from db.session import unit_of_work
from db.models.agent import Event, EventDelivery
from db.models.telegram import TelegramLink, TelegramUpdate
from db.repositories.identity import IdentityRepository
from db.repositories.agent import AgentRepository
from ai.actions import Preferences
from event_contracts import EventCandidate, Rule, CATALOG
from services.event_queue import utc_now, quiet_at, next_allowed


async def pairing_busy(session, *, uid=None, chat_id=None):
    now=utc_now()
    delivery=select(EventDelivery.id).where(EventDelivery.status=='processing',EventDelivery.lease_until>now)
    commands=select(TelegramUpdate.update_id).where(TelegramUpdate.completed_at.is_not(None),TelegramUpdate.delivered_at.is_(None),
        TelegramUpdate.lease_token.is_not(None),TelegramUpdate.lease_until>now)
    if uid is not None:
        delivery=delivery.where(EventDelivery.user_id==uid);commands=commands.where(TelegramUpdate.user_id==uid)
    if chat_id is not None:
        delivery=delivery.where(EventDelivery.recipient_chat_id==chat_id);commands=commands.where(TelegramUpdate.chat_id==chat_id)
    return bool(await session.scalar(delivery.limit(1)) or await session.scalar(commands.limit(1)))


def message_for(item):
    title=CATALOG[item.event_type][1]
    lines=[title,*item.reasons]
    facts=item.facts
    if item.event_type in ('brief.daily','review.night','coach.weekly'):
        from services.event_reports import render_text
        return render_text(facts)[:3900]
    # Explicit allowlist: provider payloads and unbounded source documents never leave the app.
    for key,label in [('title','Item'),('date','Data'),('due_date','Vencimento'),('exam_date','Prova'),
        ('days_remaining','Dias restantes'),('recorded_minutes','Minutos registrados'),('category','Categoria'),
        ('spent','Despesa registrada'),('limit','Limite'),('amount','Valor'),('question_count','Questões distintas'),
        ('remaining','Diferença para metas confirmadas')]:
        if key in facts:lines.append(f'{label}: {str(facts[key])[:700]}')
    lines.append('Consulte o Sirius para revisar os dados. Nenhum plano ou compromisso foi alterado.')
    return '\n'.join(lines)[:3900]


async def claim_delivery(*, user_id=None):
    now=utc_now()
    async with unit_of_work() as session:
        query=select(EventDelivery).where(EventDelivery.channel=='telegram',EventDelivery.available_at<=now,
            or_((EventDelivery.status=='pending')&((EventDelivery.attempts<5)|((EventDelivery.last_error=='manual_retry')&(EventDelivery.attempts<8))),
                (EventDelivery.status=='processing')&(EventDelivery.lease_until<=now)))
        if user_id is not None:query=query.where(EventDelivery.user_id==UUID(str(user_id)))
        row=await session.scalar(query.order_by(EventDelivery.available_at,EventDelivery.created_at,EventDelivery.id).limit(1).with_for_update(skip_locked=True))
        if row is None:return None
        # Never resend after a worker died in the external-call window.
        if row.status=='processing' and row.history and row.history[-1].get('outcome')=='dispatching':
            row.status='uncertain';row.last_error='worker_interrupted_during_delivery';row.lease_token=None;row.lease_until=None
            row.history=[*(row.history or []),{'at':now.isoformat(),'outcome':'uncertain'}][-32:]
            return None
        row.status='processing';row.lease_token=uuid4();row.lease_until=now+timedelta(seconds=60)
        return {'id':str(row.id),'owner':str(row.user_id),'event_id':str(row.event_id),'token':str(row.lease_token)}


async def prepare(claim):
    from services.telegram import links_lock
    from services.event_sources import collect
    now=utc_now();uid=UUID(claim['owner'])
    async with unit_of_work() as session:
        # Binding edits and preparation use the same brief lock; remote IO runs after commit.
        await links_lock(session)
        user=await IdentityRepository(session).by_id(uid,lock=True)
        row=await session.scalar(select(EventDelivery).where(EventDelivery.id==UUID(claim['id']),EventDelivery.user_id==uid,
            EventDelivery.lease_token==UUID(claim['token']),EventDelivery.status=='processing',EventDelivery.lease_until>now).with_for_update())
        if row is None or user is None:return None
        event=await session.scalar(select(Event).where(Event.id==row.event_id,Event.user_id==uid))
        prefs=Preferences.model_validate(await AgentRepository(session).preferences(uid))
        item=EventCandidate.model_validate(event.payload['candidate'])
        rule=prefs.event_automation.rules.get(item.event_type,Rule())
        from ai.config import Settings
        runtime=Settings()
        if runtime.dry_run or not runtime.automations:
            row.status='cancelled';row.last_error='simulation_only' if runtime.dry_run else 'worker_disabled'
            row.lease_token=None;row.lease_until=None;return None
        if not prefs.automations or prefs.daily_cap==0 or not rule.enabled or 'telegram' not in rule.channels:
            row.status='cancelled';row.last_error='disabled_by_owner';row.lease_token=None;row.lease_until=None;return None
        if quiet_at(now,user,prefs):
            row.status='pending';row.available_at=next_allowed(now,user,prefs);row.lease_token=None;row.lease_until=None;return None
        link=await session.scalar(select(TelegramLink).where(TelegramLink.user_id==uid,TelegramLink.id==row.recipient_link_id,
            TelegramLink.chat_id==row.recipient_chat_id))
        if link is None:
            row.status='cancelled';row.last_error='pairing_changed';row.lease_token=None;row.lease_until=None;return None
        if item.event_type not in ('brief.daily','review.night','coach.weekly'):
            fresh,_,_=await collect(uid,now=now,target=item,transaction=session)
            if not fresh:
                row.status='cancelled';row.last_error='source_resolved';row.lease_token=None;row.lease_until=None;return None
            item=fresh[0]
        else:
            from services.event_reports import briefing
            from datetime import date
            mode={'brief.daily':'morning','review.night':'night','coach.weekly':'weekly'}[item.event_type]
            origin=date.fromisoformat(item.occurrence)
            local_day=now.astimezone(ZoneInfo(user.timezone)).date()
            if not local_day-timedelta(days=1)<=origin<=local_day:
                row.status='cancelled';row.last_error='report_expired';row.lease_token=None;row.lease_until=None;return None
            item=item.model_copy(update={'facts':(await briefing(uid,mode=mode,day=origin,now=now,transaction=session)).model_dump(mode='json')})
        row.attempts+=1
        row.history=[*(row.history or []),{'at':now.isoformat(),'attempt':row.attempts,'outcome':'dispatching'}][-32:]
        return link.chat_id,message_for(item)


async def record_result(claim, *, result=None, ambiguous=False):
    now=utc_now();uid=UUID(claim['owner'])
    async with unit_of_work() as session:
        row=await session.scalar(select(EventDelivery).where(EventDelivery.id==UUID(claim['id']),EventDelivery.user_id==uid,
            EventDelivery.status=='processing',EventDelivery.lease_token==UUID(claim['token'])).with_for_update())
        if row is None:return False
        body=(result or {}).get('result') or {}
        if result and result.get('ok') is True and type(body.get('message_id')) is int and (body.get('chat') or {}).get('id')==row.recipient_chat_id:
            row.status='delivered';row.delivered_at=now;row.provider_receipt=str(body['message_id']);row.last_error=None
        elif ambiguous or result is None or (result.get('ok') is True):
            row.status='uncertain';row.last_error='provider_confirmation_unknown'
        else:
            code=result.get('error_code')
            row.last_error='provider_rejected' if code not in (429,500,502,503,504) else 'provider_temporarily_unavailable'
            row.status='pending' if code in (429,500,502,503,504) and row.attempts<5 else 'failed'
            retry=(result.get('parameters') or {}).get('retry_after')
            seconds=min(3600,max(30,int(retry))) if type(retry) is int else min(3600,30*2**row.attempts)
            row.available_at=now+timedelta(seconds=seconds)
        row.history=[*(row.history or []),{'at':now.isoformat(),'attempt':row.attempts,'outcome':row.status,
            'error':row.last_error,'receipt':row.provider_receipt}][-32:]
        row.lease_token=None;row.lease_until=None
        return True


async def deliver_one(*, user_id=None, sender=None):
    claim=await claim_delivery(user_id=user_id)
    if claim is None:return False
    prepared=await prepare(claim)
    if prepared is None:return True
    if sender is None:
        from server import send_telegram_message
        sender=send_telegram_message
    try:
        import asyncio
        result=await asyncio.wait_for(sender(*prepared),timeout=20)
    except Exception:
        await record_result(claim,ambiguous=True)
    else:await record_result(claim,result=result)
    return True
