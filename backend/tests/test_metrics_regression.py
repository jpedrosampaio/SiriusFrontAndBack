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



    async def test_conversation_ownership_replay_and_bounded_context(self):
        from assistant_service import Conversations
        from unittest.mock import AsyncMock
        llm = AsyncMock(return_value='Resposta')
        service = Conversations(self.db, llm)
        body = SimpleNamespace(conversation_id='primary', request_id='request-001', message='Lembre de português')
        first = await service.send('alice', body, 'system')
        replay = await service.send('alice', body, 'system')
        self.assertEqual(first, replay)
        self.assertEqual(llm.await_count, 1)
        self.assertEqual((await service.read('bob'))['messages'], [])
        body.request_id = 'request-002'
        body.message = 'Qual matéria eu mencionei?'
        await service.send('alice', body, 'system')
        self.assertIn('Lembre de português', llm.call_args.args[0])
        self.assertEqual(len((await service.read('alice'))['messages']), 4)

    async def test_analytics_matches_legacy_and_exceeds_its_limits(self):
        import importlib.util
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock
        from analytics_service import analytics_snapshot
        path = Path(__file__).with_name('analytics_legacy_fixture.py')
        spec = importlib.util.spec_from_file_location('legacy', path)
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)
        legacy.db = self.db
        legacy.get_current_user = AsyncMock(return_value=SimpleNamespace(user_id='alice'))
        today = datetime.now(timezone.utc).date().isoformat()
        for name, fields in [('task_instances', {'completed': True}), ('transactions', {'type': 'income', 'amount': 2.25}),
                             ('study_sessions', {'duration_minutes': 20}), ('workout_logs', {'completed': True, 'duration_minutes': 40}),
                             ('question_logs', {'total': 10, 'correct': 7}), ('xp_logs', {'amount': 5})]:
            await self.db[name].insert_many([{'user_id': 'alice', 'date': today, **fields}, {'user_id': 'bob', 'date': today, **fields}])
        await self.db.habits.insert_one({'user_id': 'alice', 'completions': [today, today]})
        old = await legacy.get_analytics_data(SimpleNamespace(headers={}), 7, None)
        new = await analytics_snapshot(self.db, 'alice', 7, today)
        self.assertEqual(new, old)
        await self.db.transactions.insert_many([{'user_id': 'alice', 'date': today, 'type': 'income', 'amount': 1} for _ in range(5005)])
        new = await analytics_snapshot(self.db, 'alice', 7, today)
        old = await legacy.get_analytics_data(SimpleNamespace(headers={}), 7, None)
        self.assertEqual(new['totals']['income'], 5007.25)
        self.assertLess(old['totals']['income'], new['totals']['income'])
        import time
        import json
        from assistant_service import context_prompt
        await self.db.users.insert_one({'user_id': 'alice', 'name': 'Fixture', 'xp': 0})
        measurements = {}
        for name, call in [
            ('analytics_before_truncated', lambda: legacy.get_analytics_data(SimpleNamespace(headers={}), 7, None)),
            ('analytics_after_full', lambda: analytics_snapshot(self.db, 'alice', 7, today)),
            ('assistant_context_before', lambda: legacy.build_ai_system_prompt('alice', '/finance')),
            ('assistant_context_after', lambda: context_prompt(self.db, 'alice', '/finance')),
        ]:
            samples = []
            for _ in range(5):
                started = time.perf_counter()
                await call()
                samples.append(round((time.perf_counter() - started) * 1000, 2))
            measurements[name] = {'median_ms': sorted(samples)[2], 'samples_ms': samples}
        print('PERFORMANCE_DISPOSABLE_MONGO ' + json.dumps(measurements), flush=True)
