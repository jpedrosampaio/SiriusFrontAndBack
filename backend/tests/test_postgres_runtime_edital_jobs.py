import os
import asyncio
import unittest
import tempfile
import hashlib
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
from unittest.mock import AsyncMock
from fastapi import FastAPI,HTTPException
from httpx import AsyncClient,ASGITransport
from sqlalchemy import delete,select
from db.models.files import EditalJob
from db.session import unit_of_work
from edital_jobs import EditalJobs
from storage.objects import LocalDevelopmentStorage,UnconfiguredStorage,StorageUnavailable,StoredObject
from services import edital_analyses as analyses
import test_postgres_runtime_catalog as catalog_tests
import test_postgres_runtime_editais as edital_tests


class ContentAddressedStorage:
    def __init__(self):
        self.objects={}; self.entered=asyncio.Event(); self.gate=None

    async def put(self,owner,content):
        digest=hashlib.sha256(content).hexdigest(); key=f'{owner}/{digest}'
        self.objects[(str(owner),key)]=content
        self.entered.set()
        if self.gate is not None: await self.gate.wait()
        return StoredObject('synthetic_content_addressed',key,digest,len(content))

    async def read(self,owner,key): return self.objects[(str(owner),key)]
    async def delete(self,owner,key): self.objects.pop((str(owner),key),None)


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeEditalJobs(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        self.directory=tempfile.TemporaryDirectory()
        self.storage=LocalDevelopmentStorage(self.directory.name)
        async def authenticate(authorization=None,session_token=None):
            return SimpleNamespace(user_id=str(self.bob if authorization=='Bearer bob' else self.uid))
        self.process=AsyncMock()
        self.service=EditalJobs(authenticate,self.process,self.storage)
        app=FastAPI(); app.include_router(self.service.router)
        self.client=AsyncClient(transport=ASGITransport(app),base_url='https://sirius.test')

    async def asyncTearDown(self):
        await self.service.stop(); await self.client.aclose()
        async with unit_of_work() as session:
            await session.execute(delete(EditalJob).where(EditalJob.user_id.in_([self.uid,self.bob])))
        self.directory.cleanup()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def submit(self,content=b'%PDF-test',headers=None,force=False):
        return await self.client.post('/study/edital-jobs',params={'force':force},files={'file':('notice.pdf',content,'application/pdf')},headers=headers)

    async def test_shared_input_survives_opposite_force_job_until_last_completion(self):
        self.service.storage=store=ContentAddressedStorage()
        left,right=await asyncio.gather(self.submit(),self.submit(force=True))
        self.assertEqual(left.status_code,202);self.assertEqual(right.status_code,202)
        self.assertNotEqual(left.json()['job_id'],right.json()['job_id'])
        first=await self.service.claim();second=await self.service.claim()
        self.assertEqual(first['storage_key'],second['storage_key'])
        self.assertNotEqual(first['force'],second['force'])
        self.process.side_effect=HTTPException(400,'Falha sintética recuperável.')
        await self.service.run(first)
        self.assertEqual(await store.read(self.uid,second['storage_key']),b'%PDF-test')
        await self.service.run(second)
        self.assertEqual(store.objects,{})
        self.assertEqual(self.process.await_count,2)
        async with unit_of_work() as session:
            rows=(await session.scalars(select(EditalJob).where(EditalJob.user_id==self.uid))).all()
            self.assertEqual(len(rows),2);self.assertTrue(all(r.storage_key is None for r in rows))

    async def test_owner_limit_rejection_cannot_delete_shared_input_or_other_owner(self):
        self.service.storage=store=ContentAddressedStorage()
        self.assertEqual((await self.submit()).status_code,202)
        self.assertEqual((await self.submit(b'%PDF-second')).status_code,202)
        other=await self.submit(headers={'Authorization':'Bearer bob'})
        self.assertEqual(other.status_code,202)
        self.assertEqual((await self.submit(force=True)).status_code,429)
        self.assertEqual(len(store.objects),3)
        async with unit_of_work() as session:
            rows=(await session.scalars(select(EditalJob))).all()
            owned=[r for r in rows if r.user_id in (self.uid,self.bob)]
            for row in owned: self.assertTrue((await store.read(row.user_id,row.storage_key)).startswith(b'%PDF-'))
        self.process.assert_not_awaited()

    async def test_terminal_cleanup_serializes_with_reupload_of_content_addressed_key(self):
        self.service.storage=store=ContentAddressedStorage()
        await self.submit(); old=await self.service.claim()
        await self.service.finish(old,'failed','Falha sintética.')
        store.entered.clear();store.gate=asyncio.Event()
        upload=asyncio.create_task(self.submit(force=True))
        await asyncio.wait_for(store.entered.wait(),timeout=5)
        cleanup=asyncio.create_task(self.service.cleanup())
        await asyncio.sleep(0.05)
        store.gate.set()
        response,_=await asyncio.gather(upload,cleanup)
        self.assertEqual(response.status_code,202)
        current=await self.service.claim()
        self.assertEqual(await store.read(self.uid,current['storage_key']),b'%PDF-test')
        await self.service.finish(current,'failed','Falha sintética.')
        await self.service.cleanup();self.assertEqual(store.objects,{})
        self.process.assert_not_awaited()

    async def test_worker_success_persists_analysis_and_deletes_binary(self):
        doc=edital_tests.RuntimeEditais.document(self); await analyses.save(self.uid,doc)
        self.process.return_value={'analysis_id':doc['analysis_id']}
        self.assertEqual((await self.submit()).status_code,202)
        job=await self.service.claim(); key=job['storage_key']
        await self.service.run(job)
        self.process.assert_awaited_once(); self.assertEqual(self.process.call_args.args[0],str(self.uid))
        async with unit_of_work() as session:
            row=await session.get(EditalJob,job['id'])
            self.assertEqual(row.status,'completed'); self.assertEqual(str(row.analysis_id),doc['analysis_id'])
            self.assertIsNone(row.storage_key)
        self.assertFalse(self.storage.path(self.uid,key).exists())
        self.assertEqual((await self.client.get('/study/edital-jobs',headers={'Authorization':'Bearer bob'})).json()['jobs'],[])
        await analyses.remove(self.uid,doc['analysis_id'])
        self.assertEqual((await self.client.get('/study/edital-jobs')).json()['jobs'],[])
        async with unit_of_work() as session:
            self.assertIsNone((await session.get(EditalJob,job['id'])).analysis_id)

    async def test_failure_and_expired_lease_never_retry_ai(self):
        self.process.side_effect=HTTPException(400,'Configure sua chave Gemini.')
        await self.submit(); job=await self.service.claim(); await self.service.run(job)
        self.process.assert_awaited_once(); self.assertIsNone(await self.service.claim())
        rows=(await self.client.get('/study/edital-jobs')).json()['jobs']
        self.assertEqual(rows[0]['status'],'failed'); self.assertIn('Gemini',rows[0]['phase'])
        await self.submit(); stale=await self.service.claim()
        async with unit_of_work() as session:
            row=await session.get(EditalJob,stale['id']); row.lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)
        self.assertIsNone(await self.service.claim()); await self.service.cleanup()
        self.process.assert_awaited_once()

    async def test_upload_validation_owner_limit_and_unconfigured_storage(self):
        self.assertEqual((await self.submit(b'not-pdf')).status_code,422)
        for i in range(2): self.assertEqual((await self.submit(b'%PDF-distinct-'+str(i).encode())).status_code,202)
        self.assertEqual((await self.submit(b'%PDF-third-distinct')).status_code,429)
        self.assertEqual(len(list(self.storage.root.rglob('*/*'))),2)
        self.assertEqual((await self.submit(headers={'Authorization':'Bearer bob'})).status_code,202)
        self.service.storage=UnconfiguredStorage()
        before=(await self.client.get('/study/edital-jobs')).json()['jobs']
        result=await self.submit()
        self.assertEqual(result.status_code,503)
        self.assertEqual(result.json()['detail']['code'],'durable_storage_unavailable')
        self.assertEqual((await self.client.get('/study/edital-jobs')).json()['jobs'],before)
        await self.service.start(); self.assertIsNone(self.service.task)
        self.assertFalse((await self.client.get('/study/edital-jobs')).json()['upload_available'])

    async def test_concurrent_duplicate_uploads_share_one_owned_job_and_keep_input(self):
        left,right=await asyncio.gather(self.submit(),self.submit())
        self.assertEqual(left.status_code,202);self.assertEqual(right.status_code,202)
        self.assertEqual(left.json()['job_id'],right.json()['job_id'])
        self.assertTrue(left.json().get('replayed') or right.json().get('replayed'))
        self.assertEqual(len((await self.client.get('/study/edital-jobs')).json()['jobs']),1)
        job=await self.service.claim()
        self.assertEqual(await self.storage.read(self.uid,job['storage_key']),b'%PDF-test')
        self.assertEqual(len(list(self.storage.root.rglob('*/*'))),1)
        other=await self.submit(headers={'Authorization':'Bearer bob'})
        self.assertEqual(other.status_code,202);self.assertNotEqual(other.json()['job_id'],left.json()['job_id'])
        self.process.assert_not_awaited()

    async def test_async_classified_failure_survives_without_private_exception_body(self):
        from ai.errors import public_ai_error
        error=public_ai_error('model_unavailable'); error.detail['message']='PRIVATE_PROVIDER_DOCUMENT'
        self.process.side_effect=error
        await self.submit(); job=await self.service.claim(); await self.service.run(job)
        row=(await self.client.get('/study/edital-jobs')).json()['jobs'][0]
        self.assertEqual(row['status'],'failed');self.assertIn('modelo',row['phase'].lower())
        self.assertNotIn('PRIVATE',row['phase']);self.assertIsNone(row['analysis_id'])
        self.process.assert_awaited_once();self.assertIsNone(await self.service.claim())

    async def test_storage_failure_never_creates_job_or_runs_ai(self):
        self.service.storage=SimpleNamespace(put=AsyncMock(side_effect=StorageUnavailable('private diagnostic')))
        response=await self.submit()
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['detail']['code'],'durable_storage_unavailable')
        self.assertNotIn('private',response.text)
        self.assertEqual((await self.client.get('/study/edital-jobs')).json()['jobs'],[])
        self.process.assert_not_awaited()
