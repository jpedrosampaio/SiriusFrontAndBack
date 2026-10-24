"""Real lease/checkpoint races, using synthetic sources and no AI IO."""
import asyncio
import os
import unittest
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
from sqlalchemy import select, delete, func
from db.session import unit_of_work
from db.models.identity import User
from db.models.edital_units import EditalUnit
from services import edital_pipeline_store as store, edital_pipeline_units as units
from services.edital_semantics import EvidenceError
from ai.types import AIError
import test_postgres_edital_pipeline as intake_setup
import test_postgres_agent as setup
from edital_test_helpers import persist_approved


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class DurableUnits(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = setup.PostgresAgent.asyncSetUp
    document = intake_setup.DurableEditalIntake.document

    async def asyncTearDown(self):
        async with unit_of_work() as session:
            await session.execute(delete(User).where(User.id.in_((self.uid, self.other))))
        await setup.PostgresAgent.asyncTearDown(self)

    async def intake(self, owner=None, count=1):
        document = self.document()
        original = document.pages[0].blocks[0]
        document.pages[0].blocks = [original.model_copy(update={'id': f'p0001-b{i:04d}'}) for i in range(1, count + 1)]
        document.pages[0].characters = sum(len(b.text) for b in document.pages[0].blocks)
        first = await store.reserve_intake(owner or self.uid, document.sha256, 'synthetic.pdf', False, str(uuid4()))
        return await persist_approved(owner or self.uid, first['job_id'], first['token'], document)

    def proposal(self, ids):
        return {'roles': [], 'classifications': [{'block_id': ids[0], 'end_block_id': ids[-1], 'kind': 'roles'}]}

    async def test_concurrent_claims_and_provider_fallback_budget_are_durable(self):
        result = await self.intake()
        claims = await asyncio.gather(*(units.claim_next() for _ in range(6)))
        self.assertEqual(sum(c is not None for c in claims), 1)
        claim = next(c for c in claims if c)
        model = SimpleNamespace(provider='mock', name='synthetic-no-network')
        for _ in range(2): await units.provider_attempt(claim, model)
        async with unit_of_work() as session:
            row = await store.owned_analysis(session, self.uid, result['analysis_id'], lock=True)
            state = store.manifest(row); state.budget.provider_limit = 2; store.write_manifest(row, state)
        with self.assertRaises(AIError): await units.provider_attempt(claim, model)
        await units.fail(claim, 'quota')
        self.assertIsNone(await units.claim_next())
        async with unit_of_work() as session:
            row = await store.owned_analysis(session, self.uid, result['analysis_id'])
            self.assertEqual(store.manifest(row).budget.reserved_attempts, 2)
            self.assertEqual(store.manifest(row).status, 'quota_paused')
            unit = await session.get(EditalUnit, claim.unit_id)
            self.assertEqual(unit.provider_calls, 2); self.assertEqual(len(unit.diagnostics['attempts']), 2)

    async def test_owned_source_window_complete_and_replay_fence(self):
        await self.intake(count=3); claim = await units.claim_next(); data = await units.snapshot(claim)
        self.assertEqual([b['id'] for b in data['primary']], ['p0001-b0001', 'p0001-b0002', 'p0001-b0003'])
        async with unit_of_work() as session:
            self.assertEqual(await units.source_blocks(session, self.other, claim.analysis_id, []), [])
            with self.assertRaises(EvidenceError): await units.source_blocks(session, self.other, claim.analysis_id, ['p0001-b0001'])
        await units.complete(claim, self.proposal([b['id'] for b in data['primary']]), {'prompt_tokens': 20, 'completion_tokens': 10})
        for operation in (units.renew(claim), units.complete(claim, self.proposal(['p0001-b0001'])),
                          units.provider_attempt(claim, SimpleNamespace(provider='mock', name='never'))):
            with self.assertRaises(units.LeaseLost): await operation
        self.assertIsNone(await units.claim_next())
        async with unit_of_work() as session:
            unit = await session.get(EditalUnit, claim.unit_id)
            self.assertEqual(unit.status, 'completed'); self.assertEqual(unit.attempts, 1)
            self.assertEqual(len(unit.result['classifications']), 1)

    async def test_invalid_evidence_cannot_complete_or_poison_a_checkpoint(self):
        await self.intake(); claim = await units.claim_next()
        invalid = self.proposal(['p0001-b0001'])
        invalid['roles'] = [{'name': {'value': 'Inventado', 'state': 'extracted', 'sources': [
            {'page': 1, 'block_id': 'p0001-b0001', 'quote': 'Inventado'}]}}]
        with self.assertRaises(EvidenceError): await units.complete(claim, invalid)
        async with unit_of_work() as session:
            unit = await session.get(EditalUnit, claim.unit_id)
            self.assertEqual(unit.status, 'running'); self.assertIsNone(unit.result)

    async def test_expired_worker_is_fenced_and_restart_reuses_only_unfinished_units(self):
        await self.intake(); old = await units.claim_next()
        async with unit_of_work() as session:
            (await session.get(EditalUnit, old.unit_id)).lease_until = store.utc_now() - timedelta(seconds=1)
        await units.expire_leases()
        with self.assertRaises(units.LeaseLost): await units.provider_attempt(old, SimpleNamespace(provider='mock', name='never'))
        async with unit_of_work() as session:
            (await session.get(EditalUnit, old.unit_id)).available_at = store.utc_now() - timedelta(seconds=1)
        new = await units.claim_next(); self.assertEqual(old.unit_id, new.unit_id); self.assertNotEqual(old.token, new.token)
        await units.complete(new, self.proposal(['p0001-b0001']))
        await units.expire_leases(); self.assertIsNone(await units.claim_next())

    async def test_truncated_response_splits_without_publishing_partial_or_recalling_completed_child(self):
        await self.intake(count=4); old = await units.claim_next()
        await units.fail(old, 'output_truncated')
        async with unit_of_work() as session:
            parent = await session.get(EditalUnit, old.unit_id)
            self.assertEqual(parent.status, 'split'); self.assertIsNone(parent.result)
        first = await units.claim_next(); data = await units.snapshot(first)
        self.assertEqual(len(data['primary']), 2)
        await units.complete(first, self.proposal([b['id'] for b in data['primary']]))
        second = await units.claim_next(); self.assertNotEqual(second.unit_id, first.unit_id)
        await units.fail(second, 'timeout', 1)
        self.assertIsNone(await units.claim_next())
        async with unit_of_work() as session:
            (await session.get(EditalUnit, second.unit_id)).available_at = store.utc_now() - timedelta(seconds=1)
        resumed = await units.claim_next(); self.assertEqual(resumed.unit_id, second.unit_id)
        with self.assertRaises(units.LeaseLost): await units.complete(second, self.proposal(['p0001-b0003', 'p0001-b0004']))
        data = await units.snapshot(resumed)
        await units.complete(resumed, self.proposal([b['id'] for b in data['primary']]))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(EditalUnit).where(
                EditalUnit.user_id == self.uid, EditalUnit.status == 'completed')), 2)

    async def test_busy_owner_is_filtered_before_limit_and_other_owner_can_progress(self):
        await self.intake(count=30); first = await units.claim_next()
        # More than the discovery limit from the busy owner must not starve Bob.
        async with unit_of_work() as session:
            source = await session.get(EditalUnit, first.unit_id)
            for index in range(15):
                session.add(EditalUnit(user_id=self.uid, analysis_id=source.analysis_id, job_id=source.job_id,
                    generation=source.generation, scope_key='inventory', kind='inventory', unit_key=f'{index:064x}',
                    source_blocks=['p0001-b0001'], context_blocks=[]))
        other = await self.intake(self.other)
        claim = await units.claim_next()
        self.assertEqual(claim.user_id, self.other); self.assertEqual(str(claim.analysis_id), other['analysis_id'])

    async def test_generation_change_and_cancellation_fence_previously_running_worker(self):
        result = await self.intake(); claim = await units.claim_next()
        async with unit_of_work() as session:
            row = await store.owned_analysis(session, self.uid, result['analysis_id'], lock=True)
            state = store.manifest(row); state.status = 'cancelled'; state.inventory.generation = uuid4(); store.write_manifest(row, state)
        with self.assertRaises(units.LeaseLost): await units.renew(claim)
        with self.assertRaises(units.LeaseLost): await units.complete(claim, self.proposal(['p0001-b0001']))
        self.assertIsNone(await units.claim_next())

    async def test_worker_releases_database_during_mock_provider_and_never_repeats_completed_work(self):
        from ai.types import AIResult
        from services.edital_pipeline_worker import IncrementalHandler
        await self.intake(); entered = asyncio.Event(); release = asyncio.Event(); calls = []
        async def generate(**kwargs):
            calls.append(kwargs)
            await kwargs['on_attempt'](SimpleNamespace(provider='mock', name='synthetic-no-network'))
            entered.set(); await release.wait()
            from edital_wire_fixtures import inventory_wire
            proposal=kwargs['output_type'].model_validate(inventory_wire(self.proposal(['p0001-b0001'])))
            return AIResult(provider='mock',model='synthetic-no-network',data=proposal, usage={'total_tokens': 30})
        async def credentials(uid):
            self.assertEqual(uid, str(self.uid)); return {'mock': 'synthetic-not-a-real-credential'}
        async def consolidate(session, analysis, unit, state):
            state.inventory.status = 'awaiting_review'; state.status = 'awaiting_review'
        handler = IncrementalHandler(SimpleNamespace(generate=generate), SimpleNamespace(get=credentials), consolidate)
        task = asyncio.create_task(handler.run_one())
        try:
            await asyncio.wait_for(entered.wait(), 3)
            async def another_owned_transaction():
                async with unit_of_work() as session:
                    await session.scalar(select(User).where(User.id == self.uid).with_for_update())
            await asyncio.wait_for(another_owned_transaction(), 1)
        finally:
            release.set(); await task
        self.assertEqual(len(calls), 1); self.assertEqual(calls[0]['max_tokens'], 3072)
        self.assertNotIn('pages', calls[0]['prompt'])
        self.assertFalse(await handler.run_one()); self.assertEqual(len(calls), 1)
        async with unit_of_work() as session:
            completed=await session.scalar(select(EditalUnit).where(EditalUnit.user_id==self.uid))
            self.assertEqual(completed.diagnostics['completed_model']['model'],'synthetic-no-network')
            self.assertRegex(completed.diagnostics['attempts'][0]['input_hash'],r'^[0-9a-f]{64}$')

    async def test_worker_truncation_splits_without_saving_unvalidated_partial_json(self):
        from services.edital_pipeline_worker import IncrementalHandler
        await self.intake(count=4)
        async def generate(**kwargs):
            await kwargs['on_attempt'](SimpleNamespace(provider='mock', name='synthetic-no-network'))
            raise AIError('output_truncated')
        async def credentials(uid): return {'mock': 'synthetic-not-a-real-credential'}
        handler = IncrementalHandler(SimpleNamespace(generate=generate), SimpleNamespace(get=credentials), None)
        self.assertTrue(await handler.run_one())
        async with unit_of_work() as session:
            rows = (await session.scalars(select(EditalUnit).where(EditalUnit.user_id == self.uid))).all()
            self.assertEqual(sorted(r.status for r in rows), ['pending', 'pending', 'split'])
            self.assertTrue(all(r.result is None for r in rows))
