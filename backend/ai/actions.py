"""User-confirmed immutable proposals and atomic, idempotent execution."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Literal
from pydantic import Field
from fastapi import HTTPException
from ai.types import StrictModel
from ai.registry import TOOLS, validate_call


class Preferences(StrictModel):
    profile: Literal['conservative', 'balanced', 'proactive'] = 'balanced'
    automations: bool = False
    quiet_start: int = Field(default=22, ge=0, le=23)
    quiet_end: int = Field(default=8, ge=0, le=23)
    daily_cap: int = Field(default=3, ge=0, le=10)
    blocked_tools: list[str] = Field(default_factory=list, max_length=30)


def autonomy(tool, prefs):
    if tool.name in prefs.blocked_tools: return 'BLOCKED'
    if tool.permission == 'read': return 'READ_ONLY'
    if prefs.profile == 'conservative': return 'PROPOSE_ONLY'
    # Proactivity is permission to suggest, never permission to spend or mutate.
    return 'CONFIRM_REQUIRED'


class Actions:
    def __init__(self, db, writer, transact):
        self.db, self.writer, self.transact = db, writer, transact

    async def preferences(self, user_id):
        row = await self.db.ai_preferences.find_one({'user_id': user_id}, {'_id': 0, 'settings': 1})
        return Preferences.model_validate((row or {}).get('settings', {}))

    async def propose(self, user_id, request_id, index, name, arguments, reason, evidence=None):
        tool = TOOLS.get(name)
        if not tool or tool.permission != 'write': raise HTTPException(422, 'Ação inválida.')
        arguments = validate_call(name, arguments)
        level = autonomy(tool, await self.preferences(user_id))
        if level == 'BLOCKED': raise HTTPException(403, 'Esta ferramenta está bloqueada nas preferências.')
        digest = hashlib.sha256(json.dumps([user_id, request_id, index, name, arguments], sort_keys=True).encode()).hexdigest()
        now = datetime.now(timezone.utc)
        row = {'action_id': digest, 'user_id': user_id, 'tool': name, 'version': tool.version, 'arguments': arguments,
               'summary': tool.description, 'reason': str(reason)[:500], 'evidence': (evidence or [])[:5], 'autonomy': level,
               'status': 'pending', 'created_at': now.isoformat(), 'expires_at': (now+timedelta(minutes=20)).isoformat()}
        await self.db.ai_actions.update_one({'_id': digest, 'user_id': user_id}, {'$setOnInsert': row}, upsert=True)
        return await self.db.ai_actions.find_one({'_id': digest, 'user_id': user_id}, {'_id': 0})

    async def cancel(self, user_id, action_id):
        result = await self.db.ai_actions.update_one({'_id': action_id, 'user_id': user_id, 'status': 'pending'}, {'$set': {'status': 'cancelled'}})
        if not result.matched_count: raise HTTPException(409, 'Proposta indisponível ou já processada.')
        return {'action_id': action_id, 'status': 'cancelled'}

    async def confirm(self, user_id, action_id):
        own = {'_id': action_id, 'user_id': user_id}
        initial = await self.db.ai_actions.find_one(own)
        if not initial: raise HTTPException(404, 'Proposta não encontrada.')
        if initial['status'] == 'executed': return {'action_id': action_id, 'status': 'executed', 'result': initial.get('result'), 'replayed': True}
        now = datetime.now(timezone.utc).isoformat()
        if initial['expires_at'] <= now:
            await self.db.ai_actions.update_one({**own, 'status': 'pending'}, {'$set': {'status': 'expired'}})
            raise HTTPException(409, 'Proposta expirada. Solicite uma nova proposta.')

        async def apply(session, balance):
            row = await self.db.ai_actions.find_one(own, session=session)
            if not row or row['status'] != 'pending' or row['expires_at'] <= datetime.now(timezone.utc).isoformat():
                raise HTTPException(409, 'Proposta indisponível ou expirada.')
            tool = TOOLS.get(row['tool'])
            if not tool or row['version'] != tool.version: raise HTTPException(409, 'Ferramenta atualizada. Solicite uma nova proposta.')
            # Recheck preferences inside the transaction (policy can change after preview).
            pref = await self.db.ai_preferences.find_one({'user_id': user_id}, session=session) or {}
            if autonomy(tool, Preferences.model_validate(pref.get('settings', {}))) == 'BLOCKED': raise HTTPException(403, 'Ferramenta bloqueada.')
            args = validate_call(row['tool'], row['arguments'])
            await self.db.ai_actions.update_one(own, {'$set': {'status': 'confirmed', 'confirmed_at': now}}, session=session)
            result = await self.writer.execute(row['tool'], user_id, args, session)
            await self.db.ai_actions.update_one(own, {'$set': {'status': 'executed', 'executed_at': now, 'result': result}}, session=session)
            await self.db.ai_audit.insert_one({'user_id': user_id, 'action_id': action_id, 'tool': row['tool'], 'version': row['version'], 'status': 'executed', 'created_at': now}, session=session)
            return {'action_id': action_id, 'status': 'executed', 'result': result}

        return await self.transact(user_id, 'agent_' + action_id, ['agent', action_id], apply)
