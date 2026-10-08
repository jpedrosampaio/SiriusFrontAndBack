"""Normalized conversation history with short SQL leases around remote AI work."""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update, delete
from db.models.agent import Conversation, Message, ConversationReceipt
from db.repositories.identity import IdentityRepository
from db.session import unit_of_work
from assistant_service import compact_history


def key(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value):
        raise HTTPException(422, 'Conversa inválida.')
    return value


def public_message(row, metadata=True):
    return {'message_id':str(row.id), 'role':row.role, 'content':row.content, 'created_at':row.created_at.isoformat(),
        **(row.context if metadata else {})}


async def owned(session, uid, cid, lock=False):
    statement = select(Conversation).where(Conversation.user_id==uid, Conversation.external_id==key(cid))
    return await session.scalar(statement.with_for_update() if lock else statement)


async def recent(session, row):
    return list((await session.scalars(select(Message).where(Message.user_id==row.user_id,
        Message.conversation_id==row.id, Message.sequence>=row.context_from).order_by(Message.sequence))).all())


class Conversations:
    def __init__(self, llm=None):
        self.llm = llm

    async def list(self, user_id):
        async with unit_of_work() as session:
            rows = (await session.scalars(select(Conversation).where(Conversation.user_id==UUID(str(user_id)))
                .order_by(Conversation.updated_at.desc(), Conversation.id).limit(30))).all()
            return [{'conversation_id':row.external_id,'title':row.title,'created_at':row.created_at.isoformat(),
                'updated_at':row.updated_at.isoformat()} for row in rows]

    async def read(self, user_id, conversation_id='primary'):
        async with unit_of_work() as session:
            row = await owned(session, UUID(str(user_id)), conversation_id)
            messages = [public_message(message) for message in await recent(session, row)] if row else []
            has_summary = bool(row and row.summary)
        action_ids = [a['action_id'] for m in messages for a in m.get('actions', [])]
        if action_ids:
            from services.agent_actions import Actions
            live = {a['action_id']:a for a in await Actions().by_ids(user_id, action_ids)}
            for message in messages:
                if 'actions' in message:
                    message['actions'] = [live[a['action_id']] for a in message['actions'] if a['action_id'] in live]
        return {'conversation_id':conversation_id, 'messages':messages, 'has_summary':has_summary}

    async def history(self, user_id, conversation_id='primary', offset=0):
        if not 0 <= offset <= 200: raise HTTPException(422, 'Página inválida.')
        async with unit_of_work() as session:
            row = await owned(session, UUID(str(user_id)), conversation_id)
            if row is None: return {'messages':[], 'next_offset':None, 'retention_messages':200}
            rows = list((await session.scalars(select(Message).where(Message.user_id==row.user_id, Message.conversation_id==row.id)
                .order_by(Message.sequence.desc()).offset(offset).limit(31))).all())
            return {'messages':[public_message(m, False) for m in reversed(rows[:30])],
                'next_offset':offset+30 if len(rows)>30 else None, 'retention_messages':200}

    async def archive(self, user_id, before=None):
        stamp = None
        if before:
            try:
                stamp = datetime.fromisoformat(before.replace('Z','+00:00'))
                if stamp.tzinfo is None: raise ValueError()
            except (ValueError, AttributeError): raise HTTPException(422, 'Cursor inválido.') from None
        async with unit_of_work() as session:
            row = await owned(session, UUID(str(user_id)), 'primary')
            if row is None: return {'messages':[], 'next_cursor':None}
            statement = select(Message).where(Message.user_id==row.user_id, Message.conversation_id==row.id)
            if stamp: statement = statement.where(Message.created_at<stamp)
            rows = (await session.scalars(statement.order_by(Message.sequence.desc()).limit(51))).all()
            return {'messages':[public_message(m, False) for m in rows[:50]],
                'next_cursor':rows[49].created_at.isoformat() if len(rows)>50 else None}

    async def send(self, user_id, body, system, fingerprint_context=None):
        uid, cid = UUID(str(user_id)), key(body.conversation_id)
        digest_input = body.message if fingerprint_context is None else json.dumps([fingerprint_context,body.message],sort_keys=True)
        digest = hashlib.sha256(digest_input.encode()).hexdigest()
        token, now = uuid4(), datetime.now(timezone.utc)
        async with unit_of_work() as session:
            # Serializes first creation only while preparing; never held during provider work.
            user = await IdentityRepository(session).by_id(uid, lock=True)
            if user is None: raise HTTPException(404, 'User not found')
            row = await owned(session, uid, cid, lock=True)
            if row is None:
                row = Conversation(user_id=uid, external_id=cid, primary=cid=='primary', title=body.message[:80])
                session.add(row); await session.flush()
            receipt = await session.scalar(select(ConversationReceipt).where(ConversationReceipt.user_id==uid,
                ConversationReceipt.conversation_id==row.id, ConversationReceipt.request_id==body.request_id))
            if receipt:
                if receipt.message_hash != digest:
                    raise HTTPException(409, 'Esta identificação já foi usada para outra mensagem.')
                return receipt.result
            if row.lease_until and row.lease_until>now:
                raise HTTPException(409, 'Uma resposta ainda está sendo gerada. Aguarde antes de reenviar.')
            row.lease_token, row.lease_until = token, now+timedelta(seconds=600)
            conversation_id, sequence = row.id, row.last_sequence
            messages = [public_message(message) for message in await recent(session, row)]
            messages, summary = compact_history(messages, row.summary or '')
        try:
            prompt = json.dumps({'summary_extracts':summary, 'history':[{'role':m['role'],'content':m['content']} for m in messages],
                'current_message':body.message}, ensure_ascii=False)
            reply = await self.llm(prompt, user_id=user_id, system_message=system)
            metadata = {}
            if isinstance(reply, dict):
                metadata = jsonable_encoder({k:v for k,v in reply.items() if k in ('actions','facts','citations','model','degraded','retrieval_method','tutor')})
                reply = reply['reply']
            if not isinstance(reply, str): raise HTTPException(502, 'Resposta inválida do assistente.')
            if reply.startswith('⚠️'): raise HTTPException(503, reply)
            stamp = datetime.now(timezone.utc)
            user_message = Message(id=uuid4(), user_id=uid, conversation_id=conversation_id, sequence=sequence+1,
                role='user', content=body.message, created_at=stamp, context={'request_id': body.request_id})
            ai_message = Message(id=uuid4(), user_id=uid, conversation_id=conversation_id, sequence=sequence+2,
                role='assistant', content=reply[:16000], created_at=stamp+timedelta(microseconds=1), context=metadata)
            user_public, ai_public = public_message(user_message), public_message(ai_message)
            kept, summary = compact_history([*messages,user_public,ai_public], summary)
            result = {'conversation_id':cid, 'reply':ai_public['content'], 'user_message':user_public, 'ai_message':ai_public}
            async with unit_of_work() as session:
                row = await owned(session, uid, cid, lock=True)
                if row is None or row.lease_token != token or row.lease_until<=datetime.now(timezone.utc):
                    raise HTTPException(409, 'A conversa mudou. Recarregue o histórico antes de continuar.')
                session.add_all([user_message,ai_message])
                await session.flush()
                if kept:
                    first = await session.scalar(select(Message.sequence).where(Message.user_id==uid,
                        Message.conversation_id==row.id, Message.id==UUID(kept[0]['message_id'])))
                else: first = sequence+3
                row.summary, row.context_from, row.last_sequence = summary, first, sequence+2
                row.lease_token, row.lease_until = None, None
                session.add(ConversationReceipt(user_id=uid, conversation_id=row.id, request_id=body.request_id,
                    message_hash=digest, sequence=sequence+2, result=result))
                await session.flush()
                await session.execute(delete(Message).where(Message.user_id==uid, Message.conversation_id==row.id, Message.sequence<=sequence+2-200))
                stale = select(ConversationReceipt.id).where(ConversationReceipt.user_id==uid, ConversationReceipt.conversation_id==row.id)
                stale = stale.order_by(ConversationReceipt.sequence.desc()).offset(12)
                await session.execute(delete(ConversationReceipt).where(ConversationReceipt.id.in_(stale)))
            return result
        finally:
            async with unit_of_work() as session:
                await session.execute(update(Conversation).where(Conversation.user_id==uid, Conversation.id==conversation_id,
                    Conversation.lease_token==token).values(lease_token=None, lease_until=None))
