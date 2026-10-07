"""User-serialized activities: domain writes, XP and receipt commit atomically."""
import hashlib
import json
from sqlalchemy import select
from fastapi import HTTPException
from db.models.identity import ActivityReceipt
from db.models.agent import Event
from db.repositories.identity import IdentityRepository
from db.session import unit_of_work


async def run_activity(user_id, request_key, fingerprint, apply):
    if request_key is not None and (not 8 <= len(request_key) <= 128 or not all(
            c.isascii() and (c.isalnum() or c in '-_') for c in request_key)):
        raise HTTPException(422, 'Invalid Idempotency-Key')
    digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    async with unit_of_work() as session:
        user = await IdentityRepository(session).by_id(user_id, lock=True)
        if user is None:
            raise HTTPException(404, 'User not found')
        if request_key is not None:
            previous = await session.scalar(select(ActivityReceipt).where(
                ActivityReceipt.user_id == user_id, ActivityReceipt.request_key == request_key))
            if previous:
                if previous.fingerprint != digest:
                    raise HTTPException(409, 'Idempotency-Key already used for another action')
                return {**previous.result, 'replayed': True}
        result = await apply(session, user)
        event_type = {'task':'task.completed', 'complete_session':'workout.completed', 'focus':'study.session.completed'}.get(
            fingerprint[0] if fingerprint else None)
        if event_type and result.get('xp_earned', 0) > 0:
            session.add(Event(user_id=user.id, event_type=event_type, payload={'result':result}))
        if request_key is not None:
            session.add(ActivityReceipt(user_id=user_id, request_key=request_key, fingerprint=digest, result=result))
        await session.flush()
        return result
