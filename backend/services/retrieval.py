"""SQL lexical retrieval; source ownership and revocation are checked in SQL."""
import hashlib
import re
from itertools import islice
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, delete, func, or_
from ai.rag import chunks, terms
from db.models.files import RagSource, RagChunk, FileRecord, EditalAnalysis
from db.models.studies import Notebook, StudyDraft, StudyNote
from db.repositories.identity import IdentityRepository
from db.repositories.rag import RagRepository, live_source
from db.session import unit_of_work


def identity(value):
    try: return UUID(str(value))
    except (ValueError, TypeError, AttributeError): raise HTTPException(404, 'Fonte não encontrada.') from None


def attachment_json(row):
    return {'attachment_id':str(row.id), 'user_id':str(row.user_id), 'filename':row.filename, 'name':row.filename,
        'provenance':row.details.get('provenance','extracted'), 'created_at':row.created_at.isoformat(),
        'indexed':row.details.get('indexed',False), 'original_available':False, 'retention':'extracted_text_only'}


class Retrieval:
    async def _index(self, session, uid, source_id, source_type, pages):
        model, field = {'edital':(EditalAnalysis,RagSource.analysis_id), 'notebook':(Notebook,RagSource.notebook_id),
            'attachment':(FileRecord,RagSource.file_id)}[source_type]
        statement=select(model).where(model.user_id==uid,model.id==source_id)
        if model is Notebook: statement=statement.where(Notebook.archived_at.is_(None))
        if await session.scalar(statement.with_for_update()) is None: raise HTTPException(404,'Fonte não encontrada.')
        batch=list(islice(chunks(pages),2001));truncated=len(batch)>2000;batch=batch[:2000]
        generation=hashlib.sha256(''.join(c['hash'] for c in batch).encode()).hexdigest()
        source=await session.scalar(select(RagSource).where(RagSource.user_id==uid,field==source_id))
        if source is None:
            source=RagSource(user_id=uid,source_type=source_type,generation='',**{field.key:source_id})
            session.add(source);await session.flush()
        result=await RagRepository(session).replace_chunks(uid,source.id,generation,batch)
        return {**result,'method':'lexical','source_id':str(source_id),'truncated':truncated}

    async def index_edital(self, user_id, source_id):
        uid,sid=identity(user_id),identity(source_id)
        async with unit_of_work() as session:
            await IdentityRepository(session).by_id(uid,lock=True)
            row=await session.scalar(select(EditalAnalysis).where(EditalAnalysis.user_id==uid,EditalAnalysis.id==sid).with_for_update())
            if row is None: raise HTTPException(404,'Análise não encontrada.')
            return await self._index(session,uid,sid,'edital',row.pages or [row.extracted_text or ''])

    async def index_notebook(self, user_id, source_id):
        uid,sid=identity(user_id),identity(source_id)
        async with unit_of_work() as session:
            await IdentityRepository(session).by_id(uid,lock=True)
            row=await session.scalar(select(Notebook).where(Notebook.user_id==uid,Notebook.id==sid,Notebook.archived_at.is_(None)).with_for_update())
            if row is None: raise HTTPException(404,'Caderno não encontrado.')
            drafts=(await session.scalars(select(StudyDraft.text).where(StudyDraft.user_id==uid,StudyDraft.notebook_id==sid)
                .order_by(StudyDraft.updated_at.desc(),StudyDraft.id).limit(100))).all()
            notes=(await session.execute(select(StudyNote.title,StudyNote.content).where(StudyNote.user_id==uid,StudyNote.notebook_id==sid)
                .order_by(StudyNote.updated_at.desc(),StudyNote.id).limit(100))).all()
            pages=[row.notes or '',*drafts,*[title+'\n'+content for title,content in notes]]
            return await self._index(session,uid,sid,'notebook',[re.sub(r'<[^>]+>',' ',p) for p in pages])

    async def ensure_selection(self,user_id,selection):
        if 'analysis' in selection: await self.index_edital(user_id,selection['analysis']['analysis_id'])
        if 'notebook' in selection: await self.index_notebook(user_id,selection['notebook']['notebook_id'])

    async def sources(self,user_id):
        uid=identity(user_id)
        from services.edital_analyses import list_owned
        editais=[{'analysis_id':r['analysis_id'],'pdf_filename':r['pdf_filename']} for r in (await list_owned(uid))['editais'][:50]]
        async with unit_of_work() as session:
            books=(await session.execute(select(Notebook.id,Notebook.name).where(Notebook.user_id==uid,Notebook.archived_at.is_(None))
                .order_by(Notebook.created_at.desc(),Notebook.id).limit(50))).all()
            return {'editais':editais,'notebooks':[{'notebook_id':str(nid),'name':name} for nid,name in books]}

    async def existing_attachment(self,user_id,digest):
        async with unit_of_work() as session:
            row=await session.scalar(select(FileRecord).where(FileRecord.user_id==identity(user_id),FileRecord.sha256==digest))
            return attachment_json(row) if row and row.details.get('indexed') else None

    async def attach(self,user_id,digest,filename,mime,size,pages,provenance):
        uid=identity(user_id)
        async with unit_of_work() as session:
            if await IdentityRepository(session).by_id(uid,lock=True) is None: raise HTTPException(404,'User not found')
            row=await session.scalar(select(FileRecord).where(FileRecord.user_id==uid,FileRecord.sha256==digest))
            if row is None:
                count=await session.scalar(select(func.count()).select_from(FileRecord).where(FileRecord.user_id==uid,FileRecord.details['attachment'].as_boolean().is_(True)))
                if count>=100: raise HTTPException(409,'Limite de 100 anexos. Remova arquivos antigos antes de enviar novos.')
                row=FileRecord(user_id=uid,storage_provider='metadata_only',filename=filename,mime_type=mime,size_bytes=size,sha256=digest,
                    details={'attachment':True,'provenance':provenance,'indexed':False})
                session.add(row);await session.flush()
            await self._index(session,uid,row.id,'attachment',pages)
            row.details={**row.details,'attachment':True,'provenance':provenance,'indexed':True}
            await session.flush();await session.refresh(row)
            return attachment_json(row)

    async def remove_attachment(self,user_id,source_id):
        uid,sid=identity(user_id),identity(source_id)
        async with unit_of_work() as session:
            await IdentityRepository(session).by_id(uid,lock=True)
            row=await session.scalar(select(FileRecord).where(FileRecord.user_id==uid,FileRecord.id==sid))
            if row is None or not row.details.get('attachment'): raise HTTPException(404,'Anexo não encontrado.')
            await session.execute(delete(RagSource).where(RagSource.user_id==uid,RagSource.file_id==sid))
            # A file metadata row may also be referenced by an analysis; preserve that foreign key.
            referenced=await session.scalar(select(EditalAnalysis.id).where(EditalAnalysis.user_id==uid,EditalAnalysis.file_id==sid).limit(1))
            if referenced: row.details={k:v for k,v in row.details.items() if k not in ('attachment','indexed','provenance')}
            else: await session.delete(row)
        return {'deleted':True}

    async def search(self,user_id,query,source_id=None):
        uid=identity(user_id);tokens=sorted(terms(query))[:30]
        if not tokens:return {'method':'lexical','citations':[]}
        async with unit_of_work() as session:
            source=None
            if source_id:
                try:sid=UUID(str(source_id))
                except ValueError:return {'method':'lexical','citations':[]}
                source=await session.scalar(select(RagSource).where(RagSource.user_id==uid,live_source(),
                    or_(RagSource.file_id==sid,RagSource.analysis_id==sid,RagSource.notebook_id==sid)))
                if source is None:return {'method':'lexical','citations':[]}
            rows=await RagRepository(session).lexical_search(uid,tokens,source.id if source else None)
            if not rows and source:
                rows=list((await session.scalars(select(RagChunk).where(RagChunk.user_id==uid,RagChunk.source_id==source.id)
                    .order_by(RagChunk.chunk_index).limit(5))).all())
            sources={s.id:s for s in (await session.scalars(select(RagSource).where(RagSource.user_id==uid,live_source(),RagSource.id.in_([r.source_id for r in rows])))).all()}
            citations=[]
            for row in rows:
                origin=sources.get(row.source_id)
                if origin is None: continue
                citations.append({'source_id':str(origin.file_id or origin.analysis_id or origin.notebook_id), 'source_type':origin.source_type,
                    'page':row.details.get('page'), 'section':'PDF' if origin.source_type=='edital' else 'Anotações',
                    'hash':row.content_hash, 'text':row.content})
            return {'method':'lexical','citations':citations}
