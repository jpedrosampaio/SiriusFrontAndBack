"""Opt-in, bounded source polling with persistent leases and owner-scoped timelines."""
import asyncio
import difflib
import hashlib
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlsplit
from uuid import uuid4
from fastapi import APIRouter, Cookie, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from contest_sources import validate_url, provider_for, trust, SourceUnavailable


class SourceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=10, max_length=2000)
    title: str = Field(min_length=1, max_length=180)
    terms_allow_monitoring: bool = False


class ContestWatcher:
    def __init__(self, db, auth):
        self.db, self.auth, self.task = db, auth, None
        self.router = APIRouter(prefix='/study/v2/programs')

        async def owner(request, token, program_id):
            uid = (await auth(authorization=request.headers.get('Authorization'), session_token=token)).user_id
            if not await db.study_programs.find_one({'user_id': uid, 'program_id': program_id}, {'_id': 1}):
                raise HTTPException(404, 'Preparação não encontrada.')
            return uid

        @self.router.get('/{program_id}/sources')
        async def sources(request: Request, program_id: str, session_token: Optional[str] = Cookie(None)):
            uid = await owner(request, session_token, program_id)
            return await db.contest_sources.find({'user_id': uid, 'program_id': program_id}, {'_id': 0, 'snapshot': 0}).to_list(10)

        @self.router.post('/{program_id}/sources')
        async def add_source(request: Request, program_id: str, body: SourceInput, session_token: Optional[str] = Cookie(None)):
            uid = await owner(request, session_token, program_id)
            if not body.terms_allow_monitoring: raise HTTPException(422, 'Confirme que os termos da página permitem acompanhamento automático.')
            try: url = validate_url(body.url)
            except SourceUnavailable as exc: raise HTTPException(422, str(exc)) from None
            own = {'user_id': uid, 'program_id': program_id}
            key = hashlib.sha256(f'{uid}:{program_id}:{url}'.encode()).hexdigest()
            existing = await db.contest_sources.find_one({'_id': key}, {'_id': 0, 'snapshot': 0})
            if existing: return existing
            if await db.contest_sources.count_documents(own, limit=5) >= 5: raise HTTPException(409, 'Limite de cinco fontes por preparação.')
            now = datetime.now(timezone.utc).isoformat()
            doc = {**own, 'source_id': key, 'url': url, 'title': body.title.strip(), 'trust': trust(url), 'provider': provider_for(url).name,
                   'created_at': now, 'next_poll': now, 'enabled': True, 'failures': 0, 'status': 'pending', 'terms_confirmed_at': now}
            await db.contest_sources.update_one({'_id': key}, {'$setOnInsert': doc}, upsert=True)
            return doc

        @self.router.delete('/{program_id}/sources/{source_id}')
        async def remove_source(request: Request, program_id: str, source_id: str, session_token: Optional[str] = Cookie(None)):
            uid = await owner(request, session_token, program_id)
            await db.contest_sources.delete_one({'user_id': uid, 'program_id': program_id, 'source_id': source_id})
            return {'removed': True}

        @self.router.post('/{program_id}/sources/{source_id}/poll')
        async def poll(request: Request, program_id: str, source_id: str, session_token: Optional[str] = Cookie(None)):
            uid = await owner(request, session_token, program_id)
            source = await db.contest_sources.find_one({'user_id': uid, 'program_id': program_id, 'source_id': source_id})
            if not source: raise HTTPException(404, 'Fonte não encontrada.')
            return await self.poll_source(source)

        @self.router.get('/{program_id}/timeline')
        async def timeline(request: Request, program_id: str, session_token: Optional[str] = Cookie(None)):
            uid = await owner(request, session_token, program_id)
            return await db.contest_updates.find({'user_id': uid, 'program_id': program_id}, {'_id': 0}).sort('detected_at', -1).to_list(100)

        @self.router.get('/{program_id}/exams')
        async def exams(request: Request, program_id: str, session_token: Optional[str] = Cookie(None)):
            uid = await owner(request, session_token, program_id)
            return await db.contest_updates.find({'user_id': uid, 'program_id': program_id, 'document_type': {'$in': ['exam', 'answer_key']}}, {'_id': 0}).sort('detected_at', -1).to_list(100)

    async def poll_source(self, source):
        now = datetime.now(timezone.utc)
        lease = uuid4().hex
        claimed = await self.db.contest_sources.find_one_and_update({'_id': source['_id'], 'enabled': True, 'next_poll': {'$lte': now.isoformat()}},
            {'$set': {'next_poll': (now + timedelta(hours=6)).isoformat(), 'lease': lease}}, return_document=ReturnDocument.AFTER)
        if not claimed: return {'status': 'cached', 'message': 'A consulta já está agendada; intervalo mínimo de seis horas.'}
        domain = urlsplit(source['url']).hostname
        try:
            await self.db.contest_host_limits.update_one({'_id': domain}, {'$setOnInsert': {'next_poll': ''}}, upsert=True)
        except DuplicateKeyError: pass
        allowed = await self.db.contest_host_limits.find_one_and_update({'_id': domain, 'next_poll': {'$lte': now.isoformat()}}, {'$set': {'next_poll': (now + timedelta(minutes=2)).isoformat()}})
        scope = {'_id': source['_id'], 'lease': lease}
        if not allowed:
            await self.db.contest_sources.update_one(scope, {'$set': {'next_poll': (now + timedelta(minutes=15)).isoformat()}})
            return {'status': 'deferred', 'message': 'Outra fonte deste domínio foi consultada recentemente.'}
        try:
            page = await asyncio.to_thread(provider_for(source['url']).poll, source['url'], source.get('etag'), source.get('modified'))
            # Source deletion during the fetch revokes further ingestion.
            if not await self.db.contest_sources.find_one(scope): return {'status': 'removed'}
            values = {'last_checked': now.isoformat(), 'status': 'ok', 'error': None, 'failures': 0}
            if page:
                previous = source.get('snapshot', '')
                changes = None
                if previous and page.content_hash != source.get('content_hash'):
                    diff = list(difflib.unified_diff(previous.splitlines(), page.text.splitlines(), n=1))
                    changes = {'added': [s[1:] for s in diff if s.startswith('+') and not s.startswith('+++')][:60],
                               'removed': [s[1:] for s in diff if s.startswith('-') and not s.startswith('---')][:60], 'partial': len(diff) > 120}
                    page.documents.insert(0, {'title': 'Alteração detectada na página acompanhada', 'url': source['url'], 'document_type': 'page_change', 'hash': page.content_hash,
                        'hash_basis': 'page_text', 'published_at': None, 'official': source['trust'] == 'OFFICIAL', 'source_type': source['trust'], 'changes': changes})
                for item in page.documents:
                    key = f"{source['source_id']}:{item['hash']}"
                    await self.db.contest_updates.update_one({'_id': key}, {'$setOnInsert': {**item, 'update_id': key, 'user_id': source['user_id'], 'program_id': source['program_id'],
                        'source': source['title'], 'source_id': source['source_id'], 'detected_at': now.isoformat(), 'summary': 'Documento encontrado na página acompanhada; confira o conteúdo na fonte.'}}, upsert=True)
                values.update(snapshot=page.text, content_hash=page.content_hash, etag=page.etag, modified=page.modified)
            await self.db.contest_sources.update_one(scope, {'$set': values})
            return {'status': 'ok', 'message': 'Fonte consultada. Documentos e diferenças disponíveis na linha do tempo.'}
        except Exception as exc:
            failures = min(8, source.get('failures', 0) + 1)
            message = str(exc) if isinstance(exc, SourceUnavailable) else 'Fonte indisponível; nova tentativa agendada.'
            await self.db.contest_sources.update_one(scope, {'$set': {'status': 'unavailable', 'error': message[:300], 'failures': failures,
                'last_checked': now.isoformat(), 'next_poll': (now + timedelta(hours=min(72, 6 * 2 ** failures))).isoformat()}})
            return {'status': 'unavailable', 'message': message}

    async def setup(self):
        await self.db.contest_sources.create_index([('enabled', 1), ('next_poll', 1)])
        await self.db.contest_updates.create_index([('user_id', 1), ('program_id', 1), ('detected_at', -1)])
        self.task = asyncio.create_task(self.worker())

    async def worker(self):
        while True:
            try:
                due = await self.db.contest_sources.find({'enabled': True, 'next_poll': {'$lte': datetime.now(timezone.utc).isoformat()}}).limit(20).to_list(20)
                for source in due:
                    if await self.db.study_programs.find_one({'user_id': source['user_id'], 'program_id': source['program_id']}, {'_id': 1}):
                        await self.poll_source(source)
            except Exception:
                pass  # A database outage must not terminate the scheduler permanently.
            await asyncio.sleep(900)

    async def close(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError): await self.task
