"""Explicit pilot, recovery and budget fences against disposable PostgreSQL only."""
import os
import unittest
from types import SimpleNamespace
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select,delete
from db.session import unit_of_work
from db.models.identity import User
from db.models.edital_units import EditalUnit
from services import (edital_pipeline_store as store,edital_pipeline_units as units,
    edital_pipeline_controls as controls,edital_pipeline_progress as progress,edital_pipeline_budget as budget)
from ai.types import AIError
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

    async def create(self,legacy=False):
        doc=self.document();reserved=await store.reserve_intake(self.uid,doc.sha256,'synthetic.pdf',False,str(uuid4()))
        accepted=await store.persist_input(self.uid,reserved['job_id'],reserved['token'],doc)
        self.identity=accepted['analysis_id']
        if legacy:
            async with unit_of_work() as session:
                row=await store.owned_analysis(session,self.uid,self.identity,lock=True)
                state=store.manifest(row);state.status=state.inventory.status='processing';state.budget.reserved_attempts=5
                base=await session.scalar(select(EditalUnit).where(EditalUnit.analysis_id==row.id))
                base.attempts=3;base.provider_calls=5;base.diagnostics={**base.diagnostics,'attempts':[{'provider':'gemini','model':'legacy','at':'2026-10-20'}]}
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

    async def test_http400_is_correlated_preserves_input_and_never_autoretries(self):
        await self.create();await self.resume(mode='pilot');claim=await units.claim_next()
        await units.provider_attempt(claim,SimpleNamespace(provider='gemini',name='mock'))
        error=AIError('invalid_request',http_status=400,incompatibility='schema_rejected',attempted=True)
        await units.fail(claim,error.kind,error=error)
        self.assertIsNone(await units.claim_next())
        _,state,_=await self.state();self.assertEqual(state.budget.reserved_attempts,1)
        self.assertFalse(state.provider_approval.pilot_validated)
        async with unit_of_work() as session:
            row=await session.get(EditalUnit,claim.unit_id)
            self.assertEqual(row.diagnostics['reference'],error.reference)
            self.assertEqual(row.diagnostics['last_failure']['http_status'],400)
            self.assertIsNone(row.result)
            analysis=await store.owned_analysis(session,self.uid,self.identity,source=True)
            self.assertEqual(analysis.pages[0]['blocks'][0]['text'],self.document().pages[0].blocks[0].text)
