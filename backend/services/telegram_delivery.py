"""Durable command replies; ambiguous external sends require explicit human retry."""
import asyncio
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, or_
from db.session import unit_of_work
from db.models.telegram import TelegramLink, TelegramUpdate
from services.event_queue import utc_now


async def claim_reply(update_id=None):
    from services.telegram import links_lock
    from db.repositories.identity import IdentityRepository
    now=utc_now()
    async with unit_of_work() as session:
        await links_lock(session)
        query=select(TelegramUpdate).where(TelegramUpdate.completed_at.is_not(None),TelegramUpdate.delivered_at.is_(None),TelegramUpdate.next_delivery_at<=now,
            or_((TelegramUpdate.delivery_status=='pending')&((TelegramUpdate.delivery_attempts<5)|
                    ((TelegramUpdate.delivery_error=='manual_retry')&(TelegramUpdate.delivery_attempts<8))),
                (TelegramUpdate.delivery_status=='processing')&(TelegramUpdate.lease_until<=now)))
        if update_id is not None:query=query.where(TelegramUpdate.update_id==update_id)
        row=await session.scalar(query.order_by(TelegramUpdate.next_delivery_at,TelegramUpdate.update_id).limit(1).with_for_update(skip_locked=True))
        if row is None:return None
        if row.delivery_status=='processing':
            row.delivery_status='uncertain';row.delivery_error='worker_interrupted_during_delivery'
            row.delivery_history=[*(row.delivery_history or []),{'at':now.isoformat(),'attempt':row.delivery_attempts,
                'outcome':'uncertain','error':row.delivery_error}][-32:]
            row.lease_token=None;row.lease_until=now;return None
        if row.completed_at<now-timedelta(days=1):
            row.delivery_status='cancelled';row.delivery_error='reply_expired';return None
        if row.binding_id is not None and row.user_id is None:
            row.delivery_status='cancelled';row.delivery_error='owner_deleted';return None
        if row.user_id is None and not (row.reply or '').startswith(('Sirius: /vincular','Vincule sua conta primeiro',
            'Código inválido ou expirado','Usuário não encontrado','Há uma entrega em andamento')):
            row.delivery_status='cancelled';row.delivery_error='anonymous_reply_not_public';return None
        if row.user_id:
            await IdentityRepository(session).by_id(row.user_id,lock=True)
            link=await session.scalar(select(TelegramLink).where(TelegramLink.id==row.binding_id,
                TelegramLink.user_id==row.user_id,TelegramLink.chat_id==row.chat_id))
            if link is None:
                row.delivery_status='cancelled';row.delivery_error='pairing_changed';return None
        row.delivery_status='processing';row.delivery_attempts+=1;row.lease_token=uuid4();row.lease_until=now+timedelta(seconds=60)
        row.delivery_history=[*(row.delivery_history or []),{'at':now.isoformat(),'attempt':row.delivery_attempts,'outcome':'dispatching'}]
        return {'id':row.update_id,'token':row.lease_token,'chat_id':row.chat_id,'reply':row.reply or ''}


async def record_reply(claim,result=None):
    now=utc_now()
    async with unit_of_work() as session:
        row=await session.scalar(select(TelegramUpdate).where(TelegramUpdate.update_id==claim['id'],
            TelegramUpdate.lease_token==claim['token'],TelegramUpdate.delivery_status=='processing').with_for_update())
        if row is None:return False
        body=(result or {}).get('result') or {}
        if result and result.get('ok') is True and type(body.get('message_id')) is int and (body.get('chat') or {}).get('id')==row.chat_id:
            row.delivery_status='delivered';row.delivered_at=now;row.delivery_error=None;row.provider_receipt=str(body['message_id'])
        elif result is None or result.get('ok') is True:
            row.delivery_status='uncertain';row.delivery_error='provider_confirmation_unknown'
        else:
            transient=result.get('error_code') in (429,500,502,503,504)
            row.delivery_status='pending' if transient and row.delivery_attempts<5 else 'failed'
            row.delivery_error='provider_temporarily_unavailable' if transient else 'provider_rejected'
            retry=(result.get('parameters') or {}).get('retry_after')
            seconds=min(3600,max(30,retry)) if type(retry) is int else min(3600,30*2**row.delivery_attempts)
            row.next_delivery_at=now+timedelta(seconds=seconds)
        row.delivery_history=[*(row.delivery_history or []),{'at':now.isoformat(),'attempt':row.delivery_attempts,
            'outcome':row.delivery_status,'error':row.delivery_error,'receipt':row.provider_receipt}]
        row.lease_token=None;row.lease_until=now
        return True


async def deliver_reply(*,update_id=None,sender=None):
    claim=await claim_reply(update_id)
    if claim is None:return False
    if sender is None:
        from server import send_telegram_message
        sender=send_telegram_message
    try:result=await asyncio.wait_for(sender(claim['chat_id'],claim['reply']),timeout=20)
    except Exception:result=None
    await record_reply(claim,result)
    return True
