import os
import unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from db.models.planning import Task,TaskInstance,Goal,Habit,HabitCheck
from db.models.finance import FinancialTransaction
from db.models.studies import StudySession
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
        self.assertEqual(values['income'],1015.05);self.assertEqual(values['study_stats']['study_time_today_minutes'],25)
        rules={s['rule'] for s in values['suggestions']};self.assertIn('tasks_pending_today',rules)
        other=self.ok(await self.http.get('/api/stats/dashboard',headers={'Authorization':'Bearer bob'}))
        self.assertEqual(other['income'],9999.99);self.assertEqual(other['tasks_today'],0);self.assertEqual(other['study_stats']['study_time_today_minutes'],0)
        suggestions=self.ok(await self.http.get('/api/suggestions/cross-module'))
        self.assertEqual(suggestions['suggestions'],values['suggestions'])

    async def test_empty_dashboard_contract(self):
        values=self.ok(await self.http.get('/api/stats/dashboard'))
        self.assertEqual(values['goals_avg_progress'],0);self.assertEqual(values['balance'],0)
        self.assertEqual(values['nutrition_stats']['calories_goal'],2000)
        self.assertEqual(values['simulado_stats']['accuracy_rate'],0)
        self.assertEqual(values['study_stats']['current_streak'],0)
        self.assertEqual(values['suggestions'],[])
