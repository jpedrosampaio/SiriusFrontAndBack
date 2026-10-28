"""Owned HTTP acceptance/ETag/source contracts with actual disposable SQL."""
import asyncio
import hashlib
import os
import unittest
from uuid import uuid4,UUID
from unittest.mock import patch
from fastapi import FastAPI
from httpx import AsyncClient,ASGITransport
from sqlalchemy import select,func,delete,event
from db.session import unit_of_work
from db.engine import get_engine
from db.models.identity import User
from db.models.files import EditalAnalysis,EditalJob
from db.models.edital_units import EditalUnit
from edital_pipeline_contracts import DocumentIR,SourcePage,SourceBlock
from services import edital_pipeline_routes as routes,edital_pipeline_units as units,edital_pipeline_store as store
from services import edital_routes as legacy_routes
from services.edital_pdf import PDFInputError,ExtractionMetrics
import test_postgres_agent as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class PipelineHTTP(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await setup.PostgresAgent.asyncSetUp(self)
        self.patches=[];self.wakes=[];self.extracts=[];self.entered=asyncio.Event();self.release=asyncio.Event();self.release.set()
        async def account(request):return {'user_id':str(self.other if request.headers.get('Authorization')=='Bearer bob' else self.uid)}
        async def extract(content):
            self.extracts.append(content);self.entered.set();await self.release.wait()
            return DocumentIR(sha256=hashlib.sha256(content).hexdigest(),size_bytes=len(content),pages=[
                SourcePage(page=1,width=600,height=800,quality='text',characters=18,blocks=[
                    SourceBlock(id='p0001-b0001',page=1,text='Cargo A: Analista.',bbox=(0,0,500,20))])])
        for target,value in [('account',account),('extract_pdf',extract),('_wake',lambda:self.wakes.append(True)),('_input_gate',asyncio.Semaphore(1))]:
            item=patch.object(routes,target,value);item.start();self.patches.append(item)
        item=patch.object(legacy_routes,'account',account);item.start();self.patches.append(item)
        app=FastAPI();app.include_router(routes.router,prefix='/api');app.include_router(legacy_routes.router,prefix='/api')
        self.http=AsyncClient(transport=ASGITransport(app),base_url='https://edital.test')

    async def asyncTearDown(self):
        await self.http.aclose()
        for item in reversed(self.patches):item.stop()
        async with unit_of_work() as session:await session.execute(delete(User).where(User.id.in_((self.uid,self.other))))
        await setup.PostgresAgent.asyncTearDown(self)

    async def submit(self,key=None,content=b'%PDF-synthetic',**headers):
        return await self.http.post('/api/study/edital-pipeline',files={'file':('synthetic.pdf',content,'application/pdf')},
            headers={'Idempotency-Key':key or str(uuid4()),**headers})

    async def test_existing_delete_route_releases_owned_incremental_upload_capacity(self):
        first=(await self.submit()).json()
        second=(await self.submit(content=b'%PDF-second')).json()
        self.assertEqual((await self.submit(content=b'%PDF-third')).status_code,429)
        path='/api/study/programs/editais/'+first['analysis_id']
        self.assertEqual((await self.http.delete(path,headers={'Authorization':'Bearer bob'})).status_code,404)
        response=await self.http.delete(path)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['deleted_count'],1)
        self.assertEqual((await self.submit(content=b'%PDF-third')).status_code,202)
        async with unit_of_work() as session:
            self.assertEqual((await session.get(EditalJob,UUID(first['job_id']))).status,'failed')
            self.assertIsNotNone(await session.get(EditalAnalysis,UUID(second['analysis_id'])))

    async def test_http202_waits_for_persisted_ir_and_lost_response_replays_without_parser_or_ai(self):
        key=str(uuid4());self.release.clear();pending=asyncio.create_task(self.submit(key))
        try:
            await asyncio.wait_for(self.entered.wait(),3)
            self.assertFalse(pending.done())
            async with unit_of_work() as session:
                self.assertEqual(await session.scalar(select(func.count()).select_from(EditalAnalysis).where(EditalAnalysis.user_id==self.uid)),0)
                job=await session.scalar(select(EditalJob).where(EditalJob.user_id==self.uid));self.assertIsNone(job.analysis_id)
        finally:self.release.set()
        response=await pending;self.assertEqual(response.status_code,202,response.text);first=response.json()
        for _ in range(2):
            replay=await self.submit(key);self.assertEqual(replay.status_code,202,replay.text)
            self.assertEqual(replay.json()['analysis_id'],first['analysis_id'])
        duplicate=await self.submit();self.assertEqual(duplicate.json()['analysis_id'],first['analysis_id'])
        self.assertEqual(len(self.extracts),1);self.assertEqual(len(self.wakes),1)
        async with unit_of_work() as session:
            row=await store.owned_analysis(session,self.uid,first['analysis_id'],source=True)
            self.assertEqual(row.pages[0]['blocks'][0]['text'],'Cargo A: Analista.')
            self.assertFalse(store.manifest(row).source.original_available)
            self.assertEqual(await session.scalar(select(func.sum(EditalUnit.provider_calls)).where(EditalUnit.user_id==self.uid)),0)
        other=await self.submit(Authorization='Bearer bob');self.assertEqual(other.status_code,202,other.text)
        self.assertNotEqual(other.json()['analysis_id'],first['analysis_id'])

    async def test_pre_ir_reservation_from_another_replica_returns409_not_false_acceptance(self):
        key=str(uuid4());content=b'%PDF-synthetic'
        first=await store.reserve_intake(self.uid,hashlib.sha256(content).hexdigest(),'synthetic.pdf',False,key)
        response=await self.submit(key);self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(response.json()['detail']['job_id'],first['job_id'])
        self.assertEqual(self.extracts,[]);self.assertEqual(self.wakes,[])

    async def test_etag_is_owned_lightweight_and_changes_on_claim_and_failure(self):
        result=(await self.submit()).json();url='/api/study/edital-pipeline/'+result['analysis_id']
        first=await self.http.get(url);self.assertEqual(first.status_code,200,first.text);tag=first.headers['etag']
        old=f'"edital-v6-{result["analysis_id"]}-{first.json()["revision"]}"'
        refreshed=await self.http.get(url,headers={'If-None-Match':old})
        self.assertEqual(refreshed.status_code,200);self.assertEqual(refreshed.headers['etag'],tag)
        with patch.object(routes,'FORECAST_VERSION',routes.FORECAST_VERSION+1):
            deployed=await self.http.get(url,headers={'If-None-Match':tag})
        self.assertEqual(deployed.status_code,200);self.assertNotEqual(deployed.headers['etag'],tag)
        statements=[];engine=get_engine().sync_engine
        def record(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
        event.listen(engine,'before_cursor_execute',record)
        try:unchanged=await self.http.get(url,headers={'If-None-Match':tag})
        finally:event.remove(engine,'before_cursor_execute',record)
        self.assertEqual(unchanged.status_code,304);self.assertEqual(unchanged.content,b'')
        reads=[s.lower() for s in statements if 'edital_analyses' in s]
        self.assertEqual(len(reads),1);self.assertNotIn('structured_payload',reads[0]);self.assertNotIn('extracted_text',reads[0])
        foreign=await self.http.get(url,headers={'If-None-Match':tag,'Authorization':'Bearer bob'})
        self.assertEqual(foreign.status_code,404)
        plan=first.json()['execution_plan'];self.assertFalse(plan['live_provider_validated'])
        self.assertEqual(first.json()['manifest']['status'],'waiting_provider')
        resumed=await self.http.post(url+'/resume',json={'revision':first.json()['revision'],'mode':'pilot'},
            headers={'Idempotency-Key':str(uuid4())})
        self.assertEqual(resumed.status_code,200,resumed.text)
        claim=await units.claim_next();self.assertEqual(claim.user_id,self.uid)
        claimed=await self.http.get(url,headers={'If-None-Match':tag});self.assertEqual(claimed.status_code,200)
        self.assertNotEqual(claimed.headers['etag'],tag)
        self.assertTrue(any(d['status']=='running' for d in claimed.json()['diagnostics']))
        await units.fail(claim,'invalid_key')
        failed=await self.http.get(url,headers={'If-None-Match':claimed.headers['etag']});self.assertEqual(failed.status_code,200)
        self.assertEqual(failed.json()['manifest']['status'],'waiting_provider')
        diagnostic=failed.json()['diagnostics'][0]
        self.assertEqual(diagnostic['error_kind'],'invalid_key');self.assertTrue(diagnostic['reference'])
        self.assertIsNone(diagnostic['last_observed_model']);self.assertEqual(diagnostic['provider_calls'],0)

    async def test_source_endpoint_returns_one_owned_page_not_original_file_or_other_account(self):
        result=(await self.submit()).json();base='/api/study/edital-pipeline/'+result['analysis_id']+'/source/'
        response=await self.http.get(base+'1');self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['text'],'Cargo A: Analista.');self.assertFalse(response.json()['original_available'])
        self.assertNotIn('pdf_bytes',response.json());self.assertIn('no-store',response.headers['cache-control'])
        for suffix in ('0','2','401'):self.assertEqual((await self.http.get(base+suffix)).status_code,404)
        self.assertEqual((await self.http.get(base+'1',headers={'Authorization':'Bearer bob'})).status_code,404)

    async def test_encrypted_input_has_specific_safe_error_and_never_creates_analysis(self):
        async def protected(content):raise PDFInputError('encrypted_pdf','PRIVATE-DOCUMENT-DO-NOT-LOG')
        with patch.object(routes,'extract_pdf',protected):response=await self.submit()
        self.assertEqual(response.status_code,422);self.assertEqual(response.json()['detail']['code'],'encrypted_pdf')
        self.assertIn('senha',response.json()['detail']['message']);self.assertNotIn('PRIVATE-DOCUMENT',response.text)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(EditalAnalysis).where(EditalAnalysis.user_id==self.uid)),0)
            job=await session.scalar(select(EditalJob).where(EditalJob.user_id==self.uid))
            self.assertEqual(job.status,'failed');self.assertNotIn('PRIVATE-DOCUMENT',job.phase)

    async def test_invalid_signature_or_missing_key_precedes_extraction(self):
        response=await self.submit(content=b'not a PDF');self.assertEqual(response.status_code,422)
        response=await self.http.post('/api/study/edital-pipeline',files={'file':('synthetic.pdf',b'%PDF-synthetic','application/pdf')})
        self.assertEqual(response.status_code,422);self.assertEqual(self.extracts,[])

    async def test_process_failure_keeps_reference_and_does_not_commit_partial_ir(self):
        for code,status in [('extraction_process_failed',503),('extraction_result_limit',422)]:
            metrics=ExtractionMetrics('123456abcdef',2760,-9,0,True)
            async def interrupted(content):
                raise PDFInputError(code,'PRIVATE-DOCUMENT-OR-CREDENTIAL',metrics=metrics)
            with self.subTest(code=code),patch.object(routes,'extract_pdf',interrupted),\
                self.assertLogs(level='WARNING') as logged:
                response=await self.submit(content=('%PDF-'+code).encode())
            self.assertEqual(response.status_code,status)
            self.assertEqual(response.json()['detail']['reference'],metrics.reference)
            self.assertEqual(response.json()['detail']['code'],code)
            self.assertNotIn('PRIVATE',response.text)
            self.assertNotIn('PRIVATE',' '.join(logged.output))
            self.assertIn('reference='+metrics.reference,' '.join(logged.output))
            async with unit_of_work() as session:
                self.assertEqual(await session.scalar(select(func.count()).select_from(EditalAnalysis).where(EditalAnalysis.user_id==self.uid)),0)
                jobs=(await session.scalars(select(EditalJob).where(EditalJob.user_id==self.uid))).all()
                self.assertTrue(jobs and all(job.status=='failed' for job in jobs))
            self.assertEqual(self.wakes,[])

    async def test_cancelled_http_keeps_durable_parser_admission_until_lease_expiry(self):
        self.release.clear();key=str(uuid4());task=asyncio.create_task(self.submit(key))
        await asyncio.wait_for(self.entered.wait(),3);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        async with unit_of_work() as session:
            job=await session.scalar(select(EditalJob).where(EditalJob.user_id==self.uid))
            self.assertEqual(job.status,'running');self.assertGreater(job.lease_until,store.utc_now());self.assertIsNone(job.analysis_id)
        response=await self.submit(key);self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(len(self.extracts),1);self.assertEqual(self.wakes,[])

    async def test_history_lists_summaries_and_loads_one_owned_immutable_snapshot_on_demand(self):
        from db.models.command import CommandAudit
        result=(await self.submit()).json();identity=UUID(result['analysis_id']);audit_id=uuid4()
        async with unit_of_work() as session:
            session.add(CommandAudit(id=audit_id,user_id=self.uid,event='edital.reviewed',action='confirm_role',
                entity_type='edital_analysis',entity_id=identity,reason={},before=None,
                after={'note':'Conferi o cargo.','program':{'private_snapshot':'DO-NOT-BULK-LOAD'}}))
        base=f'/api/study/edital-pipeline/{identity}/history'
        listed=await self.http.get(base);self.assertEqual(listed.status_code,200,listed.text)
        self.assertEqual(listed.json()['history'][0]['note'],'Conferi o cargo.')
        self.assertNotIn('DO-NOT-BULK-LOAD',listed.text);self.assertNotIn('program',listed.json()['history'][0])
        exact=await self.http.get(base+'/'+str(audit_id));self.assertEqual(exact.status_code,200,exact.text)
        self.assertEqual(exact.json()['after']['program']['private_snapshot'],'DO-NOT-BULK-LOAD')
        for suffix in ('','/'+str(audit_id)):
            self.assertEqual((await self.http.get(base+suffix,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.get(base+'/'+str(uuid4()))).status_code,404)

    async def test_prior_program_candidates_are_owned_and_match_document_not_model_role_spelling(self):
        from db.models.studies import StudyArea,StudyProgram
        result=(await self.submit()).json();identity=UUID(result['analysis_id'])
        async with unit_of_work() as session:
            analysis=await store.owned_analysis(session,self.uid,identity)
            for uid in (self.uid,self.other):
                area=StudyArea(user_id=uid,name='Concursos');session.add(area);await session.flush()
                session.add(StudyProgram(user_id=uid,area_id=area.id,name='Programa anterior',edital_data={
                    'universal_edital':{'document_hash':analysis.content_hash,'role_id':'model-name-from-another-analysis'}}))
                if uid==self.uid:session.add(StudyProgram(user_id=uid,area_id=area.id,name='Programa histórico',edital_data={'analysis_id':str(identity)}))
        response=await self.http.get(f'/api/study/edital-pipeline/{identity}/import-candidates')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual({p['name'] for p in response.json()['programs']},{'Programa anterior','Programa histórico'})
        self.assertTrue(all('document_hash' not in p and 'edital_data' not in p for p in response.json()['programs']))
        foreign=await self.http.get(f'/api/study/edital-pipeline/{identity}/import-candidates',headers={'Authorization':'Bearer bob'})
        self.assertEqual(foreign.status_code,404)
