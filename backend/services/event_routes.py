"""Owned automation configuration, channel receipts and read-only integrated reports."""
import os
from datetime import date, timedelta
from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from db.session import unit_of_work
from db.activity import run_activity
from db.models.agent import Event, EventDelivery, Preferences as StoredPreferences
from db.models.telegram import TelegramLink, TelegramUpdate
from db.models.identity import User
from db.repositories.agent import AgentRepository
from services.auth_routes import account
from services.event_queue import ensure_scan, utc_now, quiet_at
from event_contracts import CATALOG, Rule, PolicyUpdate
from ai.actions import Preferences
from ai.config import Settings

router=APIRouter(prefix='/automations')
reports=APIRouter(prefix='/dashboard')


async def state(uid):
    async with unit_of_work() as session:
        prefs=Preferences.model_validate(await AgentRepository(session).preferences(uid))
        user=await session.get(User,uid)
        link=await session.scalar(select(TelegramLink.id).where(TelegramLink.user_id==uid))
        scan=await session.scalar(select(Event).where(Event.user_id==uid,Event.dedup_key=='event-engine-scan/2'))
        settings=Settings()
        return {'user_id':str(uid),'enabled':prefs.automations,'daily_cap':prefs.daily_cap,'policy':prefs.event_automation.model_dump(mode='json'),
            'timezone':user.timezone,'inherited_quiet_start':f'{prefs.quiet_start:02}:00','inherited_quiet_end':f'{prefs.quiet_end:02}:00',
            'runtime_enabled':settings.automations,'simulation_only':settings.dry_run,
            'channels':{'in_app':True,'telegram':bool(link and os.getenv('TELEGRAM_BOT_TOKEN') and not settings.dry_run)},
            'telegram_paired':bool(link),'scan':None if scan is None else {'status':scan.status,'attempts':scan.attempts,
                'next_at':scan.available_at.isoformat(),'last_scan':scan.payload.get('last_scan'),'limitations':scan.payload.get('limitations',[]),
                'last_error':scan.last_error},
            'catalog':[{'event_type':kind,'domain':info[0],'title':info[1],'link':info[2],
                'rule':prefs.event_automation.rules.get(kind,Rule()).model_dump()} for kind,info in CATALOG.items()],
            'method':'Regras determinísticas; registros dos módulos são a fonte. Nenhum plano é alterado automaticamente.'}


@router.get('/state')
async def get_state(request:Request):
    auth=await account(request);return await state(UUID(auth['user_id']))


@router.put('/policy')
async def save_policy(request:Request,body:PolicyUpdate):
    auth=await account(request)
    if not request.headers.get('Idempotency-Key'):raise HTTPException(400,'Configuração exige chave de idempotência.')
    async def apply(session,user):
        prefs=Preferences.model_validate(await AgentRepository(session).preferences(user.id))
        prefs.automations=body.enabled;prefs.daily_cap=body.daily_cap
        policy=body.policy
        if 'routine_popups' not in policy.model_fields_set:
            policy=policy.model_copy(update={'routine_popups':prefs.event_automation.routine_popups})
        prefs.event_automation=policy
        settings=prefs.model_dump(mode='json')
        await session.execute(insert(StoredPreferences).values(user_id=user.id,settings=settings).on_conflict_do_update(
            index_elements=['user_id'],set_={'settings':settings}))
        if body.enabled:await ensure_scan(session,user.id,restart=True)
        return {'enabled':body.enabled,'daily_cap':body.daily_cap,'policy':policy.model_dump(mode='json')}
    intent=body.model_dump(mode='json')
    # Preserve recovery of pre-upgrade receipts; omission and explicit opt-out differ.
    if 'routine_popups' not in body.policy.model_fields_set:intent['policy'].pop('routine_popups')
    return await run_activity(UUID(auth['user_id']),request.headers.get('Idempotency-Key'),['automation_policy',intent],apply)


def public_delivery(row):
    from services.notification_presentations import presentation_state,public_history
    return {'delivery_id':str(row.id),'channel':row.channel,'status':row.status,'attempts':row.attempts,
        'available_at':row.available_at.isoformat(),'delivered_at':row.delivered_at.isoformat() if row.delivered_at else None,
        'provider_receipt':row.provider_receipt,'last_error':row.last_error,'history':public_history(row),'presentation':presentation_state(row),
        'retry_allowed':row.channel=='telegram' and row.status in ('failed','uncertain') and row.attempts<8}


def event_message(row):
    from event_contracts import EventCandidate
    from services.event_delivery import message_for
    try:return message_for(EventCandidate.model_validate(row.payload.get('candidate')))
    except (ValueError,TypeError,AttributeError,KeyError,IndexError):
        # Queued/cancelled routines can legitimately have no materialized
        # briefing. Preserve that historical record, without inventing a report
        # or letting one incomplete candidate break the whole history page.
        return None


