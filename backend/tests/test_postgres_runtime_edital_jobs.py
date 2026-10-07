import os
import unittest
import tempfile
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
from unittest.mock import AsyncMock
from fastapi import FastAPI,HTTPException
from httpx import AsyncClient,ASGITransport
from sqlalchemy import delete,select
from db.models.files import EditalJob
from db.session import unit_of_work
from edital_jobs import EditalJobs
from storage.objects import LocalDevelopmentStorage,UnconfiguredStorage,StorageUnavailable
from services import edital_analyses as analyses
import test_postgres_runtime_catalog as catalog_tests
import test_postgres_runtime_editais as edital_tests


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

    async def submit(self,content=b'%PDF-test',headers=None):
        return await self.client.post('/study/edital-jobs',files={'file':('notice.pdf',content,'application/pdf')},headers=headers)

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
        for _ in range(2): self.assertEqual((await self.submit()).status_code,202)
        self.assertEqual((await self.submit()).status_code,429)
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

    async def test_storage_failure_never_creates_job_or_runs_ai(self):
        self.service.storage=SimpleNamespace(put=AsyncMock(side_effect=StorageUnavailable('private diagnostic')))
        response=await self.submit()
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['detail']['code'],'durable_storage_unavailable')
        self.assertNotIn('private',response.text)
        self.assertEqual((await self.client.get('/study/edital-jobs')).json()['jobs'],[])
        self.process.assert_not_awaited()
