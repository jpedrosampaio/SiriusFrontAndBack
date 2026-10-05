import asyncio
import os
import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.agent import Event,Insight,Usage
from db.models.finance import Budget,FinancialTransaction
from services.agent_automations import claim,finish
from services.ai_usage import internal_today,gemini_today
from services.time import local_today
from ai.config import MODELS
import test_postgres_runtime_agent_actions as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class AgentAutomations(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=setup.RuntimeAgentActions.asyncSetUp
    asyncTearDown=setup.RuntimeAgentActions.asyncTearDown
    ok=setup.RuntimeAgentActions.ok

    async def enable(self,cap=3):
        return self.ok(await self.http.put('/ai/preferences',json={'automations':True,'quiet_start':0,'quiet_end':0,'daily_cap':cap}))

    async def test_internal_quota_is_atomic_separate_from_reported_provider_usage(self):
        self.runtime.settings.daily_limit=3
        async with unit_of_work() as session:
            session.add(Usage(user_id=self.uid,provider='gemini',model=MODELS['flash'].name,task='internal_reservation',status='reserved',duration_ms=0,
                created_at=datetime.now(timezone.utc)-timedelta(days=1)))
        values=await asyncio.gather(*(self.runtime.reserve(str(self.uid),MODELS['flash']) for _ in range(12)))
        self.assertEqual(sum(values),3)
        self.assertEqual(await internal_today(self.uid),3)
        self.assertEqual(await internal_today(self.other),0)
        self.assertEqual(await gemini_today(self.uid),{})
        status=self.ok(await self.http.get('/ai/status'));self.assertEqual(status['internal_requests_today'],3)

    async def test_opt_in_daily_cap_never_snooze_and_owner(self):
        now=datetime(2026,10,5,15,tzinfo=timezone.utc)
        worker=self.runtime.automations
        self.assertIsNone(await worker.suggest(self.uid,'rule','Title',{},'/tasks',now))
        await self.enable(2)
        values=await asyncio.gather(*(worker.suggest(self.uid,'rule'+str(i),'Title',{},'/tasks',now) for i in range(6)))
        self.assertEqual(sum(v is not None for v in values),2)
        rows=self.ok(await self.http.get('/ai/insights'));self.assertEqual(len(rows),2)
        sid=rows[0]['insight_id'];rule=rows[0]['rule']
        self.assertEqual(self.ok(await self.http.get('/ai/insights',headers={'Authorization':'Bearer bob'})),[])
        self.assertEqual((await self.http.post(f'/ai/insights/{sid}/feedback',json={'feedback':'never'},headers={'Authorization':'Bearer bob'})).status_code,404)
        self.ok(await self.http.post(f'/ai/insights/{sid}/feedback',json={'feedback':'never'}))
        self.assertIsNone(await worker.suggest(self.uid,rule,'Again',{},'/tasks',now+timedelta(days=1)))
        second=rows[1]['insight_id']
        self.ok(await self.http.post(f'/ai/insights/{second}/feedback',json={'feedback':'snooze'}))
        self.assertEqual(self.ok(await self.http.get('/ai/insights')),[])
        async with unit_of_work() as session:
            row=await session.get(Insight,UUID(second));row.snoozed_until=datetime.now(timezone.utc)-timedelta(seconds=1)
        self.assertEqual(len(self.ok(await self.http.get('/ai/insights'))),1)
        prefs=await self.enable();prefs.update(quiet_start=11,quiet_end=14)
        self.ok(await self.http.put('/ai/preferences',json=prefs))
        self.assertIsNone(await worker.suggest(self.uid,'quiet','Title',{},'/tasks',now+timedelta(days=1)))

    async def test_event_dedup_claim_takeover_and_budget_process_only_suggests(self):
        await self.enable()
        worker=self.runtime.automations
        await asyncio.gather(*(worker.emit(self.uid,'finance.expense.created','expense-1') for _ in range(6)))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Event).where(Event.user_id==self.uid)),1)
            day=local_today('America/Sao_Paulo')
            session.add(Budget(user_id=self.uid,month=day.replace(day=1),category='food',limit=Decimal('100.00')))
            session.add(FinancialTransaction(user_id=self.uid,type='expense',amount=Decimal('80.00'),category='food',date=day))
        claims=await asyncio.gather(*(claim(self.uid) for _ in range(4)))
        event=next(e for e in claims if e);self.assertEqual(sum(e is not None for e in claims),1)
        async with unit_of_work() as session:
            row=await session.get(Event,UUID(event['event_id']));row.lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)
        fresh=await claim(self.uid);self.assertNotEqual(fresh['lease_token'],event['lease_token'])
        self.assertFalse(await finish(event))
        await worker.process(fresh);await worker.process(fresh)
        self.assertTrue(await finish(fresh));self.assertIsNone(await claim(self.uid))
        insights=self.ok(await self.http.get('/ai/insights'));self.assertEqual(len(insights),1)
        self.assertEqual(insights[0]['evidence']['spent'],'80.00')
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id==self.uid)),1)
