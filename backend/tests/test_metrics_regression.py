"""Use a disposable MongoDB to check full histories and owner/date isolation."""
import os
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
URI = os.getenv('XP_TEST_MONGO_URI') or os.getenv('ACTIVITY_TEST_MONGO_URI')


@unittest.skipUnless(URI, 'disposable MongoDB not configured')
class MetricsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        self.client = AsyncIOMotorClient(URI, serverSelectionTimeoutMS=5000)
        self.db = self.client['sirius_metrics_test_' + uuid.uuid4().hex]

    async def asyncTearDown(self):
        await self.client.drop_database(self.db.name)
        self.client.close()

    async def test_report_full_history_date_and_owner(self):
        from report_metrics import period_metrics
        for collection, fields in [
            ('transactions', {'amount': 2, 'type': 'income'}),
            ('study_sessions', {'duration_minutes': 3}),
            ('focus_sessions', {'focus_minutes': 5, 'completed': True}),
            ('question_logs', {'total': 4, 'correct': 3}),
            ('workout_logs', {'completed': True, 'duration_minutes': 10}),
            ('meals', {'total_calories': 100}), ('water_logs', {'amount_ml': 200}),
            ('task_instances', {'completed': True}),
        ]:
            await self.db[collection].insert_many([
                {'user_id': 'alice', 'date': '2026-09-25', **fields} for _ in range(1005)
            ] + [{'user_id': 'alice', 'date': '2026-09-24', **fields},
                 {'user_id': 'bob', 'date': '2026-09-25', **fields}])
        await self.db.habits.insert_one({'user_id': 'alice', 'completions': ['2026-09-24', '2026-09-25']})
        metrics = await period_metrics(self.db, 'alice', '2026-09-25', '2026-09-25')
        self.assertEqual(metrics['income'], 2010)
        self.assertEqual(metrics['study_minutes'], 8040)
        self.assertEqual(metrics['workouts'], 1005)
        self.assertEqual(metrics['tasks_completed'], 1005)
        self.assertEqual(metrics['questions_correct'], 3015)
        self.assertEqual(metrics['calories'], 100500)
        self.assertEqual(metrics['water_ml'], 201000)
        self.assertEqual(metrics['total_habits_completions'], 1)

    async def test_dashboard_real_percent_and_applicable_tasks(self):
        from dashboard_service import dashboard_snapshot
        await self.db.goals.insert_many([{'user_id': 'alice', 'progress': 20, 'daily_checks': ['x'] * 8}, {'user_id': 'alice', 'progress': 80}])
        await self.db.tasks.insert_many([
            {'user_id': 'alice', 'task_id': 'today', 'is_template': True, 'date': '2026-09-25', 'recurrence': 'once'},
            {'user_id': 'alice', 'task_id': 'tomorrow', 'is_template': True, 'date': '2026-09-26', 'recurrence': 'daily'},
        ])
        await self.db.task_instances.insert_many([{'user_id': 'alice', 'task_id': 'today', 'date': '2026-09-25', 'completed': True} for _ in range(2)])
        snapshot = await dashboard_snapshot(self.db, SimpleNamespace(user_id='alice', name='A', xp=0, rank='R', picture=None), '2026-09-25')
        self.assertEqual(snapshot['goals_avg_progress'], 50)
        self.assertEqual(snapshot['tasks_today'], 1)
        self.assertEqual(snapshot['tasks_completed_today'], 1)
