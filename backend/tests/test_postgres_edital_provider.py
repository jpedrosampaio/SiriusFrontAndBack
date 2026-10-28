"""Explicit pilot, recovery and budget fences against disposable PostgreSQL only."""
import os
import asyncio
import unittest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock,patch
import json
import httpx
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import select,delete
from db.session import unit_of_work
from db.models.identity import User
from db.models.edital_units import EditalUnit
from services import (edital_pipeline_store as store,edital_pipeline_units as units,
    edital_pipeline_controls as controls,edital_pipeline_progress as progress,edital_pipeline_budget as budget)
from ai.types import AIError,AIResult
from ai.config import MODELS
import test_postgres_agent as setup
import test_postgres_edital_pipeline as intake


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class ProviderRecovery(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=setup.PostgresAgent.asyncSetUp
    document=intake.DurableEditalIntake.document

    async def asyncTearDown(self):
        async with unit_of_work() as session:
            await session.execute(delete(User).where(User.id.in_((self.uid,self.other))))
        await setup.PostgresAgent.asyncTearDown(self)

    async def create(self,legacy=False,reserved_attempts=5):
        doc=self.document();reserved=await store.reserve_intake(self.uid,doc.sha256,'synthetic.pdf',False,str(uuid4()))
        accepted=await store.persist_input(self.uid,reserved['job_id'],reserved['token'],doc)
        self.identity=accepted['analysis_id']
        if legacy:
            async with unit_of_work() as session:
                row=await store.owned_analysis(session,self.uid,self.identity,lock=True)
                state=store.manifest(row);state.status=state.inventory.status='processing';state.budget.reserved_attempts=reserved_attempts
                base=await session.scalar(select(EditalUnit).where(EditalUnit.analysis_id==row.id))
                base.attempts=3;base.provider_calls=reserved_attempts;base.diagnostics={**base.diagnostics,'attempts':[{'provider':'gemini','model':'legacy','at':'2026-10-20'}]}
                for index in range(66):
                    session.add(EditalUnit(user_id=self.uid,analysis_id=row.id,job_id=base.job_id,generation=base.generation,
                        scope_key='inventory',kind='inventory',unit_key=f'{index:064x}',source_blocks=base.source_blocks,context_blocks=[]))
                store.write_manifest(row,state)

    async def state(self):
        async with unit_of_work() as session:
            row=await store.owned_analysis(session,self.uid,self.identity)
            return row.revision,store.manifest(row),await budget.forecast(session,row,store.manifest(row))

    async def resume(self,owner=None,key=None,**values):
        revision,_,_=await self.state()
        return await controls.resume(owner or self.uid,self.identity,key or str(uuid4()),controls.Resume(revision=revision,**values))

    async def test_documentary_failure_preserves_sources_budget_and_owned_safe_diagnostic(self):
        await self.create();await self.resume(mode='pilot');claim=await units.claim_next()
        await units.provider_attempt(claim,MODELS['vision'])
        validation={'stage':'documentary','code':'source_excerpt_mismatch','path':'$','quote':'PRIVATE-OUTPUT'}
        await units.fail(claim,'evidence_invalid',validation=validation)
        self.assertIsNone(await units.claim_next())
        _,state,_=await self.state()
        self.assertEqual(state.budget.reserved_attempts,1);self.assertEqual(state.budget.provider_limit,120)
        self.assertFalse(state.provider_approval.pilot_validated);self.assertEqual(state.inventory.roles,[])
        from services import edital_pipeline_routes as routes
        request=Request({'type':'http','method':'GET','path':'/','headers':[]})
        with patch.object(routes,'account',AsyncMock(return_value={'user_id':str(self.uid)})):
            response=await routes.get_state(request,self.identity)
        failure=json.loads(response.body)['diagnostics'][0]['failure']
        self.assertEqual(failure['response_validation'],{'stage':'documentary','code':'source_excerpt_mismatch','path':'$'})
        self.assertIsNone(failure['http_status']);self.assertNotIn('PRIVATE-OUTPUT',response.body.decode())
        with patch.object(routes,'account',AsyncMock(return_value={'user_id':str(self.other)})):
            with self.assertRaises(HTTPException) as denied:await routes.get_state(request,self.identity)
        self.assertEqual(denied.exception.status_code,404)
        async with unit_of_work() as session:
            row=await session.get(EditalUnit,claim.unit_id)
            self.assertIsNone(row.result);self.assertNotIn('PRIVATE-OUTPUT',json.dumps(row.diagnostics))
            analysis=await store.owned_analysis(session,self.uid,self.identity,source=True)
            self.assertEqual(analysis.pages[0]['blocks'][0]['text'],self.document().pages[0].blocks[0].text)

    async def test_legacy_is_paused_before_io_and_budget_includes_future_checks(self):
        await self.create(legacy=True)
        self.assertIsNone(await units.claim_next())
        _,state,plan=await self.state()
        self.assertEqual(state.status,'waiting_provider');self.assertEqual(state.budget.reserved_attempts,5)
        self.assertEqual(plan['stages'],{'inventory':67,'scope':0,'detail':0,'verify':67})
        self.assertEqual(plan['minimum_total_attempts'],139);self.assertTrue(plan['extension_required'])
        with self.assertRaises(HTTPException) as error:await self.resume(mode='full',provider_limit=139)
        self.assertEqual(error.exception.detail['code'],'pilot_required')
        with self.assertRaises(HTTPException) as foreign:await self.resume(owner=self.other,mode='pilot')
        self.assertEqual(foreign.exception.status_code,404)
        await self.resume(mode='pilot');claim=await units.claim_next();self.assertIsNotNone(claim)
        data=await units.snapshot(claim)
        self.assertEqual(data['primary'][0]['text'],self.document().pages[0].blocks[0].text)
        await units.provider_attempt(claim,SimpleNamespace(provider='gemini',name='mock'))
        with self.assertRaises(AIError) as cap:await units.provider_attempt(claim,SimpleNamespace(provider='groq',name='mock'))
        self.assertEqual(cap.exception.kind,'pilot_limit')
        await units.complete(claim,{'roles':[],'classifications':[{'block_id':'p0001-b0001','kind':'roles'}]},
            consolidate=progress.consolidate,provider='gemini',model='mock')
        self.assertIsNone(await units.claim_next())
        _,state,plan=await self.state()
        self.assertTrue(plan['live_provider_validated']);self.assertEqual(state.status,'waiting_provider')
        self.assertEqual(state.error_kind,'pilot_review_required');self.assertEqual(state.budget.reserved_attempts,6)
        self.assertEqual(plan['minimum_total_attempts'],139)
        with self.assertRaises(HTTPException) as missing:await self.resume(mode='full')
        self.assertEqual(missing.exception.detail['code'],'planned_units_exceed_remaining_budget')
        async with unit_of_work() as session:
            row=await session.get(EditalUnit,claim.unit_id)
            self.assertEqual(row.attempts,3);self.assertEqual(row.diagnostics['claims_total'],4);self.assertEqual(row.provider_calls,6)
            self.assertEqual(row.diagnostics['attempts'][0]['model'],'legacy')
            self.assertEqual(row.status,'completed')
        revision,_,_=await self.state();key=str(uuid4());body=controls.Resume(revision=revision,mode='full',provider_limit=139)
        result=await controls.resume(self.uid,self.identity,key,body)
        replay=await controls.resume(self.uid,self.identity,key,body)
        self.assertEqual(result['revision'],replay['revision']);self.assertTrue(replay['replayed'])
        _,state,_=await self.state();self.assertEqual(state.budget.provider_limit,139)

    async def test_no_io_cooldown_does_not_burn_retry_failures_or_provider_budget(self):
        await self.create();await self.resume(mode='pilot');claim=await units.claim_next()
        with self.assertRaises(HTTPException) as running:await self.resume(mode='pilot')
        self.assertEqual(running.exception.detail['code'],'execution_in_progress')
        error=AIError('unavailable',retry_after=60,reason='cooldown')
        await units.fail(claim,error.kind,error.retry_after,error=error)
        self.assertIsNone(await units.claim_next())
        _,state,_=await self.state();self.assertEqual(state.budget.reserved_attempts,0)
        self.assertEqual(state.status,'waiting_provider');self.assertFalse(state.provider_approval.pilot_validated)
        async with unit_of_work() as session:
            row=await session.get(EditalUnit,claim.unit_id)
            self.assertEqual(row.attempts,1);self.assertEqual(row.diagnostics['retry_failures'],0)
            self.assertFalse(row.diagnostics['last_failure']['provider_attempted'])
        with self.assertRaises(HTTPException) as cooldown:await self.resume(mode='pilot')
        self.assertEqual(cooldown.exception.detail['code'],'retry_not_before')

    async def test_groq_public_rejection_survives_owned_persistence_without_validating_document(self):
        await self.create();await self.resume(mode='pilot');claim=await units.claim_next()
        await units.provider_attempt(claim,MODELS['reasoning'])
        error=AIError('invalid_request',http_status=400,attempted=True,request_format='groq_json_schema',
            schema_sha256='a'*64,schema_bytes=2315,provider_rejection={'provider_code':'json_validate_failed',
            'provider_type':'invalid_request_error','category':'output_validation','fields':[],
            'failed_generation':'PRIVATE-PDF-PROMPT-KEY'})
        await units.fail(claim,error.kind,error=error)
        self.assertIsNone(await units.claim_next())
        _,state,_=await self.state()
        self.assertEqual(state.budget.reserved_attempts,1);self.assertEqual(state.budget.provider_limit,120)
        self.assertFalse(state.provider_approval.pilot_validated);self.assertEqual(state.inventory.roles,[])
        from services import edital_pipeline_routes as routes
        request=Request({'type':'http','method':'GET','path':'/','headers':[]})
        with patch.object(routes,'account',AsyncMock(return_value={'user_id':str(self.uid)})):
            response=await routes.get_state(request,self.identity)
        failure=json.loads(response.body)['diagnostics'][0]['failure']
        self.assertEqual(failure['provider_rejection'],error.provider_rejection)
        self.assertEqual(failure['request_format'],'groq_json_schema');self.assertEqual(failure['schema_sha256'],'a'*64)
        self.assertNotIn('PRIVATE-PDF-PROMPT-KEY',response.body.decode())
        with patch.object(routes,'account',AsyncMock(return_value={'user_id':str(self.other)})):
            with self.assertRaises(HTTPException) as denied:await routes.get_state(request,self.identity)
        self.assertEqual(denied.exception.status_code,404)
        async with unit_of_work() as session:
            row=await session.get(EditalUnit,claim.unit_id);self.assertIsNone(row.result)
            analysis=await store.owned_analysis(session,self.uid,self.identity,source=True)
            self.assertEqual(analysis.pages[0]['blocks'][0]['text'],self.document().pages[0].blocks[0].text)

    async def test_scoped_inventory_mock_is_validated_consolidated_and_paused_without_new_upload_or_budget(self):
        import hashlib
        from ai.router import AIRouter
        from ai.providers.groq import GroqProvider
        from edital_pipeline_contracts import DocumentIR,SourcePage,SourceBlock
        from services.edital_pipeline_worker import IncrementalHandler
        text='Perfil A: Analista de Sistemas. Estas regras aplicam-se a todos os cargos.'
        doc=DocumentIR(sha256=hashlib.sha256(text.encode()).hexdigest(),size_bytes=len(text.encode()),
            pages=[SourcePage(page=1,width=600,height=800,quality='text',characters=len(text),
                blocks=[SourceBlock(id='p0001-b0001',page=1,text=text,bbox=(50,50,550,70))])])
        reserved=await store.reserve_intake(self.uid,doc.sha256,'synthetic.pdf',False,str(uuid4()))
        accepted=await store.persist_input(self.uid,reserved['job_id'],reserved['token'],doc)
        self.identity=accepted['analysis_id']
        await self.resume(mode='pilot');claim=await units.claim_next();calls=[]
        citation={'page':1,'block_id':'p0001-b0001','quote':text}
        payload={'roles':[{'name':{'value':'Analista de Sistemas','state':'extracted','sources':[citation]}}],
            'classifications':[{'block_id':'p0001-b0001','kind':'roles','scope':'all_roles','scope_sources':[citation]}]}
        from edital_wire_fixtures import inventory_wire
        payload=inventory_wire(payload)
        def response(request):
            calls.append(request);body=json.loads(request.content)
            self.assertIs(body['response_format']['json_schema']['strict'],True)
            self.assertEqual(len(body['response_format']['json_schema']['schema']['$defs']['ScopeEvidenceTransport']['anyOf']),3)
            self.assertIn('scope_sources',body['messages'][-1]['content'])
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(payload)}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['vision']]),providers={'groq':GroqProvider(client)})
            credentials=SimpleNamespace(get=AsyncMock(return_value={'groq':'synthetic-key'}))
            await IncrementalHandler(router,credentials,progress.consolidate).execute(claim)
        self.assertEqual(len(calls),1);self.assertIsNone(await units.claim_next())
        _,state,_=await self.state()
        self.assertEqual(state.budget.reserved_attempts,1);self.assertEqual(state.budget.provider_limit,120)
        self.assertTrue(state.provider_approval.pilot_validated);self.assertEqual(state.provider_approval.mode,'paused')
        self.assertEqual(state.error_kind,'pilot_review_required')
        self.assertEqual(len(state.inventory.roles),1);self.assertEqual(state.inventory.roles[0].name.value,'Analista de Sistemas')
        async with unit_of_work() as session:
            row=await session.get(EditalUnit,claim.unit_id)
            self.assertEqual(row.status,'completed');self.assertEqual(row.provider_calls,1)
            self.assertNotIn('applicability',row.result['classifications'][0])
            analysis=await store.owned_analysis(session,self.uid,self.identity,source=True)
            self.assertEqual(analysis.pages[0]['blocks'][0]['text'],text)
            self.assertEqual(store.manifest(analysis).source.hash,doc.sha256)
            with self.assertRaises(HTTPException) as denied:await store.owned_analysis(session,self.other,self.identity)
        self.assertEqual(denied.exception.status_code,404)

    async def test_local_validation_is_owned_sanitized_and_preserves_budget_history_and_source(self):
        await self.create(legacy=True,reserved_attempts=5)
        await self.resume(mode='pilot');claim=await units.claim_next()
        await units.provider_attempt(claim,MODELS['vision'])
        error=AIError('malformed_output',attempted=True,request_format='groq_json_schema',schema_sha256='a'*64,schema_bytes=2315,
            response_validation={'stage':'pydantic','code':'value_error','path':'$.roles[].name',
                'rule':'fact_missing_inconsistent','input':'PRIVATE-PDF-PROMPT-KEY'})
        await units.fail(claim,error.kind,error=error)
        self.assertIsNone(await units.claim_next())
        _,state,_=await self.state()
        self.assertEqual(state.budget.reserved_attempts,6);self.assertEqual(state.budget.provider_limit,120)
        self.assertFalse(state.provider_approval.pilot_validated);self.assertEqual(state.inventory.roles,[])
        from services import edital_pipeline_routes as routes
        request=Request({'type':'http','method':'GET','path':'/','headers':[]})
        async def read():
            with patch.object(routes,'account',AsyncMock(return_value={'user_id':str(self.uid)})):
                return await routes.get_state(request,self.identity)
        response=await read()
        diagnostic=next(row for row in json.loads(response.body)['diagnostics'] if row['unit_id']==str(claim.unit_id))
        self.assertEqual(diagnostic['failure']['response_validation'],error.response_validation)
        self.assertIsNone(diagnostic['failure']['http_status'])
        self.assertNotIn('PRIVATE-PDF-PROMPT-KEY',response.body.decode())
        with patch.object(routes,'account',AsyncMock(return_value={'user_id':str(self.other)})):
            with self.assertRaises(HTTPException) as denied:await routes.get_state(request,self.identity)
        self.assertEqual(denied.exception.status_code,404)
        async with unit_of_work() as session:
            row=await session.get(EditalUnit,claim.unit_id);self.assertIsNone(row.result)
            self.assertEqual(row.diagnostics['attempts'][0]['model'],'legacy')
            analysis=await store.owned_analysis(session,self.uid,self.identity,source=True)
            self.assertEqual(analysis.pages[0]['blocks'][0]['text'],self.document().pages[0].blocks[0].text)
            row.diagnostics={**row.diagnostics,'last_failure':{**row.diagnostics['last_failure'],
                'response_validation':{'stage':'pydantic','code':'value_error','path':'$.PRIVATE-PDF-PROMPT-KEY',
                    'rule':'PRIVATE-PDF-PROMPT-KEY','message':'PRIVATE-PDF-PROMPT-KEY'}}}
        response=await read()
        diagnostic=next(row for row in json.loads(response.body)['diagnostics'] if row['unit_id']==str(claim.unit_id))
        self.assertEqual(diagnostic['failure']['response_validation'],{'stage':'pydantic','code':'value_error','path':'$'})
        self.assertNotIn('PRIVATE-PDF-PROMPT-KEY',response.body.decode())

    async def test_http400_is_correlated_preserves_input_and_never_autoretries(self):
        await self.create();await self.resume(mode='pilot');claim=await units.claim_next()
        await units.provider_attempt(claim,SimpleNamespace(provider='gemini',name='mock'))
        error=AIError('invalid_request',http_status=400,incompatibility='schema_rejected',attempted=True,
            provider_rejection={'code':400,'status':'INVALID_ARGUMENT','category':'unknown_field','fields':['store'],
                'message':'PRIVATE-PDF-PROMPT-KEY'})
        await units.fail(claim,error.kind,error=error)
        self.assertIsNone(await units.claim_next())
        _,state,_=await self.state();self.assertEqual(state.budget.reserved_attempts,1)
        self.assertFalse(state.provider_approval.pilot_validated)
        async with unit_of_work() as session:
            row=await session.get(EditalUnit,claim.unit_id)
            self.assertEqual(row.diagnostics['reference'],error.reference)
            self.assertEqual(row.diagnostics['last_failure']['http_status'],400)
            self.assertEqual(row.diagnostics['last_failure']['provider_rejection'],
                {'code':400,'status':'INVALID_ARGUMENT','category':'unknown_field','fields':['store']})
            self.assertNotIn('PRIVATE-PDF-PROMPT-KEY',json.dumps(row.diagnostics))
            self.assertIsNone(row.result)
            analysis=await store.owned_analysis(session,self.uid,self.identity,source=True)
            self.assertEqual(analysis.pages[0]['blocks'][0]['text'],self.document().pages[0].blocks[0].text)
        from services import edital_pipeline_routes as routes
        request=Request({'type':'http','method':'GET','path':'/','headers':[]})
        with patch.object(routes,'account',AsyncMock(return_value={'user_id':str(self.uid)})):
            response=await routes.get_state(request,self.identity)
        data=json.loads(response.body)
        self.assertEqual(data['diagnostics'][0]['failure']['provider_rejection'],error.provider_rejection)
        with patch.object(routes,'account',AsyncMock(return_value={'user_id':str(self.other)})):
            with self.assertRaises(HTTPException) as denied:await routes.get_state(request,self.identity)
        self.assertEqual(denied.exception.status_code,404)
        # Even old/malformed persisted metadata cannot become a private-text echo.
        async with unit_of_work() as session:
            row=await session.get(EditalUnit,claim.unit_id)
            row.diagnostics={**row.diagnostics,'last_failure':{**row.diagnostics['last_failure'],
                'provider_rejection':{'status':'PRIVATE-PDF-PROMPT-KEY','fields':['store','PRIVATE-PDF-PROMPT-KEY'],
                    'message':'PRIVATE-PDF-PROMPT-KEY'}}}
        with patch.object(routes,'account',AsyncMock(return_value={'user_id':str(self.uid)})):
            response=await routes.get_state(request,self.identity)
        self.assertEqual(json.loads(response.body)['diagnostics'][0]['failure']['provider_rejection'],{'fields':['store']})
        self.assertNotIn('PRIVATE-PDF-PROMPT-KEY',response.body.decode())

    async def test_new_wire_requires_new_pilot_without_resetting_seven_historical_attempts(self):
        from edital_pipeline_contracts import ProviderApproval
        await self.create(legacy=True,reserved_attempts=7)
        async with unit_of_work() as session:
            row=await store.owned_analysis(session,self.uid,self.identity,lock=True)
            state=store.manifest(row)
            state.provider_approval=ProviderApproval(transport_version='structured-transport/2',mode='full',pilot_validated=True,pilot_stop_after=0)
            store.write_manifest(row,state)
        self.assertIsNone(await units.claim_next())
        _,state,plan=await self.state()
        self.assertEqual(state.budget.reserved_attempts,7);self.assertEqual(state.budget.provider_limit,120)
        self.assertEqual(plan['minimum_total_attempts'],141);self.assertFalse(plan['live_provider_validated'])
        with self.assertRaises(HTTPException) as full:await self.resume(mode='full',provider_limit=141)
        self.assertEqual(full.exception.detail['code'],'pilot_required')
        _,state,_=await self.state();self.assertEqual(state.budget.provider_limit,120)

    async def test_mock_http_role_passes_canonical_evidence_consolidation_and_pauses_after_one_call(self):
        from ai.router import AIRouter
        from ai.providers.gemini import GeminiProvider
        from services.edital_pipeline_worker import IncrementalHandler
        from test_gemini_wire_regression import published_contract
        await self.create();await self.resume(mode='pilot');calls=[]
        payload={'roles':[{'name':{'value':'Analista de Sistemas','state':'extracted','sources':[
            {'page':1,'block_id':'p0001-b0001','quote':'Analista de Sistemas'}]}}],
            'classifications':[{'block_id':'p0001-b0001','kind':'roles'}]}
        from edital_wire_fixtures import inventory_wire
        payload=inventory_wire(payload)
        def transport(request):
            body=json.loads(request.content);published_contract(body);calls.append(body)
            self.assertEqual(body['generationConfig']['responseFormat']['text']['mimeType'],'APPLICATION_JSON')
            return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(payload)}]}}],
                'usageMetadata':{'totalTokenCount':20}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            handler=IncrementalHandler(AIRouter(providers={'gemini':GeminiProvider(client)}),
                SimpleNamespace(get=AsyncMock(return_value={'gemini':'synthetic-only'})),progress.consolidate)
            self.assertTrue(await handler.run_one());self.assertFalse(await handler.run_one())
        self.assertEqual(len(calls),1)
        _,state,plan=await self.state()
        self.assertEqual(state.inventory.roles[0].name.value,'Analista de Sistemas')
        self.assertEqual(state.inventory.roles[0].name.sources[0].block_id,'p0001-b0001')
        self.assertEqual(state.status,'waiting_provider');self.assertEqual(state.error_kind,'pilot_review_required')
        self.assertEqual(state.budget.reserved_attempts,1);self.assertEqual(state.budget.provider_limit,120)
        self.assertTrue(plan['live_provider_validated']) # synthetic provider only; not a live acceptance claim
        async with unit_of_work() as session:
            completed=await session.scalar(select(EditalUnit).where(EditalUnit.analysis_id==store.uuid(self.identity),EditalUnit.kind=='inventory'))
            self.assertEqual(completed.status,'completed');self.assertEqual(completed.provider_calls,1)
            analysis=await store.owned_analysis(session,self.uid,self.identity,source=True)
            self.assertEqual(analysis.pages[0]['blocks'][0]['text'],self.document().pages[0].blocks[0].text)

    async def test_three_explicit_synthetic_probes_never_complete_real_units_or_release_full_run(self):
        from ai.router import AIRouter
        from ai.providers.gemini import GeminiProvider
        from services.edital_pipeline_worker import IncrementalHandler
        await self.create();calls=[];consolidate=AsyncMock()
        for index,case in enumerate(('text','json','inventory'),1):
            revision,before,_=await self.state()
            body=controls.Resume(revision=revision,mode='pilot',diagnostic_case=case);key=str(uuid4())
            await controls.resume(self.uid,self.identity,key,body)
            payload='OK' if case=='text' else json.dumps({'ok':True} if case=='json' else {'roles':[],
                'classifications':[{'block_id':'p0001-b0001','kind':'other'}]})
            def transport(request):
                content=json.loads(request.content);calls.append(content)
                self.assertNotIn(self.document().pages[0].blocks[0].text,json.dumps(content))
                self.assertFalse(content['store']);self.assertEqual(content['generationConfig']['maxOutputTokens'],3072)
                self.assertEqual('responseFormat' in content['generationConfig'],case!='text')
                return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':payload}]}}],'usageMetadata':{'totalTokenCount':20}})
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                handler=IncrementalHandler(AIRouter(providers={'gemini':GeminiProvider(client)}),
                    SimpleNamespace(get=AsyncMock(return_value={'gemini':'synthetic-only'})),consolidate)
                self.assertTrue(await handler.run_one());self.assertFalse(await handler.run_one())
            replay=await controls.resume(self.uid,self.identity,key,body)
            self.assertTrue(replay['replayed']);self.assertEqual(len(calls),index)
            _,state,plan=await self.state()
            self.assertEqual(state.budget.reserved_attempts,index);self.assertEqual(state.budget.provider_limit,120)
            self.assertEqual(state.budget.reported_usage['totalTokenCount'],20*index)
            self.assertEqual(state.status,'waiting_provider');self.assertEqual(state.error_kind,'provider_probe_accepted')
            self.assertEqual(state.inventory.roles,[]);self.assertFalse(state.provider_approval.pilot_validated)
            self.assertFalse(plan['live_provider_validated']);self.assertEqual(state.provider_approval.mode,'paused')
            async with unit_of_work() as session:
                row=await session.scalar(select(EditalUnit).where(EditalUnit.analysis_id==store.uuid(self.identity)))
                self.assertEqual(row.status,'waiting_provider');self.assertIsNone(row.result)
                self.assertEqual(len(row.diagnostics['provider_probes']),index)
                self.assertEqual(row.diagnostics['provider_probes'][-1]['case'],case)
                analysis=await store.owned_analysis(session,self.uid,self.identity,source=True)
                self.assertEqual(analysis.pages[0]['blocks'][0]['text'],self.document().pages[0].blocks[0].text)
            with self.assertRaises(HTTPException) as full:await self.resume(mode='full')
            self.assertEqual(full.exception.detail['code'],'pilot_required')
        consolidate.assert_not_awaited()

    async def test_predeployment_resume_receipt_replays_but_cannot_authorize_a_new_diagnostic(self):
        from db.activity import run_activity
        await self.create();revision,state,_=await self.state();key=str(uuid4())
        body=controls.Resume(revision=revision,mode='pilot')
        old_payload={'revision':revision,'provider_limit':None,'mode':'pilot'}
        previous={'analysis_id':self.identity,'revision':revision,'status':state.status}
        await run_activity(self.uid,key,['edital_pipeline','resume',self.identity,old_payload],
            AsyncMock(return_value=previous))
        replay=await controls.resume(self.uid,self.identity,key,body)
        self.assertTrue(replay['replayed']);self.assertEqual(replay['revision'],revision)
        with self.assertRaises(HTTPException) as changed:
            await controls.resume(self.uid,self.identity,key,controls.Resume(revision=revision,mode='pilot',diagnostic_case='text'))
        self.assertEqual(changed.exception.status_code,409)
        _,after,_=await self.state();self.assertEqual(after.status,state.status)
        self.assertIsNone(after.provider_approval);self.assertEqual(after.budget.reserved_attempts,state.budget.reserved_attempts)

    async def test_probe_validation_ownership_budget_and_real_completion_guard(self):
        from services.edital_semantics import EvidenceError
        await self.create()
        for values in ({'mode':'full','diagnostic_case':'text'},{'mode':'pilot','diagnostic_case':'text','provider_limit':121}):
            with self.assertRaises(HTTPException):await self.resume(**values)
        with self.assertRaises(HTTPException) as foreign:await self.resume(owner=self.other,mode='pilot',diagnostic_case='text')
        self.assertEqual(foreign.exception.status_code,404)
        await self.resume(mode='pilot',diagnostic_case='inventory');claim=await units.claim_next()
        snapshot=await units.snapshot(claim)
        self.assertEqual(snapshot['primary'],[]);self.assertEqual(snapshot['context'],[])
        with self.assertRaises(units.LeaseLost):await units.complete_diagnostic(claim,AIResult(provider='gemini',model=MODELS['flash'].name))
        with self.assertRaises(HTTPException) as running:await self.resume(mode='pilot',diagnostic_case='json')
        self.assertEqual(running.exception.detail['code'],'execution_in_progress')
        with self.assertRaises(EvidenceError):await units.complete(claim,{'roles':[],
            'classifications':[{'block_id':'p0001-b0001','kind':'other'}]},consolidate=progress.consolidate)
        revision,_,_=await self.state()
        await controls.cancel(self.uid,self.identity,str(uuid4()),controls.Version(revision=revision))

    async def test_probe400_and_quota_keep_one_attempt_and_original_failure_without_fallback(self):
        from ai.router import AIRouter
        from ai.providers.gemini import GeminiProvider
        from services.edital_pipeline_worker import IncrementalHandler
        await self.create();calls=[]
        for status in (400,429):
            await self.resume(mode='pilot',diagnostic_case='json')
            def transport(request):
                calls.append(request)
                return httpx.Response(status,json={'error':{'code':status,'status':'INVALID_ARGUMENT',
                    'message':'Request contains an invalid argument.' if status==400 else 'quota exceeded'}})
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                handler=IncrementalHandler(AIRouter(providers={'gemini':GeminiProvider(client)}),
                    SimpleNamespace(get=AsyncMock(return_value={'gemini':'synthetic-only'})),AsyncMock())
                self.assertTrue(await handler.run_one());self.assertFalse(await handler.run_one())
            _,state,_=await self.state()
            self.assertEqual(state.budget.reserved_attempts,len(calls));self.assertEqual(state.budget.provider_limit,120)
            self.assertEqual(state.error_kind,'invalid_request' if status==400 else 'quota')
            self.assertFalse(state.provider_approval.pilot_validated)
        self.assertEqual(len(calls),2)

    async def test_probe_does_not_silently_change_model_or_send_credentials_to_another_provider(self):
        from ai.router import AIRouter
        from ai.providers.gemini import GeminiProvider
        from services.edital_pipeline_worker import IncrementalHandler
        await self.create();await self.resume(mode='pilot',diagnostic_case='text');calls=[]
        def transport(request):calls.append(request);raise AssertionError('Unexpected provider request')
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['lite']]),providers={'gemini':GeminiProvider(client)})
            handler=IncrementalHandler(router,SimpleNamespace(get=AsyncMock(return_value={'gemini':'synthetic-only'})),AsyncMock())
            self.assertTrue(await handler.run_one());self.assertFalse(await handler.run_one())
        self.assertEqual(calls,[])
        _,state,_=await self.state();self.assertEqual(state.budget.reserved_attempts,0)
        self.assertEqual(state.error_kind,'model_unavailable');self.assertFalse(state.provider_approval.pilot_validated)

    async def test_cancelled_probe_cannot_commit_a_late_success_receipt(self):
        from ai.router import AIRouter
        from ai.providers.gemini import GeminiProvider
        from services.edital_pipeline_worker import IncrementalHandler
        await self.create();await self.resume(mode='pilot',diagnostic_case='text')
        started=asyncio.Event();release=asyncio.Event()
        async def transport(request):
            started.set();await release.wait()
            return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'OK'}]}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            handler=IncrementalHandler(AIRouter(providers={'gemini':GeminiProvider(client)}),
                SimpleNamespace(get=AsyncMock(return_value={'gemini':'synthetic-only'})),AsyncMock())
            task=asyncio.create_task(handler.run_one())
            await asyncio.wait_for(started.wait(),10)
            revision,_,_=await self.state()
            await controls.cancel(self.uid,self.identity,str(uuid4()),controls.Version(revision=revision))
            release.set();await asyncio.wait_for(task,10)
        _,state,_=await self.state();self.assertEqual(state.status,'cancelled')
        self.assertEqual(state.budget.reserved_attempts,1);self.assertEqual(state.inventory.roles,[])
        async with unit_of_work() as session:
            row=await session.scalar(select(EditalUnit).where(EditalUnit.analysis_id==store.uuid(self.identity)))
            self.assertIsNone(row.result);self.assertFalse(row.diagnostics.get('provider_probes'))

    async def test_malformed_probe_response_does_not_split_real_multiblock_document(self):
        from ai.router import AIRouter
        from ai.providers.gemini import GeminiProvider
        from services.edital_pipeline_worker import IncrementalHandler
        await self.create()
        async with unit_of_work() as session:
            row=await session.scalar(select(EditalUnit).where(EditalUnit.analysis_id==store.uuid(self.identity)))
            original_id=row.id;row.source_blocks=[*row.source_blocks,'p0001-b0002']
            analysis=await store.owned_analysis(session,self.uid,self.identity,source=True)
            pages=json.loads(json.dumps(analysis.pages))
            pages[0]['blocks'].append({**pages[0]['blocks'][0],'id':'p0001-b0002','text':'Segundo bloco real preservado, nunca enviado no diagnóstico.'})
            analysis.pages=pages
        await self.resume(mode='pilot',diagnostic_case='json')
        def transport(request):return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{'}]}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            handler=IncrementalHandler(AIRouter(providers={'gemini':GeminiProvider(client)}),
                SimpleNamespace(get=AsyncMock(return_value={'gemini':'synthetic-only'})),AsyncMock())
            self.assertTrue(await handler.run_one());self.assertFalse(await handler.run_one())
        async with unit_of_work() as session:
            rows=(await session.scalars(select(EditalUnit).where(EditalUnit.analysis_id==store.uuid(self.identity)))).all()
            self.assertEqual(len(rows),1);self.assertEqual(rows[0].id,original_id)
            self.assertEqual(rows[0].source_blocks,['p0001-b0001','p0001-b0002'])
            self.assertEqual(rows[0].status,'waiting_provider');self.assertIsNone(rows[0].result)
        _,state,_=await self.state();self.assertEqual(state.error_kind,'malformed_output')
        self.assertFalse(state.provider_approval.pilot_validated);self.assertEqual(state.budget.reserved_attempts,1)
