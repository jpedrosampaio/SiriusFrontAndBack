import asyncio
import os
import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from unittest.mock import AsyncMock,patch
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.gamification import DailyQuote
from db.models.planning import Habit,HabitCheck
from db.models.finance import Budget,FinancialTransaction
import test_postgres_runtime_dashboard as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class QuotesAlerts(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeDashboard.ok
    asyncTearDown=setup.RuntimeDashboard.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeDashboard.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid)}
        p=patch('services.quotes_alerts.account',account);p.start();self.patches.append(p)

    async def test_quote_local_five_am_cache_owner_fallback_and_concurrency(self):
        instant=datetime(2026,10,5,7,59,tzinfo=timezone.utc)
        with patch('services.quotes_alerts.utc_now',return_value=instant),patch('server.call_llm',AsyncMock(return_value='Quote')) as llm:
            first=self.ok(await self.http.get('/api/motivational-quote'))
            self.assertEqual(first['motivational_date'],'2026-10-04');self.assertFalse(first['cached'])
            self.assertTrue(self.ok(await self.http.get('/api/motivational-quote'))['cached']);self.assertEqual(llm.await_count,1)
            self.assertFalse(self.ok(await self.http.get('/api/motivational-quote',headers={'Authorization':'Bearer bob'}))['cached'])
        with patch('services.quotes_alerts.utc_now',return_value=instant+timedelta(minutes=1)),patch('server.call_llm',AsyncMock(return_value='⚠ unavailable')):
            self.assertTrue(self.ok(await self.http.get('/api/motivational-quote'))['fallback'])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(DailyQuote).where(DailyQuote.user_id==self.uid)),1)
        with patch('services.quotes_alerts.utc_now',return_value=instant+timedelta(minutes=1)),patch('server.call_llm',AsyncMock(return_value='New day')):
            values=[self.ok(r) for r in await asyncio.gather(*(self.http.get('/api/motivational-quote') for _ in range(5)))]
        self.assertTrue(all(v['motivational_date']=='2026-10-05' for v in values))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(DailyQuote).where(DailyQuote.user_id==self.uid)),2)

    async def test_alerts_derived_spend_zero_limit_and_real_habit_streak(self):
        async with unit_of_work() as session:
            session.add_all([Budget(user_id=self.uid,month=self.today.replace(day=1),category='food',limit=Decimal('100.00')),
                Budget(user_id=self.uid,month=self.today.replace(day=1),category='zero',limit=Decimal('0.00')),
                FinancialTransaction(user_id=self.uid,date=self.today,type='expense',category='food',amount=Decimal('90.01')),
                FinancialTransaction(user_id=self.bob,date=self.today,type='expense',category='food',amount=Decimal('500.00')),
                FinancialTransaction(user_id=self.uid,date=self.today+timedelta(days=1),type='expense',category='food',amount=Decimal('500.00'))])
            habit=Habit(user_id=self.uid,name='Reading');session.add(habit);await session.flush()
            session.add(HabitCheck(user_id=self.uid,habit_id=habit.id,date=self.today-timedelta(days=1),checked_at=datetime.now(timezone.utc)))
        values=self.ok(await self.http.get('/api/alerts'));self.assertEqual(len(values),2)
        budget=next(v for v in values if v['type']=='budget_alert')
        self.assertEqual(budget['severity'],'warning');self.assertEqual(budget['data']['spent'],90.01)
        self.assertEqual(self.ok(await self.http.get('/api/alerts',headers={'Authorization':'Bearer bob'})),[])
