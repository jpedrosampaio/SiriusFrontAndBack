"""Owned native API reservations. Acceptance is not evidence of reading."""
from datetime import date, datetime
from uuid import UUID, uuid4
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from sqlalchemy import select, exists, and_, cast, String, Integer
from db.models.identity import ActivityReceipt
from db.models.notifications import NotificationDelivery
from db.activity import activity_digest


class NativeClaim(BaseModel):
    notification_id: UUID
    claim_id: UUID
    occurrence: date


class NativeOutcome(BaseModel):
    claims: list[NativeClaim] = Field(min_length=1, max_length=50)
    outcome: Literal['accepted', 'failed', 'uncertain']


class NativeRetry(BaseModel):
    occurrence: date
    attempted_at: datetime
    duplicate_risk_accepted: bool = False


def key(nid, occurrence):
    return f'native_notice_{nid.hex}_{occurrence.isoformat()}'


def unavailable(occurrence):
    """Filter durable reservations before the scheduler's bounded LIMIT."""
    from db.models.notifications import Notification
    result = ActivityReceipt.result
    return exists(select(ActivityReceipt.id).where(ActivityReceipt.user_id == Notification.user_id,
        result['kind'].astext == 'native_notice', result['notification_id'].astext == cast(Notification.id, String),
        result['occurrence'].astext == cast(occurrence, String),
        ~and_(result['state'].astext == 'failed', cast(result['cycle_attempts'].astext, Integer) < 3)))


async def receipt(session, uid, nid, occurrence):
    return await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id == uid,
        ActivityReceipt.request_key == key(nid, occurrence)))


def public(result):
    return {k: result.get(k) for k in ('state', 'occurrence', 'attempted_at', 'confirmed_at', 'attempts')}


def reserve_result(nid, occurrence, now, previous=None, manual=False):
    previous = previous or {}
    return {**previous, 'kind': 'native_notice', 'notification_id': str(nid), 'occurrence': occurrence.isoformat(),
        'state': 'reserved', 'claim_id': str(uuid4()), 'attempted_at': now.isoformat(), 'confirmed_at': None,
        'attempts': previous.get('attempts', 0) + 1,
        'cycle_attempts': 1 if manual else previous.get('cycle_attempts', 0) + 1,
        'history': [*previous.get('history', []), {'state': 'reserved', 'at': now.isoformat(), 'manual': manual}]}


def claim(result):
    return {k: result[k] for k in ('notification_id', 'claim_id', 'occurrence')}


async def reserve(session, row, occurrence, now):
    slot = await receipt(session, row.user_id, row.id, occurrence)
    if slot and (slot.result['state'] != 'failed' or slot.result['cycle_attempts'] >= 3):
        return None
    result = reserve_result(row.id, occurrence, now, slot.result if slot else None)
    if slot:
        slot.result = result
    else:
        session.add(ActivityReceipt(user_id=row.user_id, request_key=key(row.id, occurrence),
            fingerprint=activity_digest(['native_notice', str(row.id), occurrence.isoformat()]), result=result))
    return claim(result)


async def finish(session, row, body, outcome, now):
    slot = await receipt(session, row.user_id, row.id, body.occurrence)
    if slot is None or slot.result.get('claim_id') != str(body.claim_id):
        raise HTTPException(409, 'Tentativa nativa desatualizada')
    result = slot.result
    if result['state'] != 'reserved':
        if result['state'] != outcome: raise HTTPException(409, 'Resultado nativo já confirmado')
        return public(result)
    if outcome == 'accepted':
        # Do not regress a newer occurrence when an older ACK arrives late.
        row.last_sent = max(row.last_sent or now, now)
        row.last_occurrence = max(row.last_occurrence or body.occurrence, body.occurrence)
        log = await session.scalar(select(NotificationDelivery).where(NotificationDelivery.user_id == row.user_id,
            NotificationDelivery.notification_id == row.id, NotificationDelivery.occurrence == body.occurrence,
            NotificationDelivery.channel == 'browser'))
        if log is None:
            session.add(NotificationDelivery(user_id=row.user_id, notification_id=row.id, occurrence=body.occurrence,
                sent_at=now, channel='browser'))
    slot.result = {**result, 'state': outcome, 'confirmed_at': now.isoformat() if outcome == 'accepted' else None,
        'history': [*result['history'], {'state': outcome, 'at': now.isoformat()}]}
    return public(slot.result)


async def latest(session, uid):
    # One latest receipt per reminder, selected in SQL; no claim tokens exposed.
    result = ActivityReceipt.result
    notification_id = result['notification_id'].astext
    rows = (await session.scalars(select(ActivityReceipt).where(ActivityReceipt.user_id == uid,
        result['kind'].astext == 'native_notice').distinct(notification_id)
        .order_by(notification_id, result['occurrence'].astext.desc()))).all()
    return {row.result['notification_id']: public(row.result) for row in rows}
