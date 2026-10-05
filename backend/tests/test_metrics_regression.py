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
