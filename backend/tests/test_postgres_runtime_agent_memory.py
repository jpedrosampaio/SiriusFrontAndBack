import asyncio
import os
import unittest
from uuid import UUID
from db.models.agent import Memory
from db.session import unit_of_work
from ai.memory import fingerprint
import test_postgres_runtime_agent_actions as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class RuntimeMemory(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = setup.RuntimeAgentActions.asyncSetUp
    asyncTearDown = setup.RuntimeAgentActions.asyncTearDown
    ok = setup.RuntimeAgentActions.ok

    async def test_owned_edit_delete_block_erases_content_and_prevents_recreation(self):
        body = {'category':'rule', 'content':'No reminders'}
        row = self.ok(await self.http.post('/ai/memory', json=body)); mid=row['memory_id']
        self.assertEqual(self.ok(await self.http.get('/ai/memory', headers={'Authorization':'Bearer bob'})), [])
        self.assertEqual((await self.http.put('/ai/memory/'+mid, json=body, headers={'Authorization':'Bearer bob'})).status_code, 404)
        self.assertEqual((await self.http.delete('/ai/memory/'+mid, headers={'Authorization':'Bearer bob'})).status_code, 404)
        edited = self.ok(await self.http.put('/ai/memory/'+mid, json={**body,'content':'Only morning reminders'}))
        self.assertEqual(edited['content'], 'Only morning reminders')
        self.ok(await self.http.delete('/ai/memory/'+mid))
        self.assertEqual(self.ok(await self.http.get('/ai/memory')), [])
        async with unit_of_work() as session:
            record = await session.get(Memory, UUID(mid))
            self.assertEqual(record.content, ''); self.assertEqual(record.provenance, {}); self.assertTrue(record.blocked)
        self.assertEqual((await self.http.post('/ai/memory', json={'category':'context','content':'  ONLY morning   reminders '})).status_code, 409)
        self.ok(await self.http.delete('/ai/memory/'+mid, params={'block':'false'}))
        self.ok(await self.http.post('/ai/memory', json={'category':'context','content':'Only morning reminders'}))
        self.assertEqual((await self.http.delete('/ai/memory/invalid')).status_code, 404)

    async def test_concurrent_duplicates_and_limit_are_serialized(self):
        body = {'category':'preference', 'content':'Study in the morning'}
        rows = [self.ok(r) for r in await asyncio.gather(*(self.http.post('/ai/memory', json=body) for _ in range(6)))]
        self.assertEqual(len({row['memory_id'] for row in rows}), 1)
        async with unit_of_work() as session:
            session.add_all([Memory(user_id=self.uid, kind='context', content='Memory '+str(i), content_hash=fingerprint('Memory '+str(i))) for i in range(48)])
        responses = await asyncio.gather(*(self.http.post('/ai/memory', json={'category':'context','content':'Final '+str(i)}) for i in range(5)))
        self.assertEqual([r.status_code for r in responses].count(200), 1)
        self.assertEqual([r.status_code for r in responses].count(409), 4)
        self.assertEqual(len(self.ok(await self.http.get('/ai/memory'))), 50)
        self.ok(await self.http.put('/ai/memory/'+rows[0]['memory_id'], json={**body,'content':'Evening instead'}))
        self.assertEqual((await self.http.post('/ai/memory', json={**body,'content':'   '})).status_code, 422)
