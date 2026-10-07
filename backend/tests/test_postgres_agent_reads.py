import os
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import UUID
from ai.core import Core
from db.session import unit_of_work
from db.models.planning import Task, Goal, Habit, HabitCheck, CalendarEvent
from db.models.finance import FinancialTransaction, Budget
from db.models.studies import StudyTopic, StudySession, QuestionAttempt, ReviewEvent, StudyPlan, StudyPlanEntry
from db.models.health import WorkoutPlan, WorkoutDay
from db.models.files import FileRecord, EditalAnalysis
import test_postgres_runtime_dashboard as setup
import test_postgres_runtime_catalog as catalog


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class AgentReads(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = setup.RuntimeDashboard.asyncSetUp
    asyncTearDown = setup.RuntimeDashboard.asyncTearDown
    ok = setup.RuntimeDashboard.ok

    async def test_every_read_empty_uses_sql_and_composite_planning(self):
        core = Core(object())
        names = ('get_today_tasks', 'get_tasks', 'get_habits', 'get_finance_summary', 'get_budget_status',
            'get_study_progress', 'get_wrong_questions', 'get_next_study_block', 'get_active_workout',
            'get_workout_progress', 'get_nutrition_today', 'get_calendar', 'get_goals', 'get_upcoming_deadlines',
            'get_dashboard_summary', 'get_daily_plan', 'get_weekly_review')
        values = {name: await core.read(name, self.uid) for name in names}
        self.assertEqual(values['get_daily_plan']['blocks'], [])
        self.assertEqual(values['get_today_tasks']['total'], 0)
        self.assertEqual(values['get_finance_summary']['balance'], Decimal('0.00'))
        self.assertEqual(values['get_weekly_review']['current']['study_minutes'], 0)
        with self.assertRaises(ValueError):
            await core.read('unregistered', self.uid)

    async def test_owned_counts_limits_money_habit_goal_and_full_calendar(self):
        day = self.today
        from zoneinfo import ZoneInfo
        midnight = datetime.combine(day, datetime.min.time(), ZoneInfo('America/Sao_Paulo'))
        async with unit_of_work() as session:
            session.add_all([Task(user_id=self.uid, title='Task', date=day, xp_reward=5) for _ in range(65)])
            session.add(Task(user_id=self.bob, title='Foreign', date=day, xp_reward=5))
            session.add(Task(user_id=self.uid, title='Future', date=day+timedelta(days=1), recurrence='daily', xp_reward=5))
            habit = Habit(user_id=self.uid, name='Reading'); session.add(habit)
            await session.flush()
            session.add(HabitCheck(user_id=self.uid, habit_id=habit.id, date=day, checked_at=datetime.now(timezone.utc)))
            session.add(Budget(user_id=self.uid, month=day.replace(day=1), category='food', limit=Decimal('2000.00')))
            session.add_all([FinancialTransaction(user_id=self.uid, date=day, type='expense', category='food', amount=Decimal('1.01')) for _ in range(1005)])
            session.add(FinancialTransaction(user_id=self.bob, date=day, type='expense', category='food', amount=Decimal('9999.99')))
            session.add_all([Goal(user_id=self.uid, title='Later', target_date=day+timedelta(days=20), progress=20) for _ in range(31)])
            session.add(Goal(user_id=self.uid, title='First', target_date=day, progress=10))
            # More than the old 30-item cap, then a fixed event filling the remaining working day.
            session.add_all([CalendarEvent(user_id=self.uid, title='Early', start_at=midnight+timedelta(minutes=i), end_at=midnight+timedelta(minutes=i+1)) for i in range(31)])
            session.add(CalendarEvent(user_id=self.uid, title='Busy', start_at=midnight+timedelta(hours=8), end_at=midnight+timedelta(hours=18)))
            session.add(CalendarEvent(user_id=self.uid, title='Overnight', start_at=midnight-timedelta(hours=1), end_at=midnight+timedelta(hours=1)))
        core = Core()
        tasks = await core.read('get_tasks', self.uid)
        self.assertEqual(tasks['total'], 65); self.assertEqual(len(tasks['items']), 60); self.assertTrue(tasks['truncated'])
        self.assertTrue((await core.read('get_habits', self.uid))[0]['completed_today'])
        self.assertEqual((await core.read('get_budget_status', self.uid))[0]['spent'], Decimal('1015.05'))
        self.assertEqual((await core.read('get_finance_summary', self.uid))['balance'], Decimal('-1015.05'))
        self.assertEqual((await core.read('get_upcoming_deadlines', self.uid))[0]['title'], 'First')
        calendar = await core.read('get_calendar', self.uid)
        self.assertEqual(len(calendar), 33)
        self.assertEqual(next(row for row in calendar if row['title']=='Overnight')['start_minute'], 0)
        self.assertEqual((await core.read('get_daily_plan', self.uid))['blocks'], [])
        self.assertEqual((await core.read('get_tasks', self.bob))['total'], 1)

    async def test_page_context_study_facts_and_plan_weeks_are_owned_and_archivable(self):
        _, program, book = await catalog.RuntimeCatalog.setup_catalog(self)
        nid, pid = UUID(book['notebook_id']), UUID(program['program_id'])
        async with unit_of_work() as session:
            topic = StudyTopic(user_id=self.uid, notebook_id=nid, topic_key='0', name='Grammar', position=0)
            plan = StudyPlan(user_id=self.uid, program_id=pid, start_date=self.today, end_date=self.today, availability=[60]*7, block_minutes=30)
            workout = WorkoutPlan(user_id=self.uid, name='Four weeks', plan_duration='mes')
            file = FileRecord(user_id=self.uid, filename='material.pdf', mime_type='application/pdf', size_bytes=5, sha256='a'*64, storage_provider='metadata_only')
            analysis = EditalAnalysis(user_id=self.uid, content_hash='a'*64, status='completed', analysis_version='1', structured_payload={}, filename='edital.pdf')
            session.add_all([topic, plan, workout, file, analysis]); await session.flush()
            fid, aid = str(file.id), str(analysis.id)
            session.add(StudySession(user_id=self.uid, notebook_id=nid, date=self.today, completed=True, source='focus', duration_minutes=25))
            session.add(StudySession(user_id=self.uid, notebook_id=nid, date=self.today, completed=False, duration_minutes=100))
            session.add(QuestionAttempt(user_id=self.uid, notebook_id=nid, topic_id=topic.id, total=10, correct=3, source='manual', answered_at=datetime.now(timezone.utc)))
            session.add(ReviewEvent(user_id=self.uid, topic_id=topic.id, reviewed_at=datetime.now(timezone.utc), result='practice', next_review=self.today))
            session.add(StudyPlanEntry(user_id=self.uid, plan_id=plan.id, notebook_id=nid, date=self.today, name='Grammar', minutes=30, kind='theory'))
            session.add_all([WorkoutDay(user_id=self.uid, plan_id=workout.id, position=i, week=i+1, label='A', name='Day') for i in range(4)])
        core = Core()
        raw = {'query':f'?program={pid}&notebook={nid}&topic=0&attachment={fid}&analysis={aid}'}
        context = await core.page_context(self.uid, raw)
        self.assertEqual(set(context), {'program','notebook','topic','attachment','analysis'})
        self.assertEqual(context['topic']['title'], 'Grammar')
        self.assertEqual(await core.page_context(self.bob, raw), {})
        self.assertEqual(await core.page_context(self.uid, {'notebook_id':'invalid'}), {})
        self.assertEqual(await core.page_context(self.uid, '[]'), {})
        self.assertEqual((await core.read('get_study_progress', self.uid))[0]['total_study_time_minutes'], 25)
        self.assertEqual((await core.read('get_wrong_questions', self.uid))[0]['accuracy'], 30)
        self.assertEqual((await core.read('get_next_study_block', self.uid))[0]['program_id'], str(pid))
        self.assertEqual((await core.read('get_active_workout', self.uid))[0]['duration_weeks'], 4)
        self.assertEqual(await core.read('get_next_study_block', self.bob), [])
        self.ok(await self.http.delete('/api/study/programs/'+str(pid)))
        self.assertEqual(await core.read('get_study_progress', self.uid), [])
        self.assertEqual(await core.read('get_wrong_questions', self.uid), [])
        self.assertEqual(await core.read('get_next_study_block', self.uid), [])
        self.assertEqual(set(await core.page_context(self.uid, raw)), {'attachment','analysis'})
