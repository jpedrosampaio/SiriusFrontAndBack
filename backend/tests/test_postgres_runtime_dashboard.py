import os
import unittest
from datetime import timedelta,datetime,timezone
from decimal import Decimal
from unittest.mock import patch
from db.models.planning import Task,TaskInstance,Goal,Habit,HabitCheck
from db.models.finance import FinancialTransaction
from db.models.studies import StudySession
from db.models.health import WorkoutLog
from db.models.exams import Exam,ExamAttempt
from db.session import unit_of_work
import test_postgres_runtime_nutrition as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeDashboard(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeNutrition.ok
    asyncTearDown=setup.RuntimeNutrition.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeNutrition.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        p=patch('services.dashboard.account',account);p.start();self.patches.append(p)

    async def test_dashboard_real_percent_applicable_tasks_full_history_and_owner(self):
        async with unit_of_work() as session:
            session.add_all([Goal(user_id=self.uid,title='One',target_date=self.today,progress=20),Goal(user_id=self.uid,title='Two',target_date=self.today,progress=80)])
            task=Task(user_id=self.uid,title='Today',date=self.today,recurrence='once',xp_reward=5);session.add(task)
            session.add(Task(user_id=self.uid,title='Tomorrow',date=self.today+timedelta(days=1),recurrence='daily',xp_reward=5))
            session.add(Task(user_id=self.uid,title='Last week',date=self.today-timedelta(days=7),recurrence='weekly',xp_reward=5))
            await session.flush();session.add(TaskInstance(user_id=self.uid,task_id=task.id,date=self.today,status='done',completed=True))
            session.add_all([FinancialTransaction(user_id=self.uid,date=self.today,type='income',amount=Decimal('1.01'),category='income') for _ in range(1005)])
            session.add(FinancialTransaction(user_id=self.bob,date=self.today,type='income',amount=Decimal('9999.99'),category='income'))
            session.add(StudySession(user_id=self.uid,date=self.today,duration_minutes=25,completed=True,source='focus'))
            session.add(StudySession(user_id=self.uid,date=self.today,duration_minutes=50,completed=False,source='focus'))
        values=self.ok(await self.http.get('/api/stats/dashboard'))
        self.assertEqual(values['goals_avg_progress'],50);self.assertEqual(values['tasks_today'],2);self.assertEqual(values['tasks_completed_today'],1)
        self.assertEqual(values['income'],'1015.05');self.assertEqual(values['study_stats']['study_time_today_minutes'],25)
        rules={s['rule'] for s in values['suggestions']};self.assertIn('tasks_pending_today',rules)
        other=self.ok(await self.http.get('/api/stats/dashboard',headers={'Authorization':'Bearer bob'}))
        self.assertEqual(other['income'],'9999.99');self.assertEqual(other['tasks_today'],0);self.assertEqual(other['study_stats']['study_time_today_minutes'],0)
        suggestions=self.ok(await self.http.get('/api/suggestions/cross-module'))
        self.assertEqual(suggestions['suggestions'],values['suggestions'])

    async def test_empty_dashboard_contract(self):
        values=self.ok(await self.http.get('/api/stats/dashboard'))
        self.assertIsNone(values['goals_avg_progress']);self.assertEqual(Decimal(values['balance']),Decimal('0'))
        self.assertIsNone(values['nutrition_stats']['calories_goal'])
        self.assertIsNone(values['simulado_stats']['accuracy_rate']);self.assertIsNone(values['simulado_stats']['average_score']);self.assertIsNone(values['question_overview']['accuracy_rate']);self.assertIsNone(values['workout_stats']['total_calories_burned'])
        self.assertEqual(values['study_stats']['current_streak'],0)
        self.assertEqual(values['suggestions'],[])

    async def test_registered_zero_unknown_partial_calories_and_planned_exclusion(self):
        async with unit_of_work() as session:
            session.add_all([WorkoutLog(user_id=self.uid,date=self.today,activity_type='walking',name='Unknown',duration_minutes=30,completed=True,calories=None),
                WorkoutLog(user_id=self.uid,date=self.today,activity_type='walking',name='Declared zero',duration_minutes=10,completed=True,calories=0),
                WorkoutLog(user_id=self.uid,date=self.today,activity_type='walking',name='Planned',duration_minutes=90,completed=False,calories=900)])
        result=self.ok(await self.http.get('/api/stats/dashboard'))['workout_stats']
        self.assertEqual(result['workouts_this_week'],2);self.assertEqual(result['total_duration_minutes'],40)
        self.assertIsNone(result['total_calories_burned']);self.assertEqual(result['calorie_records'],1)
        async with unit_of_work() as session:
            from sqlalchemy import select
            row=await session.scalar(select(WorkoutLog).where(WorkoutLog.user_id==self.uid,WorkoutLog.name=='Unknown'));row.calories=0
        result=self.ok(await self.http.get('/api/stats/dashboard'))['workout_stats']
        self.assertEqual(result['total_calories_burned'],0);self.assertEqual(result['calories_source'],'unverified')
        other=self.ok(await self.http.get('/api/stats/dashboard',headers={'Authorization':'Bearer bob'}))
        self.assertEqual(other['workout_stats']['workouts_this_week'],0);self.assertIsNone(other['workout_stats']['total_calories_burned'])

    async def test_money_exact_above_js_integer_and_weighted_score_distinct_from_accuracy(self):
        async with unit_of_work() as session:
            session.add_all([FinancialTransaction(user_id=self.uid,date=self.today,type='income',amount=Decimal(value),category='income') for value in ('9007199254740993.01','1.09')])
            exam=Exam(user_id=self.uid,title='Weighted sourced',kind='simulado',status='completed');session.add(exam);await session.flush()
            session.add(ExamAttempt(user_id=self.uid,exam_id=exam.id,completed_at=datetime.now(timezone.utc),duration_seconds=120,score=25,scoring_version='sourced_weighted',result_details={'correct_count':1,'total_questions':2,'raw_points':1,'maximum_points':4}))
        result=self.ok(await self.http.get('/api/stats/dashboard'))
        self.assertEqual(result['income'],'9007199254740994.10');self.assertEqual(result['balance'],'9007199254740994.10')
        self.assertEqual(result['simulado_stats']['average_score'],25);self.assertEqual(result['simulado_stats']['accuracy_rate'],50)
        async def account(request): return {'user_id':str(self.uid),'timezone':'America/Sao_Paulo','xp':0,'rank':'Recruta'}
        with patch('services.dashboard_panels.account',account): weekly=self.ok(await self.http.get('/api/dashboard/weekly-summary'))
        self.assertEqual(weekly['finance']['income'],'9007199254740994.10');self.assertIsNone(weekly['workouts']['total_calories'])
        analytics=self.ok(await self.http.get('/api/stats/analytics',params={'days':7}))
        self.assertEqual(analytics['totals']['income'],'9007199254740994.10');self.assertEqual(analytics['data'][-1]['income'],'9007199254740994.10')
