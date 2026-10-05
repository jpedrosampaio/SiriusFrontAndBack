import asyncio
import io
import os
import unittest
from datetime import datetime, timezone
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func,delete
from db.session import unit_of_work
from db.models.files import FileRecord,RagSource,RagChunk,EditalAnalysis
from db.models.studies import StudyArea,Notebook,StudyNote,StudyDraft
from db.repositories.rag import RagRepository
import test_postgres_runtime_agent_actions as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeRetrieval(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=setup.RuntimeAgentActions.asyncSetUp
    asyncTearDown=setup.RuntimeAgentActions.asyncTearDown
    ok=setup.RuntimeAgentActions.ok

    def pdf(self):
        from reportlab.pdfgen.canvas import Canvas
        output=io.BytesIO();canvas=Canvas(output);canvas.drawString(30,800,'Direito constitucional e portugues');canvas.save()
        return output.getvalue()

    async def test_pdf_attachment_dedup_owner_lexical_citation_and_delete(self):
        content=self.pdf()
        values=[self.ok(r) for r in await asyncio.gather(*(self.http.post('/ai/attachments',files={'file':('material.pdf',content,'application/pdf')}) for _ in range(5)))]
        sid=values[0]['attachment_id'];self.assertEqual(len({v['attachment_id'] for v in values}),1)
        self.assertFalse(values[0]['original_available']);self.assertEqual(values[0]['retention'],'extracted_text_only')
        result=self.ok(await self.http.post('/ai/rag/search',json={'query':'constitucional','source_id':sid}))
        self.assertEqual(result['method'],'lexical');self.assertEqual(result['citations'][0]['page'],1)
        self.assertEqual(result['citations'][0]['source_id'],sid)
        foreign={'Authorization':'Bearer bob'}
        self.assertEqual(self.ok(await self.http.post('/ai/rag/search',json={'query':'constitucional','source_id':sid},headers=foreign))['citations'],[])
        self.assertEqual((await self.http.delete('/ai/attachments/'+sid,headers=foreign)).status_code,404)
        async with unit_of_work() as session:
            for model in (FileRecord,RagSource,RagChunk):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),1)
        self.ok(await self.http.delete('/ai/attachments/'+sid))
        self.assertEqual(self.ok(await self.http.post('/ai/rag/search',json={'query':'constitucional'}))['citations'],[])
        self.assertEqual((await self.http.post('/ai/attachments',files={'file':('bad.pdf',b'bad','application/pdf')})).status_code,422)

    async def test_notebook_refresh_archive_and_edital_delete_revoke_sources(self):
        async with unit_of_work() as session:
            area=StudyArea(user_id=self.uid,name='Study');session.add(area);await session.flush()
            book=Notebook(user_id=self.uid,area_id=area.id,name='Book',notes='Direito constitucional')
            analysis=EditalAnalysis(user_id=self.uid,content_hash='a'*64,status='completed',analysis_version='1',structured_payload={},
                filename='edital.pdf',pages=[{'page':7,'text':'Direito administrativo'}])
            session.add_all([book,analysis]);await session.flush();nid,aid=book.id,analysis.id
            session.add(StudyNote(user_id=self.uid,notebook_id=nid,title='Note',content='Portuguese grammar'))
            session.add(StudyDraft(user_id=self.uid,notebook_id=nid,text='Mathematics probability'))
        service=self.runtime.retrieval
        await service.ensure_selection(self.uid,{'notebook':{'notebook_id':str(nid)},'analysis':{'analysis_id':str(aid)}})
        self.assertTrue((await service.index_notebook(self.uid,nid))['unchanged'])
        self.assertEqual((await service.search(self.uid,'administrativo',aid))['citations'][0]['page'],7)
        self.assertEqual((await service.search(self.other,'administrativo'))['citations'],[])
        async with unit_of_work() as session:
            book=await session.get(Notebook,nid);book.notes='Biologia celular'
        original=RagRepository.replace_chunks
        async def fail_refresh(*args,**kwargs):
            await original(*args,**kwargs)
            raise RuntimeError('after replacement')
        with patch.object(RagRepository,'replace_chunks',fail_refresh):
            with self.assertRaises(RuntimeError):await service.index_notebook(self.uid,nid)
        self.assertTrue((await service.search(self.uid,'constitucional'))['citations'])
        await service.index_notebook(self.uid,nid)
        self.assertEqual((await service.search(self.uid,'constitucional'))['citations'],[])
        self.assertTrue((await service.search(self.uid,'biologia'))['citations'])
        async with unit_of_work() as session:
            book=await session.get(Notebook,nid);book.archived_at=datetime.now(timezone.utc)
            await session.execute(delete(EditalAnalysis).where(EditalAnalysis.id==aid))
        self.assertEqual((await service.search(self.uid,'biologia'))['citations'],[])
        self.assertEqual((await service.search(self.uid,'administrativo',aid))['citations'],[])
        sources=self.ok(await self.http.get('/ai/rag/sources'));self.assertEqual(sources,{'editais':[],'notebooks':[]})

    async def test_attachment_failure_rolls_back_metadata_and_chunks(self):
        original=RagRepository.replace_chunks
        async def failure(*args,**kwargs):
            await original(*args,**kwargs)
            raise RuntimeError('after chunks')
        with patch.object(RagRepository,'replace_chunks',failure):
            with self.assertRaises(RuntimeError):await self.http.post('/ai/attachments',files={'file':('material.pdf',self.pdf(),'application/pdf')})
        async with unit_of_work() as session:
            for model in (FileRecord,RagSource,RagChunk):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),0)
