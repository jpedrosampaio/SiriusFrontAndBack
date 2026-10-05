import asyncio
import os
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import patch
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func
from db.models.agent import Action, ActionAudit, Event
from db.models.finance import FinancialTransaction
from db.models.planning import Task, CalendarEvent
from db.models.studies import StudyArea, Notebook, StudySession
from db.models.identity import User
from db.session import unit_of_work
from ai.routes import AgentRuntime
import test_postgres_agent as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class RuntimeAgentActions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await setup.PostgresAgent.asyncSetUp(self)
        async def auth(authorization=None, session_token=None):
            return SimpleNamespace(user_id=str(self.other if authorization=='Bearer bob' else self.uid))
        with patch.dict(os.environ, {'AI_AGENT_ENABLED':'true'}):
            self.runtime = AgentRuntime(object(), auth, None, None, None)
        app = FastAPI(); app.include_router(self.runtime.api)
        self.http = AsyncClient(transport=ASGITransport(app), base_url='https://sirius.test')

    async def asyncTearDown(self):
        await self.http.aclose()
        await setup.PostgresAgent.asyncTearDown(self)

    def ok(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def propose(self, request='request-one', name='record_expense', arguments=None):
        return await self.runtime.actions.propose(str(self.uid), request, 0, name,
            arguments or {'amount':'48.00','category':'food','date':'2026-10-01'}, 'User asked')

    async def test_real_routes_concurrent_48_receipt_audit_owner_and_preferences(self):
        proposals = await asyncio.gather(*(self.propose() for _ in range(5)))
        aid = proposals[0]['action_id']
        self.assertEqual(len({p['action_id'] for p in proposals}), 1)
        self.assertEqual((await self.http.post(f'/ai/actions/{aid}/confirm', headers={'Authorization':'Bearer bob'})).status_code, 404)
        results = [self.ok(r) for r in await asyncio.gather(*(self.http.post(f'/ai/actions/{aid}/confirm') for _ in range(8)))]
        self.assertEqual(sum(bool(r.get('replayed')) for r in results), 7)
        async with unit_of_work() as session:
            self.assertEqual(list((await session.scalars(select(FinancialTransaction.amount).where(FinancialTransaction.user_id==self.uid))).all()), [Decimal('48.00')])
            for model in (ActionAudit, Event):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)), 1)
        self.assertEqual(self.ok(await self.http.get('/ai/actions'))[0]['status'], 'executed')
        self.assertEqual(self.ok(await self.http.get('/ai/actions', headers={'Authorization':'Bearer bob'})), [])
        policy = self.ok(await self.http.get('/ai/preferences')); policy['blocked_tools']=['record_expense']
        other = await self.propose('next-proposal')
        self.ok(await self.http.put('/ai/preferences', json=policy))
        self.assertEqual((await self.http.post(f"/ai/actions/{other['action_id']}/confirm")).status_code, 403)
        self.assertEqual(self.ok(await self.http.get('/ai/preferences', headers={'Authorization':'Bearer bob'}))['blocked_tools'], [])
        policy['blocked_tools']=['not-a-tool']
        self.assertEqual((await self.http.put('/ai/preferences', json=policy)).status_code, 422)
        self.assertEqual((await self.http.post('/ai/actions/invalid/confirm')).status_code, 404)

    async def test_rollback_cancel_expiry_and_tool_version(self):
        action = await self.propose(); aid=action['action_id']
        original = self.runtime.actions.writer.execute
        async def failing(*args):
            await original(*args)
            raise RuntimeError('after expense')
        with patch.object(self.runtime.actions.writer, 'execute', failing):
            with self.assertRaises(RuntimeError): await self.http.post(f'/ai/actions/{aid}/confirm')
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id==self.uid)), 0)
            self.assertEqual((await session.get(Action, UUID(aid))).status, 'pending')
        self.ok(await self.http.post(f'/ai/actions/{aid}/cancel'))
        self.assertEqual((await self.http.post(f'/ai/actions/{aid}/confirm')).status_code, 409)
        expired = await self.propose('expired')
        async with unit_of_work() as session:
            row = await session.get(Action, UUID(expired['action_id'])); row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        self.assertEqual((await self.http.post(f"/ai/actions/{expired['action_id']}/confirm")).status_code, 409)
        values = self.ok(await self.http.get('/ai/actions'))
        self.assertEqual(next(r['status'] for r in values if r['action_id']==expired['action_id']), 'expired')
        changed = await self.propose('changed')
        async with unit_of_work() as session:
            row = await session.get(Action, UUID(changed['action_id'])); row.version=999
        self.assertEqual((await self.http.post(f"/ai/actions/{changed['action_id']}/confirm")).status_code, 409)

    async def test_task_calendar_and_invalid_notebook_writes(self):
        task = await self.propose('task', 'create_task', {'title':'Owned', 'date':'2026-10-01'})
        self.ok(await self.http.post(f"/ai/actions/{task['action_id']}/confirm"))
        args = {'title':'Appointment', 'date':'2026-10-01', 'start_minute':600, 'end_minute':660}
        event = await self.propose('calendar', 'create_calendar_event', args)
        self.ok(await self.http.post(f"/ai/actions/{event['action_id']}/confirm"))
        clash = await self.propose('clash', 'create_calendar_event', args)
        self.assertEqual((await self.http.post(f"/ai/actions/{clash['action_id']}/confirm")).status_code, 409)
        bad = await self.propose('bad-notebook', 'record_study_session', {'notebook_id':'invalid', 'duration_minutes':30, 'date':'2026-10-01'})
        self.assertEqual((await self.http.post(f"/ai/actions/{bad['action_id']}/confirm")).status_code, 404)
        async with unit_of_work() as session:
            for model in (Task, CalendarEvent):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)), 1)

    async def test_study_confirmation_owns_notebook_awards_once_and_refreshes_actions(self):
        async with unit_of_work() as session:
            area = StudyArea(user_id=self.uid, name='Study'); session.add(area); await session.flush()
            book = Notebook(user_id=self.uid, area_id=area.id, name='Notebook'); session.add(book); await session.flush()
            nid = str(book.id)
        args = {'notebook_id':nid, 'duration_minutes':30, 'date':'2026-10-01'}
        action = await self.propose('study', 'record_study_session', args)
        self.ok(await self.http.post(f"/ai/actions/{action['action_id']}/confirm"))
        self.ok(await self.http.post(f"/ai/actions/{action['action_id']}/confirm"))
        live = await self.runtime.actions.by_ids(self.uid, [action['action_id'], 'invalid'])
        self.assertEqual(live[0]['status'], 'executed')
        self.assertEqual(await self.runtime.actions.by_ids(self.other, [action['action_id']]), [])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudySession).where(StudySession.user_id==self.uid)), 1)
            self.assertEqual((await session.get(User, self.uid)).xp, 20)
        foreign = await self.runtime.actions.propose(self.other, 'foreign', 0, 'record_study_session', args, 'User asked')
        response = await self.http.post(f"/ai/actions/{foreign['action_id']}/confirm", headers={'Authorization':'Bearer bob'})
        self.assertEqual(response.status_code, 404)