@router.get('/events')
async def events(request:Request,before:UUID|None=None,limit:int=20):
    if not 1<=limit<=50:raise HTTPException(422,'Limite de 1 a 50.')
    auth=await account(request);uid=UUID(auth['user_id'])
    async with unit_of_work() as session:
        query=select(Event).where(Event.user_id==uid,Event.event_type!='system.scan')
        if before:
            pivot=await session.scalar(select(Event).where(Event.id==before,Event.user_id==uid))
            if pivot is None:raise HTTPException(404,'Evento não encontrado.')
            query=query.where((Event.created_at<pivot.created_at)|((Event.created_at==pivot.created_at)&(Event.id<pivot.id)))
        rows=list((await session.scalars(query.order_by(Event.created_at.desc(),Event.id.desc()).limit(limit+1))).all())
        deliveries=(await session.scalars(select(EventDelivery).where(EventDelivery.user_id==uid,
            EventDelivery.event_id.in_([r.id for r in rows[:limit]])))).all()
        return {'items':[{'event_id':str(row.id),'event_type':row.event_type,'title':CATALOG.get(row.event_type,('','Evento histórico',''))[1],
            'status':row.status,'attempts':row.attempts,'created_at':row.created_at.isoformat(),
            'available_at':row.available_at.isoformat(),'last_error':row.last_error,'outcome':row.payload.get('outcome'),
                'candidate':row.payload.get('candidate'),'message':event_message(row),'deliveries':[public_delivery(d) for d in deliveries if d.event_id==row.id]}
            for row in rows[:limit]],'next_cursor':str(rows[limit-1].id) if len(rows)>limit else None}


@router.get('/inbox')
async def inbox(request:Request):
    auth=await account(request);uid=UUID(auth['user_id'])
    async with unit_of_work() as session:
        prefs=Preferences.model_validate(await AgentRepository(session).preferences(uid));user=await session.get(User,uid)
        if not prefs.automations or quiet_at(utc_now(),user,prefs):return []
        rows=(await session.execute(select(EventDelivery,Event).join(Event,(Event.id==EventDelivery.event_id)&
            (Event.user_id==EventDelivery.user_id)).where(EventDelivery.user_id==uid,EventDelivery.channel=='in_app',
                EventDelivery.status=='available',Event.event_type.in_([kind for kind in CATALOG
                    if prefs.event_automation.rules.get(kind,Rule()).enabled and 'in_app' in prefs.event_automation.rules.get(kind,Rule()).channels]))
            .order_by(EventDelivery.created_at,EventDelivery.id).limit(10))).all()
        from services.event_delivery import message_for
        from event_contracts import EventCandidate
        result=[]
        for delivery,event in rows:
            rule=prefs.event_automation.rules.get(event.event_type,Rule())
            if not rule.enabled or 'in_app' not in rule.channels:continue
            item=EventCandidate.model_validate(event.payload['candidate'])
            result.append({'delivery_id':str(delivery.id),'event_id':str(event.id),'title':CATALOG[event.event_type][1],
                'message':message_for(item),'link':CATALOG[event.event_type][2],'observed_at':event.created_at.isoformat(),
                'reasons':item.reasons,'priority':rule.priority,'status':'available'})
        return result


