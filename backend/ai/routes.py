"""Authenticated Agent endpoints. User scope comes exclusively from the session."""
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, Query
from pydantic import Field
from pymongo import ReturnDocument
from ai.types import StrictModel, AIError
from ai.config import Settings, MODELS
from ai.router import AIRouter
from ai.credentials import Credentials, public_profile, cipher
from ai.core import Core
from ai.core_writes import CoreWrites
from ai.actions import Actions, Preferences
from ai.memory import Memory, MemoryInput
from ai.rag import Retrieval
from ai.agent import SiriusAgent
from ai.automations import Automations


class KeyInput(StrictModel):
    key: str = Field(max_length=512)


class SearchInput(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    source_id: str | None = Field(default=None, max_length=100)


class InsightFeedback(StrictModel):
    feedback: str = Field(pattern='^(dismiss|snooze|never|helpful)$')


class AgentRuntime:
    def __init__(self, db, auth, transact, award_xp, update_streak):
        self.db, self.settings = db, Settings()
        self.credentials = Credentials(db)
        self.router = AIRouter(self.settings, reserve=self.reserve)
        self.core, self.memory, self.retrieval = Core(db), Memory(db), Retrieval(db, self.router, self.credentials)
        self.actions = Actions(db, CoreWrites(db, award_xp, update_streak), transact)
        self.automations = Automations(db, self.core, self.settings)
        self.agent = SiriusAgent(self.core, self.router, self.credentials, self.actions, self.memory, self.retrieval)
        self.running = {}
        self.api = APIRouter(prefix='/ai')

        async def user(request: Request):
            return await auth(authorization=request.headers.get('Authorization'), session_token=request.cookies.get('session_token'))

        @self.api.get('/status')
        async def status(account=Depends(user)):
            doc = await db.users.find_one({'user_id': account.user_id}) or {}
            public = public_profile(doc)
            usage = await db.ai_usage.find_one({'_id': self.usage_key(account.user_id)}) or {}
            return {'flags': self.settings.flags(), 'providers': {p: {'has_key': public[f'has_{p}_key'], 'last4': public[f'{p}_key_last4'], 'live_checked': False} for p in ('gemini', 'groq')},
                    'encryption_configured': bool(cipher()), 'internal_daily_limit': self.settings.daily_limit, 'internal_requests_today': usage.get('count', 0),
                    'models': {k: {'provider': m.provider, 'model': m.name, 'capabilities': sorted(m.capabilities)} for k, m in MODELS.items()},
                    'capabilities': {'chat': self.settings.agent, 'actions': 'confirmation_required', 'rag': 'lexical' if self.settings.rag else 'disabled', 'streaming': False, 'voice': self.settings.voice, 'automations': 'suggestions_only', 'automatic_writes': False},
                    'provider_limits': 'Os limites reais dependem da conta do provedor; o limite interno não representa a quota do provedor.'}

        @self.api.put('/providers/{provider}')
        async def save_key(provider: str, body: KeyInput, account=Depends(user)):
            return await self.credentials.save(account.user_id, provider, body.key)

        @self.api.get('/preferences')
        async def preferences(account=Depends(user)):
            return (await self.actions.preferences(account.user_id)).model_dump()

        @self.api.get('/insights')
        async def insights(account=Depends(user)):
            await db.ai_insights.update_many({'user_id': account.user_id, 'feedback': 'snooze', 'snoozed_until': {'$lte': datetime.now(timezone.utc).isoformat()}}, {'$set': {'feedback': None}})
            return await db.ai_insights.find({'user_id': account.user_id, 'feedback': None}, {'_id': 0}).sort('date', -1).to_list(10)

        @self.api.post('/insights/{insight_id}/feedback')
        async def feedback(insight_id: str, body: InsightFeedback, account=Depends(user)):
            from datetime import timedelta
            fields = {'feedback': body.feedback}
            if body.feedback == 'snooze': fields['snoozed_until'] = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
            result = await db.ai_insights.update_one({'user_id': account.user_id, 'insight_id': insight_id}, {'$set': fields})
            if not result.matched_count: raise HTTPException(404, 'Sugestão não encontrada.')
            return fields

        @self.api.put('/preferences')
        async def save_preferences(body: Preferences, account=Depends(user)):
            from ai.registry import TOOLS
            if any(n not in TOOLS for n in body.blocked_tools): raise HTTPException(422, 'Ferramenta desconhecida.')
            await db.ai_preferences.update_one({'user_id': account.user_id}, {'$set': {'settings': body.model_dump()}}, upsert=True)
            return body

        @self.api.get('/conversations')
        async def conversations(account=Depends(user)):
            return await db.ai_conversations.find({'user_id': account.user_id}, {'_id': 0, 'conversation_id': 1, 'title': 1, 'created_at': 1, 'updated_at': 1}).sort('updated_at', -1).to_list(30)

        @self.api.get('/conversations/{conversation_id}/history')
        async def conversation_history(conversation_id: str, offset: int = Query(0, ge=0, le=200), account=Depends(user)):
            from assistant_service import Conversations
            row = await db.ai_conversations.find_one({'_id': Conversations(db, None).key(account.user_id, conversation_id), 'user_id': account.user_id}, {'archive': 1}) or {}
            archive = row.get('archive', [])
            stop = max(0, len(archive)-offset)
            start = max(0, stop-30)
            return {'messages': archive[start:stop], 'next_offset': offset+30 if start else None, 'retention_messages': 200}

        @self.api.post('/cancel/{request_id}')
        async def cancel(request_id: str, account=Depends(user)):
            task = self.running.get((account.user_id, request_id))
            if task: task.cancel()
            return {'cancelled': bool(task)}

        @self.api.get('/actions')
        async def actions(account=Depends(user)):
            await db.ai_actions.update_many({'user_id': account.user_id, 'status': 'pending', 'expires_at': {'$lte': datetime.now(timezone.utc).isoformat()}}, {'$set': {'status': 'expired'}})
            return await db.ai_actions.find({'user_id': account.user_id}, {'_id': 0}).sort('created_at', -1).to_list(30)

        @self.api.post('/actions/{action_id}/confirm')
        async def confirm(action_id: str, account=Depends(user)):
            if not self.settings.agent: raise HTTPException(503, 'Agente desabilitado.')
            return await self.actions.confirm(account.user_id, action_id)

        @self.api.post('/actions/{action_id}/cancel')
        async def cancel_action(action_id: str, account=Depends(user)):
            return await self.actions.cancel(account.user_id, action_id)

        @self.api.get('/daily')
        async def daily(start: int = Query(480, ge=0, le=1439), end: int = Query(1080, gt=0, le=1440), capacity: int = Query(240, ge=0, le=1440), account=Depends(user)):
            if start >= end: raise HTTPException(422, 'Intervalo inválido.')
            return await self.agent.daily(account.user_id, start, end, capacity)

        @self.api.get('/weekly')
        async def weekly(account=Depends(user)):
            return await self.core.weekly(account.user_id)

        @self.api.get('/memory')
        async def memories(account=Depends(user)):
            return await self.memory.list(account.user_id)

        @self.api.post('/memory')
        async def create_memory(body: MemoryInput, account=Depends(user)):
            return await self.memory.save(account.user_id, body)

        @self.api.put('/memory/{memory_id}')
        async def update_memory(memory_id: str, body: MemoryInput, account=Depends(user)):
            return await self.memory.save(account.user_id, body, memory_id)

        @self.api.delete('/memory/{memory_id}')
        async def remove_memory(memory_id: str, block: bool = True, account=Depends(user)):
            return await self.memory.remove(account.user_id, memory_id, block)

        @self.api.post('/rag/editais/{source_id}')
        async def index(source_id: str, account=Depends(user)):
            if not self.settings.rag: raise HTTPException(503, 'Busca documental desabilitada.')
            return await self.retrieval.index_edital(account.user_id, source_id)

        @self.api.post('/rag/search')
        async def search(body: SearchInput, account=Depends(user)):
            if not self.settings.rag: raise HTTPException(503, 'Busca documental desabilitada.')
            return await self.retrieval.search(account.user_id, body.query, body.source_id)

        @self.api.get('/rag/sources')
        async def sources(account=Depends(user)):
            own = {'user_id': account.user_id}
            editais = await db.edital_analyses.find(own, {'_id': 0, 'analysis_id': 1, 'pdf_filename': 1}).to_list(50)
            notebooks = await db.notebooks.find(own, {'_id': 0, 'notebook_id': 1, 'name': 1, 'title': 1}).to_list(50)
            return {'editais': editais, 'notebooks': notebooks}

        @self.api.post('/rag/notebooks/{source_id}')
        async def index_notebook(source_id: str, account=Depends(user)):
            if not self.settings.rag: raise HTTPException(503, 'Busca documental desabilitada.')
            return await self.retrieval.index_notebook(account.user_id, source_id)

        @self.api.post('/voice/transcribe')
        async def transcribe(file: UploadFile = File(...), account=Depends(user)):
            if not self.settings.voice: raise HTTPException(503, 'Voz desabilitada.')
            mime = (file.content_type or '').split(';')[0]
            if mime not in ('audio/webm', 'audio/ogg', 'audio/wav', 'audio/mpeg', 'audio/mp4'): raise HTTPException(415, 'Formato de áudio inválido.')
            content = await file.read(8 * 1024 * 1024 + 1)
            if not content or len(content) > 8 * 1024 * 1024: raise HTTPException(413, 'Envie áudio de até 8 MB.')
            try:
                result = await self.router.generate(task='speech_to_text', keys=await self.credentials.get(account.user_id), user_id=account.user_id, audio=content, mime=mime)
                return {'text': result.text[:6000], 'requires_review': True}
            except AIError: raise HTTPException(503, 'Transcrição indisponível. Você pode continuar digitando.') from None

    def usage_key(self, user_id):
        return user_id + ':' + datetime.now(timezone.utc).strftime('%Y-%m-%d')

    async def reserve(self, user_id, model):
        key = self.usage_key(user_id)
        await self.db.ai_usage.update_one({'_id': key}, {'$setOnInsert': {'user_id': user_id, 'count': 0}}, upsert=True)
        row = await self.db.ai_usage.find_one_and_update({'_id': key, 'count': {'$lt': self.settings.daily_limit}}, {'$inc': {'count': 1}}, return_document=ReturnDocument.AFTER)
        return bool(row)

    async def chat(self, user_id, body):
        from assistant_service import Conversations
        if not self.settings.agent: raise HTTPException(503, 'Agente desabilitado.')
        key = (user_id, body.request_id)
        if key in self.running: raise HTTPException(409, 'Esta mensagem já está em processamento.')
        async def generate(prompt, **kwargs): return await self.agent.respond(user_id, body, prompt)
        task = asyncio.create_task(Conversations(self.db, generate).send(user_id, body, ''))
        self.running[key] = task
        try:
            return await asyncio.wait_for(task, timeout=150)
        except asyncio.TimeoutError: raise HTTPException(504, 'Tempo de resposta excedido. Reenvie a mensagem.') from None
        except asyncio.CancelledError: raise HTTPException(409, 'Geração cancelada. Nenhuma proposta foi executada.') from None
        finally: self.running.pop(key, None)

    async def setup(self):
        for name in ('ai_actions', 'ai_audit', 'ai_events', 'ai_memory', 'ai_chunks', 'ai_usage', 'calendar_commitments', 'transactions', 'budgets', 'notebooks', 'study_sessions', 'tasks'):
            await self.db[name].create_index('user_id')
        await self.db.ai_preferences.create_index('user_id', unique=True)
        await self.db.ai_chunks.create_index([('user_id', 1), ('terms', 1)])
        await self.db.ai_conversations.create_index([('user_id', 1), ('updated_at', -1)])
        await self.automations.start()
