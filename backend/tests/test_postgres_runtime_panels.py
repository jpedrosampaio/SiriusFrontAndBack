import os
import json
import asyncio
import unittest
from datetime import datetime,time,timedelta,timezone
from decimal import Decimal
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.planning import Task,TaskInstance,Habit,HabitCheck
from db.models.finance import FinancialTransaction,Budget
from db.models.studies import StudySession
from db.models.health import WorkoutLog,Meal
from db.models.reports import DailySummary
import test_postgres_runtime_dashboard as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimePanels(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeDashboard.ok
    asyncTearDown=setup.RuntimeDashboard.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeDashboard.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),
            'timezone':'America/Sao_Paulo','name':'User','xp':0,'rank':'Recruta'}
        self.llm=AsyncMock(side_effect=RuntimeError('offline'))
        extra=[patch(module+'.account',account) for module in ('services.dashboard_panels','services.daily_briefing','services.workout_plan_routes')]
        extra.append(patch('services.daily_briefing.call_llm',self.llm))
        for p in extra:p.start()
        self.patches.extend(extra)

    async def test_all_panels_empty_and_daily_cache_fallback_expiry_and_owner(self):
        result=self.ok(await self.http.get('/api/dashboard/panels'))
        self.assertEqual(result['errors'],[]);self.assertEqual(set(result['panels']),{'weekly','reminders','streaks','daily','workout'})
        self.assertEqual(result['panels']['daily']['summary']['score'],0);self.assertFalse(result['panels']['workout']['scheduled'])
        self.assertEqual(result['panels']['streaks']['current_streak'],0);self.assertEqual(self.llm.await_count,1)
        self.ok(await self.http.get('/api/dashboard/daily-summary'));self.assertEqual(self.llm.await_count,1)
        async with unit_of_work() as session:
            row=await session.scalar(select(DailySummary).where(DailySummary.user_id==self.uid));row.updated_at=datetime.now(timezone.utc)-timedelta(hours=5)
        self.llm.side_effect=None;self.llm.return_value=json.dumps({'greeting':'Hello','progress_summary':'Empty','pending_items':[],'motivation':'Go','priority_action':'Study','score':20})
        values=[self.ok(r) for r in await asyncio.gather(*(self.http.get('/api/dashboard/daily-summary') for _ in range(5)))]
        self.assertTrue(all(v['summary']['greeting']=='Hello' for v in values))
        async with unit_of_work() as session:self.assertEqual(await session.scalar(select(func.count()).select_from(DailySummary).where(DailySummary.user_id==self.uid)),1)
        foreign=self.ok(await self.http.get('/api/dashboard/daily-summary',headers={'Authorization':'Bearer bob'}))
        self.assertEqual(foreign['user_id'],str(self.bob))

    async def test_weekly_reminders_streaks_and_daily_read_current_sql_facts(self):
        now=datetime.combine(self.today,time(15),timezone.utc)
        async with unit_of_work() as session:
            task=Task(user_id=self.uid,title='Today task',date=self.today,recurrence='daily',xp_reward=5)
            habit=Habit(user_id=self.uid,name='Habit',created_at=now-timedelta(days=7));session.add_all([task,habit]);await session.flush()
            session.add_all([Task(user_id=self.uid,title='Future task',date=self.today+timedelta(days=1),recurrence='once',xp_reward=5),
                Task(user_id=self.uid,title='Overdue',date=self.today-timedelta(days=8),recurrence='once',xp_reward=5),
                TaskInstance(user_id=self.uid,task_id=task.id,date=self.today,status='done',completed=True),
                Budget(user_id=self.uid,category='food',month=self.today.replace(day=1),limit=Decimal('500')),
                StudySession(user_id=self.uid,date=self.today,duration_minutes=25,completed=True,source='focus'),
                WorkoutLog(user_id=self.uid,date=self.today,activity_type='walking',name='Done',duration_minutes=30,completed=True),
                WorkoutLog(user_id=self.uid,date=self.today,activity_type='walking',name='Not done',duration_minutes=50,completed=False),
                WorkoutLog(user_id=self.uid,date=self.today+timedelta(days=1),activity_type='walking',name='Future',duration_minutes=90,completed=True),
                Meal(user_id=self.uid,date=self.today,name='Lunch',meal_type='lunch',reported_calories=500)])
            session.add_all([HabitCheck(user_id=self.uid,habit_id=habit.id,date=self.today-timedelta(days=delta),checked_at=now) for delta in (1,2,3)])
            session.add_all([FinancialTransaction(user_id=self.uid,date=self.today,type='expense',amount=Decimal('1'),category='food') for _ in range(501)])
        result=self.ok(await self.http.get('/api/dashboard/panels'));self.assertEqual(result['errors'],[])
        weekly=result['panels']['weekly'];self.assertEqual(weekly['finance']['expense'],501);self.assertEqual(weekly['finance']['transactions_count'],501)
        self.assertEqual(weekly['tasks']['total'],1);self.assertEqual(weekly['tasks']['completed'],1)
        self.assertEqual(weekly['workouts']['total_minutes'],30);self.assertEqual(weekly['study']['total_minutes'],25)
        types={r['type'] for r in result['panels']['reminders']['reminders']};self.assertTrue({'finance','habit','task'}<=types)
        streak=result['panels']['streaks'];self.assertEqual(streak['current_streak'],4);self.assertEqual(streak['module_streaks']['habits'],3)
        daily=result['panels']['daily']['raw_data'];self.assertEqual(daily['tasks_done'],1);self.assertEqual(daily['tasks_pending'],0)
        self.assertEqual(daily['study_minutes'],25);self.assertEqual(daily['workouts_count'],1);self.assertEqual(daily['calories'],500)
        self.assertNotIn('Future task',self.llm.call_args.args[0])
        other=self.ok(await self.http.get('/api/dashboard/weekly-summary',headers={'Authorization':'Bearer bob'}));self.assertEqual(other['finance']['expense'],0)