class Receipt(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['read','dismiss','retry']
    accept_duplicate_risk:bool=Field(default=False,strict=True)


class PresentationReceipt(BaseModel):
    model_config=ConfigDict(extra='forbid')
    key:UUID


@router.post('/presentations/claim')
async def claim_presentation(request:Request):
    auth=await account(request)
    from services.notification_presentations import claim
    return {'user_id':auth['user_id'],**await claim(auth['user_id'],request.headers.get('Idempotency-Key'))}


@router.post('/presentations/{identity}')
async def confirm_presentation(request:Request,identity:UUID,body:PresentationReceipt):
    auth=await account(request)
    from services.notification_presentations import acknowledge
    return await acknowledge(auth['user_id'],identity,body.key)


def public_reply(row):
    return {'kind':'command_reply','delivery_id':str(row.update_id),'channel':'telegram','status':row.delivery_status,
        'reply':row.reply,'completed_at':row.completed_at.isoformat(),'attempts':row.delivery_attempts,
        'available_at':row.next_delivery_at.isoformat(),'provider_receipt':row.provider_receipt,
        'last_error':row.delivery_error,'history':row.delivery_history,
        'retry_allowed':row.delivery_status in ('failed','uncertain') and row.delivery_attempts<8
            and row.completed_at>=utc_now()-timedelta(days=1)}


@router.get('/telegram-replies')
async def replies(request:Request,before:int|None=None,limit:int=20):
    if not 1<=limit<=50:raise HTTPException(422,'Limite de 1 a 50.')
    if before is not None and not -(2**63)<=before<2**63:raise HTTPException(422,'Cursor inválido.')
    auth=await account(request);uid=UUID(auth['user_id'])
    async with unit_of_work() as session:
        query=select(TelegramUpdate).where(TelegramUpdate.user_id==uid,TelegramUpdate.completed_at.is_not(None))
        if before is not None:
            pivot=await session.scalar(query.where(TelegramUpdate.update_id==before))
            if pivot is None:raise HTTPException(404,'Resposta não encontrada.')
            query=query.where((TelegramUpdate.completed_at<pivot.completed_at)|
                ((TelegramUpdate.completed_at==pivot.completed_at)&(TelegramUpdate.update_id<pivot.update_id)))
        rows=list((await session.scalars(query.order_by(TelegramUpdate.completed_at.desc(),TelegramUpdate.update_id.desc()).limit(limit+1))).all())
        return {'items':[public_reply(row) for row in rows[:limit]],
            'next_cursor':str(rows[limit-1].update_id) if len(rows)>limit else None}


@router.post('/telegram-replies/{identity}')
async def retry_reply(request:Request,identity:int,body:Receipt):
    if not -(2**63)<=identity<2**63:raise HTTPException(422,'Resposta inválida.')
    auth=await account(request)
    if not request.headers.get('Idempotency-Key'):raise HTTPException(400,'Ação exige chave de idempotência.')
    if body.action!='retry' or not body.accept_duplicate_risk:raise HTTPException(409,'Confirme o risco de duplicação antes de reenviar.')
    async def apply(session,user):
        row=await session.scalar(select(TelegramUpdate).where(TelegramUpdate.user_id==user.id,
            TelegramUpdate.update_id==identity).with_for_update())
        if row is None or row.completed_at is None:raise HTTPException(404,'Resposta não encontrada.')
        if not public_reply(row)['retry_allowed']:raise HTTPException(409,'Reenvio indisponível.')
        link=await session.scalar(select(TelegramLink).where(TelegramLink.id==row.binding_id,
            TelegramLink.user_id==user.id,TelegramLink.chat_id==row.chat_id))
        if link is None:raise HTTPException(409,'Vínculo alterado; a resposta não será enviada.')
        row.delivery_status='pending';row.next_delivery_at=utc_now();row.delivery_error='manual_retry'
        row.lease_token=None;row.lease_until=utc_now()
        row.delivery_history=[*(row.delivery_history or []),{'at':utc_now().isoformat(),
            'attempt':row.delivery_attempts,'outcome':'manual_retry'}][-32:]
        return public_reply(row)
    # Match transport/binding lock order before run_activity serializes the owner.
    from services.telegram import links_lock
    async with unit_of_work() as session:
        await links_lock(session)
        return await run_activity(UUID(auth['user_id']),request.headers.get('Idempotency-Key'),
            ['telegram_reply_retry',str(identity),body.model_dump()],apply,session=session)


@router.post('/deliveries/{identity}')
async def receipt(request:Request,identity:UUID,body:Receipt):
    if body.action not in ('read','dismiss','retry'):raise HTTPException(422,'Ação desconhecida.')
    auth=await account(request)
    if not request.headers.get('Idempotency-Key'):raise HTTPException(400,'Ação exige chave de idempotência.')
    async def apply(session,user):
        row=await session.scalar(select(EventDelivery).where(EventDelivery.user_id==user.id,EventDelivery.id==identity).with_for_update())
        if row is None:raise HTTPException(404,'Entrega não encontrada.')
        if body.action=='retry':
            if not body.accept_duplicate_risk:raise HTTPException(409,'Confirme o risco de duplicação antes de reenviar.')
            if row.channel!='telegram' or row.status not in ('failed','uncertain') or row.attempts>=8:raise HTTPException(409,'Reenvio indisponível.')
            row.status='pending';row.available_at=utc_now();row.last_error='manual_retry';row.lease_token=None;row.lease_until=None
            row.history=[*(row.history or []),{'at':utc_now().isoformat(),'outcome':'manual_retry','attempt':row.attempts}][-32:]
        elif row.channel!='in_app':raise HTTPException(409,'Recibos do Telegram dependem do provedor.')
        elif row.status=='available':
            row.status='delivered' if body.action=='read' else 'cancelled'
            row.delivered_at=utc_now() if body.action=='read' else None
            row.provider_receipt='owner_read' if body.action=='read' else None
            row.history=[*(row.history or []),{'at':utc_now().isoformat(),'outcome':row.status,'receipt':row.provider_receipt}][-32:]
        return public_delivery(row)
    return await run_activity(UUID(auth['user_id']),request.headers.get('Idempotency-Key'),
        ['automation_receipt',str(identity),body.model_dump()],apply)


@reports.get('/daily-briefing')
async def report(request:Request,mode:str='morning',day:date|None=None):
    auth=await account(request)
    from services.event_reports import briefing
    return (await briefing(auth['user_id'],mode=mode,day=day)).model_dump(mode='json')
