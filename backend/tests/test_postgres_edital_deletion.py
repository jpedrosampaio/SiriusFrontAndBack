"""Owned deletion races against durable intake/workers; synthetic PostgreSQL only."""
import asyncio
import os
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select, func

from ai.types import AIResult
from db.models.edital_units import EditalUnit
from db.models.files import EditalAnalysis, EditalJob
from db.session import unit_of_work
from services import edital_analyses as analyses, edital_pipeline_units as units
from services.edital_pipeline_worker import IncrementalHandler
import test_postgres_edital_pipeline as intake_setup
from edital_test_helpers import persist_approved


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class OwnedAnalysisDeletion(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = intake_setup.DurableEditalIntake.asyncSetUp
    asyncTearDown = intake_setup.DurableEditalIntake.asyncTearDown
    document = intake_setup.DurableEditalIntake.document
    reserve = intake_setup.DurableEditalIntake.reserve

    async def intake(self, owner=None, digest=None):
        document = self.document()
        if digest: document = document.model_copy(update={'sha256': digest})
        first = await self.reserve(owner=owner, document=document)
        return await persist_approved(owner or self.uid, first['job_id'], first['token'], document)

    def proposal(self):
        return {'roles': [], 'classifications': [
            {'block_id': 'p0001-b0001', 'end_block_id': 'p0001-b0001', 'kind': 'roles'}]}

    async def test_deleting_two_queued_analyses_releases_capacity_without_touching_other_owner(self):
        first = await self.intake()
        second = await self.intake(digest='a' * 64)
        other = await self.intake(owner=self.other)
        with self.assertRaises(HTTPException) as error:
            await self.reserve(document=self.document().model_copy(update={'sha256': 'b' * 64}))
        self.assertEqual(error.exception.detail['code'], 'analysis_concurrency')
        for result in (first, second):
            self.assertEqual((await analyses.remove(self.uid, result['analysis_id']))['deleted_count'], 1)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(EditalUnit)
                .where(EditalUnit.user_id == self.uid)), 0)
            for result in (first, second):
                job = await session.get(EditalJob, UUID(result['job_id']))
                self.assertEqual(job.status, 'failed')
                self.assertIsNone(job.analysis_id)
                self.assertIsNone(job.lease_token)
                self.assertIsNone(job.lease_until)
                self.assertIsNotNone(job.finished_at)
            self.assertEqual((await session.get(EditalJob, UUID(other['job_id']))).status, 'queued')
            self.assertIsNotNone(await session.get(EditalAnalysis, UUID(other['analysis_id'])))
        self.assertEqual((await self.intake())['action'], 'accepted')

    async def test_foreign_deletion_is_rejected_and_deleted_running_claim_is_fenced(self):
        result = await self.intake()
        claim = await units.claim_next()
        with self.assertRaises(HTTPException) as error:
            await analyses.remove(self.other, result['analysis_id'])
        self.assertEqual(error.exception.status_code, 404)
        await units.renew(claim)
        await analyses.remove(self.uid, result['analysis_id'])
        for operation in (
            lambda: units.renew(claim), lambda: units.snapshot(claim),
            lambda: units.provider_attempt(claim, SimpleNamespace(provider='mock', name='synthetic')),
            lambda: units.complete(claim, self.proposal()), lambda: units.fail(claim, 'network_error'),
        ):
            with self.assertRaises(units.LeaseLost): await operation()
        async with unit_of_work() as session:
            job = await session.get(EditalJob, claim.job_id)
            self.assertEqual(job.status, 'failed')
            self.assertIsNone(job.lease_token)
            self.assertIsNone(job.lease_until)
        self.assertIsNone(await units.claim_next())

    async def test_deleted_analysis_discards_inflight_mock_provider_result_without_worker_error(self):
        result = await self.intake()
        entered = asyncio.Event(); release = asyncio.Event(); consolidated = AsyncMock()

        async def generate(**kwargs):
            await kwargs['on_attempt'](SimpleNamespace(provider='mock', name='synthetic'))
            entered.set(); await release.wait()
            return AIResult(provider='mock', model='synthetic', data=self.proposal())

        handler = IncrementalHandler(SimpleNamespace(generate=generate),
            SimpleNamespace(get=AsyncMock(return_value={'mock': 'test-only'})), consolidated)
        task = asyncio.create_task(handler.run_one())
        try:
            await asyncio.wait_for(entered.wait(), 5)
            await analyses.remove(self.uid, result['analysis_id'])
        finally:
            release.set()
            await asyncio.wait_for(task, 5)
        consolidated.assert_not_awaited()
        async with unit_of_work() as session:
            self.assertIsNone(await session.get(EditalAnalysis, UUID(result['analysis_id'])))
            self.assertEqual((await session.get(EditalJob, UUID(result['job_id']))).status, 'failed')

    async def test_claim_discovery_tolerates_deletion_before_its_owner_lock(self):
        result = await self.intake()
        calls = 0

        @asynccontextmanager
        async def interleave_deletion():
            nonlocal calls
            calls += 1
            if calls == 2: await analyses.remove(self.uid, result['analysis_id'])
            async with unit_of_work() as session: yield session

        with patch.object(units, 'expire_leases', AsyncMock()), \
                patch.object(units, 'unit_of_work', interleave_deletion):
            self.assertIsNone(await units.claim_next())
        self.assertEqual(calls, 2)

    async def test_delete_failure_rolls_back_job_retirement_and_keeps_live_claim(self):
        result = await self.intake()
        claim = await units.claim_next()
        with patch.object(analyses, 'delete', side_effect=RuntimeError('synthetic delete failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic delete failure'):
                await analyses.remove(self.uid, result['analysis_id'])
        await units.renew(claim)
        async with unit_of_work() as session:
            job = await session.get(EditalJob, claim.job_id)
            self.assertEqual(job.status, 'running')
            self.assertEqual(job.analysis_id, claim.analysis_id)
            self.assertEqual(job.lease_token, claim.token)

    async def test_legacy_group_delete_preserves_canonical_analysis_and_completed_job_history(self):
        canonical = await self.intake()
        digest = self.document().sha256
        finished = datetime(2026, 10, 1, tzinfo=timezone.utc)
        async with unit_of_work() as session:
            older = [EditalAnalysis(user_id=self.uid, content_hash=digest, status='completed',
                analysis_version=version, structured_payload={}) for version in ('4', '5')]
            session.add_all(older); await session.flush()
            job = EditalJob(user_id=self.uid, analysis_id=older[0].id, filename='synthetic.pdf',
                storage_provider='legacy-test', content_hash=digest, status='completed',
                phase='Historical result', finished_at=finished)
            session.add(job); await session.flush()
            old_id, job_id = older[0].id, job.id
        self.assertEqual((await analyses.remove(self.uid, old_id))['deleted_count'], 2)
        async with unit_of_work() as session:
            job = await session.get(EditalJob, job_id)
            self.assertEqual(job.status, 'completed')
            self.assertEqual(job.phase, 'Historical result')
            self.assertEqual(job.finished_at, finished)
            self.assertIsNone(job.analysis_id)
            self.assertIsNotNone(await session.get(EditalAnalysis, UUID(canonical['analysis_id'])))
            self.assertEqual((await session.get(EditalJob, UUID(canonical['job_id']))).status, 'queued')
