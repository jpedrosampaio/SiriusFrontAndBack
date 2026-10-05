import os
import asyncio
import unittest
from datetime import datetime,time,timezone
from decimal import Decimal
from sqlalchemy import select,func
from db.models.planning import Task,TaskInstance,Habit,HabitCheck,XPEntry
from db.models.finance import FinancialTransaction
from db.models.studies import StudySession,QuestionAttempt
from db.models.health import WorkoutLog
from db.models.identity import User
from db.session import unit_of_work
from db.activity import run_activity
from services.planning import set_task_completion,apply_xp
import test_postgres_runtime_dashboard as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeAnalytics(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeDashboard.ok
    asyncTearDown=setup.RuntimeDashboard.asyncTearDown

    async def asyncSetUp(self):await setup.RuntimeDashboard.asyncSetUp(self)

    async def test_analytics_contract_full_history_owner_and_period(self):
        now=datetime.combine(self.today,time(15),timezone.utc)
        async with unit_of_work() as session:
            task=Task(user_id=self.uid,title='Task',date=self.today,xp_reward=5);habit=Habit(user_id=self.uid,name='Habit')
            session.add_all([task,habit]);await session.flush()
            session.add_all([TaskInstance(user_id=self.uid,task_id=task.id,date=self.today,status='done',completed=True),
                HabitCheck(user_id=self.uid,habit_id=habit.id,date=self.today,checked_at=now),
                FinancialTransaction(user_id=self.uid,date=self.today,type='income',amount=Decimal('2.25'),category='income'),
                StudySession(user_id=self.uid,date=self.today,duration_minutes=20,completed=True),
                WorkoutLog(user_id=self.uid,date=self.today,activity_type='walking',name='Workout',duration_minutes=40),
                QuestionAttempt(user_id=self.uid,answered_at=now,total=10,correct=7,source='manual'),XPEntry(user_id=self.uid,date=self.today,amount=5),
                FinancialTransaction(user_id=self.bob,date=self.today,type='income',amount=Decimal('9999'),category='income')])
            session.add_all([FinancialTransaction(user_id=self.uid,date=self.today,type='income',amount=Decimal('1'),category='income') for _ in range(5005)])
        result=self.ok(await self.http.get('/api/stats/analytics',params={'days':7}))
        self.assertEqual(result['totals'],{'tasks':1,'habits_avg':0.1,'income':5007.25,'expenses':0,'study_hours':0.3,'workouts':1,'questions':10,'xp_earned':5})
        self.assertEqual(result['data'][-1],{'date':self.today.isoformat(),'label':self.today.isoformat()[5:],'tasks':1,'habits':1,'habits_total':1,
            'income':5007.25,'expenses':0,'balance':5007.25,'study_min':20,'workouts':1,'workout_min':40,'questions':10,'correct':7,'xp':5,'xp_cumulative':5})
        self.assertEqual(len(result['data']),7);self.assertEqual(result['data'][0]['income'],0)
        self.assertEqual((await self.http.get('/api/stats/analytics',params={'days':0})).status_code,422)
        self.assertEqual(self.ok(await self.http.get('/api/stats/analytics',params={'days':100}))['days'],90)
        other=self.ok(await self.http.get('/api/stats/analytics',headers={'Authorization':'Bearer bob'}))
        self.assertEqual(other['totals']['income'],9999);self.assertEqual(other['totals']['tasks'],0)

    async def test_xp_ledger_atomic_replay_undo_and_rollback(self):
        async with unit_of_work() as session:
            task=Task(user_id=self.uid,title='Task',date=self.today,xp_reward=5);session.add(task);await session.flush();tid=task.id
        await asyncio.gather(*(set_task_completion(self.uid,tid,self.today,'done','analytics-xp-done') for _ in range(6)))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(XPEntry).where(XPEntry.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,5)
        await set_task_completion(self.uid,tid,self.today,'todo','analytics-xp-undo')
        async def fail(session,user):apply_xp(user,50);await session.flush();raise RuntimeError('rollback XP')
        with self.assertRaises(RuntimeError):await run_activity(self.uid,'analytics-xp-fail',['fail'],fail)
        result=self.ok(await self.http.get('/api/stats/analytics'))
        self.assertEqual(result['totals']['xp_earned'],0)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(XPEntry).where(XPEntry.user_id==self.uid)),2)
            self.assertEqual((await session.get(User,self.uid)).xp,0)
