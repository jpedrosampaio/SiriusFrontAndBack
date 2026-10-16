"""Actual PostgreSQL intake durability. No provider or production database."""
import asyncio
import hashlib
import os
import unittest
from datetime import timedelta
from uuid import UUID,uuid4
from fastapi import HTTPException
from sqlalchemy import select,func,delete
from db.session import unit_of_work
from db.models.files import EditalAnalysis,EditalJob
from db.models.edital_units import EditalUnit
from db.models.identity import User
from edital_pipeline_contracts import DocumentIR,SourcePage,SourceBlock
from services import edital_pipeline_store as store
import test_postgres_agent as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class DurableEditalIntake(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=setup.PostgresAgent.asyncSetUp

    async def asyncTearDown(self):
        async with unit_of_work() as session:await session.execute(delete(User).where(User.id.in_((self.uid,self.other))))
        await setup.PostgresAgent.asyncTearDown(self)

    def document(self,scanned=False):
        text='Perfil A: Analista de Sistemas. Vagas: cadastro de reserva. Programa da seleção pública.'
        return DocumentIR(sha256=hashlib.sha256(text.encode()).hexdigest(),size_bytes=200,
            pages=[SourcePage(page=1,width=600,height=800,quality='requires_ocr' if scanned else 'text',characters=0 if scanned else len(text),
                blocks=[] if scanned else [SourceBlock(id='p0001-b0001',page=1,text=text,bbox=(50,50,550,70))])])

    async def reserve(self,owner=None,key=None,document=None,force=False):
        document=document or self.document()
        return await store.reserve_intake(owner or self.uid,document.sha256,'synthetic.pdf',force,key or str(uuid4()))

    async def test_concurrent_lost_ack_replay_uses_one_durable_input_and_unit_set(self):
        key=str(uuid4());document=self.document()
        results=await asyncio.gather(*(self.reserve(key=key) for _ in range(6)))
        self.assertEqual(sum(r['action']=='start' for r in results),1)
        self.assertEqual(len({r['job_id'] for r in results}),1)
        first=next(r for r in results if r['action']=='start')
        committed=await store.persist_input(self.uid,first['job_id'],first['token'],document)
        # Simulate a successful commit followed by a lost HTTP202 response.
        replies=await asyncio.gather(*(self.reserve(key=key) for _ in range(4)))
        self.assertTrue(all(r['action']=='accepted' and r['analysis_id']==committed['analysis_id'] for r in replies))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(EditalAnalysis).where(EditalAnalysis.user_id==self.uid)),1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(EditalUnit).where(EditalUnit.user_id==self.uid)),1)
            row=await store.owned_analysis(session,self.uid,committed['analysis_id'],source=True)
            self.assertEqual(row.pages[0]['blocks'][0]['text'],document.pages[0].blocks[0].text)
            self.assertEqual(store.manifest(row).source.hash,document.sha256)

    async def test_duplicate_upload_keys_share_input_but_accounts_do_not(self):
        document=self.document();first=await self.reserve()
        result=await store.persist_input(self.uid,first['job_id'],first['token'],document)
        duplicate=await self.reserve();self.assertEqual(duplicate['analysis_id'],result['analysis_id'])
        other=await self.reserve(owner=self.other)
        other_result=await store.persist_input(self.other,other['job_id'],other['token'],document)
        self.assertNotEqual(other_result['analysis_id'],result['analysis_id'])
        async with unit_of_work() as session:
            with self.assertRaises(HTTPException) as error:await store.owned_analysis(session,self.other,result['analysis_id'])
            self.assertEqual(error.exception.status_code,404)

    async def test_expired_intake_is_fenced_and_original_does_not_overwrite_resumption(self):
        key=str(uuid4());first=await self.reserve(key=key)
        async with unit_of_work() as session:(await session.get(EditalJob,UUID(first['job_id']))).lease_until=store.utc_now()-timedelta(seconds=1)
        resumed=await self.reserve(key=key);self.assertEqual(resumed['action'],'start')
        self.assertNotEqual(first['token'],resumed['token'])
        with self.assertRaises(HTTPException) as error:await store.persist_input(self.uid,first['job_id'],first['token'],self.document())
        self.assertEqual(error.exception.status_code,409)
        result=await store.persist_input(self.uid,resumed['job_id'],resumed['token'],self.document())
        await store.fail_intake(self.uid,first['job_id'],first['token'],'old_handler_cancelled')
        async with unit_of_work() as session:
            row=await session.get(EditalJob,UUID(first['job_id']));self.assertEqual(str(row.analysis_id),result['analysis_id']);self.assertEqual(row.status,'queued')

    async def test_scanned_input_preserves_page_identity_and_schedules_no_ai(self):
        document=self.document(scanned=True);first=await self.reserve(document=document)
        result=await store.persist_input(self.uid,first['job_id'],first['token'],document)
        self.assertEqual(result['status'],'ocr_required')
        async with unit_of_work() as session:
            row=await store.owned_analysis(session,self.uid,result['analysis_id'])
            self.assertEqual(store.manifest(row).source.ocr_required_pages,[1])
            self.assertFalse(store.manifest(row).source.original_available)
            self.assertEqual(await session.scalar(select(func.count()).select_from(EditalUnit).where(EditalUnit.user_id==self.uid)),0)

    async def test_key_cannot_change_document_or_force_and_foreign_nonce_cannot_finish(self):
        key=str(uuid4());first=await self.reserve(key=key)
        for digest,force in [('a'*64,False),(self.document().sha256,True)]:
            with self.assertRaises(HTTPException) as error:await store.reserve_intake(self.uid,digest,'other.pdf',force,key)
            self.assertEqual(error.exception.status_code,409)
        with self.assertRaises(HTTPException) as error:await store.persist_input(self.other,first['job_id'],first['token'],self.document())
        self.assertEqual(error.exception.status_code,404)

    async def test_parser_admission_is_global_and_released_after_failure(self):
        first=await self.reserve();key=str(uuid4())
        with self.assertRaises(HTTPException) as error:await self.reserve(owner=self.other,key=key)
        self.assertEqual(error.exception.status_code,429)
        await store.fail_intake(self.uid,first['job_id'],first['token'],'invalid_pdf')
        self.assertEqual((await self.reserve(owner=self.other,key=key))['action'],'start')
