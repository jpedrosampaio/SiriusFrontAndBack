import os
import asyncio
import unittest
from datetime import date,datetime,timezone,timedelta
from decimal import Decimal
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.reports import Report
from db.models.planning import Task,TaskInstance,Habit,HabitCheck
from db.models.finance import FinancialTransaction
from db.models.studies import StudySession,QuestionAttempt
from db.models.health import WorkoutLog,Meal,WaterLog
from report_metrics import period_metrics
import test_postgres_runtime_nutrition as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeReports(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeNutrition.ok
    asyncTearDown=setup.RuntimeNutrition.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeNutrition.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.llm=AsyncMock(return_value='Report insight')
        extra=[patch('services.reports.account',account),patch('services.reports._llm',self.llm)]
        for p in extra:p.start()
        self.patches.extend(extra)

    async def test_report_full_history_date_and_owner(self):
        day=date(2026,9,25);instant=datetime(2026,9,25,15,tzinfo=timezone.utc)
        async with unit_of_work() as session:
            tasks=[Task(user_id=self.uid,title='Task',date=day,xp_reward=5,created_at=instant) for _ in range(1005)]
            session.add_all(tasks);habit=Habit(user_id=self.uid,name='Habit');session.add(habit);await session.flush()
            session.add(HabitCheck(user_id=self.uid,habit_id=habit.id,date=day,checked_at=instant))
            session.add(HabitCheck(user_id=self.uid,habit_id=habit.id,date=day-timedelta(days=1),checked_at=instant))
            session.add_all([TaskInstance(user_id=self.uid,task_id=t.id,date=day,status='done',completed=True) for t in tasks])
            for uid,record_day,count in [(self.uid,day,1005),(self.uid,day-timedelta(days=1),1),(self.bob,day,1)]:
                when=datetime.combine(record_day,instant.timetz())
                for _ in range(count):
                    session.add_all([FinancialTransaction(user_id=uid,date=record_day,type='income',amount=Decimal('2.00'),category='income'),
                        StudySession(user_id=uid,date=record_day,duration_minutes=3,completed=True),
                        StudySession(user_id=uid,date=record_day,duration_minutes=5,completed=True,source='focus'),
                        QuestionAttempt(user_id=uid,answered_at=when,total=4,correct=3,source='manual'),
                        WorkoutLog(user_id=uid,date=record_day,name='Workout',activity_type='walking',duration_minutes=10,completed=True),
                        Meal(user_id=uid,date=record_day,name='Meal',meal_type='lunch',reported_calories=100),
                        WaterLog(user_id=uid,date=record_day,amount_ml=200)])
            session.add(QuestionAttempt(user_id=self.uid,answered_at=datetime(2026,9,26,2,30,tzinfo=timezone.utc),total=1,correct=1,source='manual'))
            session.add(QuestionAttempt(user_id=self.uid,answered_at=datetime(2026,9,25,2,30,tzinfo=timezone.utc),total=1,correct=1,source='manual'))
            session.add(QuestionAttempt(user_id=self.uid,answered_at=instant,total=1,correct=0,source='exam',evidence={'answered':False}))
        values=await period_metrics(self.uid,day,day)
        self.assertEqual(values['income'],Decimal('2010.00'));self.assertIsInstance(values['income'],Decimal)
        self.assertEqual(values['study_minutes'],8040);self.assertEqual(values['workouts'],1005)
        self.assertEqual(values['tasks_completed'],1005);self.assertEqual(values['tasks'],1005)
        self.assertEqual(values['questions_correct'],3016);self.assertEqual(values['questions_answered'],4021)
        self.assertEqual(values['calories'],100500);self.assertEqual(values['water_ml'],201000);self.assertEqual(values['total_habits_completions'],1)

    async def test_report_snapshot_replay_download_filter_and_rollback(self):
        async with unit_of_work() as session:
            session.add(FinancialTransaction(user_id=self.uid,date=self.today,type='expense',amount=Decimal('48.01'),category='food'))
        query={'report_type':'daily','period':'ignored'}
        values=[self.ok(r) for r in await asyncio.gather(*(self.http.post('/api/reports/generate',params=query,headers={'Idempotency-Key':'daily-report-001'}) for _ in range(5)))]
        self.assertEqual(len({v['report_id'] for v in values}),1);self.assertEqual(values[0]['data']['expenses'],48.01)
        rows=self.ok(await self.http.get('/api/reports'));self.assertEqual(len(rows),1)
        self.assertEqual(self.ok(await self.http.get('/api/reports',params={'type':'monthly'})),[])
        foreign={'Authorization':'Bearer bob'}
        self.assertEqual(self.ok(await self.http.get('/api/reports',headers=foreign)),[])
        path='/api/reports/'+rows[0]['report_id']+'/download'
        self.assertEqual((await self.http.get(path,headers=foreign)).status_code,404)
        self.assertIn('48.01',(await self.http.get(path)).text)
        with patch('services.reports.report_json',side_effect=RuntimeError('after flush')):
            with self.assertRaises(RuntimeError):await self.http.post('/api/reports/generate',params=query)
        async with unit_of_work() as session:
            report=await session.scalar(select(Report).where(Report.user_id==self.uid));self.assertEqual(report.expenses,Decimal('48.01'))
            self.assertEqual(await session.scalar(select(func.count()).select_from(Report).where(Report.user_id==self.uid)),1)
        self.assertEqual((await self.http.post('/api/reports/generate',params={'report_type':'sprint','start':'2026-10-02','end':'2026-10-01'})).status_code,422)
