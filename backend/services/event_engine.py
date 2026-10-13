"""Durable scanning shares the existing outbox; canonical records remain the source of truth."""
from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy import select
from db.session import unit_of_work
from db.models.agent import Event
from db.repositories.identity import IdentityRepository
from db.repositories.agent import AgentRepository
from ai.actions import Preferences
from event_contracts import EventCandidate, Rule
from services import event_queue as queue


async def scan(event):
    from services.event_sources import collect, candidate
    uid=UUID(event['user_id']);instant=queue.utc_now()
    items,cursors,warnings=await collect(uid,now=instant,cursors=event['payload'].get('cursors',{}))
    async with unit_of_work() as session:
        user=await IdentityRepository(session).by_id(uid,lock=True)
        row=await session.scalar(select(Event).where(*queue.leased(event,queue.utc_now())).with_for_update())
        if user is None or row is None:return False
        prefs=Preferences.model_validate(await AgentRepository(session).preferences(uid))
        if not prefs.automations:
            row.status='processed';row.processed_at=instant;row.lease_token=None;row.lease_until=None
            return True
        local=instant.astimezone(ZoneInfo(user.timezone));day=local.date();policy=prefs.event_automation
        for kind,scheduled in [('brief.daily',policy.morning_time),('review.night',policy.night_time),('coach.weekly',policy.weekly_time)]:
            if local.strftime('%H:%M')>=scheduled and (kind!='coach.weekly' or local.weekday()==policy.weekly_weekday):
                items.append(candidate(kind,'routine',day,{},'Resumo determinístico dos registros próprios; propostas exigem confirmação.'))
        enabled=[item for item in items if policy.rules.get(item.event_type,Rule()).enabled]
        enabled.sort(key=lambda item:({'high':0,'medium':1,'low':2}[policy.rules.get(item.event_type,Rule()).priority],item.event_type,str(item.entity_id),item.occurrence))
        for item in enabled:
            rule=policy.rules.get(item.event_type,Rule())
            await queue.enqueue(session,uid,item,day,rule.frequency,rule.priority)
        row.payload={'cursors':cursors,'last_scan':instant.isoformat(),'limitations':warnings,'observed_candidates':len(items)}
        row.status='pending';row.attempts=0;row.last_error=None
        row.available_at=instant+timedelta(minutes=15);row.lease_token=None;row.lease_until=None
        return True


async def process(event, *, dry_run):
    if event['type']=='system.scan':return await scan(event)
    item=EventCandidate.model_validate(event['payload']['candidate'])
    outcome,deadline=await queue.publish(event,item,dry_run=dry_run)
    if deadline:return await queue.defer(event,deadline)
    return await queue.finish(event,payload=None if outcome=='published' else {**event['payload'],'outcome':outcome})


async def tick(automations, *, sender=None, user_id=None, bootstrap=True):
    if bootstrap:await queue.bootstrap()
    processed=0
    # Reserve capacity in both directions; due scans must not starve their alerts.
    for scans_only in (True,False,False,False):
        event=await queue.claim(user_id,scans_only=scans_only)
        if not event:event=await queue.claim(user_id,scans_only=not scans_only)
        if not event:break
        try:
            if event['type']=='system.scan' or event['payload'].get('schema')=='domain-event/2':
                await process(event,dry_run=automations.settings.dry_run)
            else:
                await automations.process(event);await queue.finish(event)
        except Exception:
            await queue.finish(event,error='processing_failed')
        processed+=1
    from services.event_delivery import deliver_one
    for _ in range(2):
        try:
            if not await deliver_one(user_id=user_id,sender=sender):break
            processed+=1
        except Exception:
            import logging
            logging.warning('automation delivery deferred; persisted lease retained')
            break
    return processed
