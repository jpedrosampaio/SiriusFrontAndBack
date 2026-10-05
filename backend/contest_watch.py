"""Opt-in source polling; persistence and leases are PostgreSQL-backed."""
import asyncio
import difflib
import logging
from contextlib import suppress
from typing import Optional
from fastapi import APIRouter,Cookie,Request
from pydantic import BaseModel,ConfigDict,Field
from contest_sources import provider_for,SourceUnavailable
from services import contest_tracking as tracking


class SourceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=10, max_length=2000)
    title: str = Field(min_length=1, max_length=180)
    terms_allow_monitoring: bool = False


class ContestWatcher:
    def __init__(self,auth):
        self.auth,self.task=auth,None
        self.router=APIRouter(prefix='/study/v2/programs')

        async def owner(request,token):
            return (await auth(authorization=request.headers.get('Authorization'),session_token=token)).user_id

        @self.router.get('/{program_id}/sources')
        async def sources(request: Request,program_id: str,session_token: Optional[str]=Cookie(None)):
            return await tracking.list_sources(await owner(request,session_token),program_id)

        @self.router.post('/{program_id}/sources')
        async def add_source(request: Request,program_id: str,body: SourceInput,session_token: Optional[str]=Cookie(None)):
            return await tracking.add(await owner(request,session_token),program_id,body)

        @self.router.delete('/{program_id}/sources/{source_id}')
        async def remove_source(request: Request,program_id: str,source_id: str,session_token: Optional[str]=Cookie(None)):
            return await tracking.remove(await owner(request,session_token),program_id,source_id)

        @self.router.post('/{program_id}/sources/{source_id}/poll')
        async def poll(request: Request,program_id: str,source_id: str,session_token: Optional[str]=Cookie(None)):
            return await self.poll_source(await owner(request,session_token),program_id,source_id)

        @self.router.get('/{program_id}/timeline')
        async def timeline(request: Request,program_id: str,session_token: Optional[str]=Cookie(None)):
            return await tracking.timeline(await owner(request,session_token),program_id)

        @self.router.get('/{program_id}/exams')
        async def exams(request: Request,program_id: str,session_token: Optional[str]=Cookie(None)):
            return await tracking.timeline(await owner(request,session_token),program_id,exams=True)

    async def poll_source(self,user_id,program_id,source_id):
        source=await tracking.claim(user_id,program_id,source_id)
        if not source.get('claimed'):return source
        try:
            page=await asyncio.to_thread(provider_for(source['url']).poll,source['url'],source.get('etag'),source.get('modified'))
            documents=[]
            if page:
                documents=list(page.documents)
                previous=source.get('snapshot','')
                if previous and page.content_hash!=source.get('content_hash'):
                    diff=list(difflib.unified_diff(previous.splitlines(),page.text.splitlines(),n=1))
                    changes={'added':[line[1:] for line in diff if line.startswith('+') and not line.startswith('+++')][:60],
                        'removed':[line[1:] for line in diff if line.startswith('-') and not line.startswith('---')][:60],'partial':len(diff)>120}
                    documents.insert(0,{'title':'Alteração detectada na página acompanhada','url':source['url'],'document_type':'page_change',
                        'hash':page.content_hash,'hash_basis':'page_text','published_at':None,'official':source['trust']=='OFFICIAL',
                        'source_type':source['trust'],'changes':changes})
            if not await tracking.finish(source,page,documents):return {'status':'removed'}
            return {'status':'ok','message':'Fonte consultada. Documentos e diferenças disponíveis na linha do tempo.'}
        except Exception as exc:
            message=str(exc) if isinstance(exc,SourceUnavailable) else 'Fonte indisponível; nova tentativa agendada.'
            if not await tracking.finish(source,error=message):return {'status':'removed'}
            return {'status':'unavailable','message':message}

    async def setup(self):
        if self.task is None:self.task=asyncio.create_task(self.worker())

    async def worker(self):
        while True:
            try:
                for uid,pid,sid in await tracking.due():
                    await self.poll_source(uid,pid,sid)
            except Exception:
                logging.warning('contest source worker failed; retry deferred')
            await asyncio.sleep(900)

    async def close(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):await self.task
            self.task=None
