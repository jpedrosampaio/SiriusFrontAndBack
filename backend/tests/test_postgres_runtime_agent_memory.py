import asyncio
import os
import unittest
from uuid import UUID,uuid4
from sqlalchemy import select,func
from db.models.agent import Memory
from db.models.command import CommandAudit
from db.session import unit_of_work
from ai.memory import fingerprint
import test_postgres_runtime_agent_actions as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class RuntimeMemory(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = setup.RuntimeAgentActions.asyncSetUp
    asyncTearDown = setup.RuntimeAgentActions.asyncTearDown
    ok = setup.RuntimeAgentActions.ok

    def key(self,**extra):return {'Idempotency-Key':str(uuid4()),**extra}

    async def current(self,mid):
        return next(row for row in self.ok(await self.http.get('/ai/memory')) if row['memory_id']==mid)

    async def test_owned_edit_delete_block_erases_content_and_prevents_recreation(self):
        body = {'category':'rule', 'content':'No reminders'}
        row = self.ok(await self.http.post('/ai/memory', json=body,headers=self.key())); mid=row['memory_id']
        self.assertEqual(self.ok(await self.http.get('/ai/memory', headers={'Authorization':'Bearer bob'})), [])
        self.assertEqual((await self.http.put('/ai/memory/'+mid, json={**body,'expected_version':row['version']}, headers=self.key(Authorization='Bearer bob'))).status_code, 404)
        self.assertEqual((await self.http.delete('/ai/memory/'+mid,params={'version':row['version']}, headers=self.key(Authorization='Bearer bob'))).status_code, 404)
        self.ok(await self.http.put('/ai/memory/'+mid, json={**body,'content':'Only morning reminders','expected_version':row['version']},headers=self.key()))
        edited=await self.current(mid);self.assertEqual(edited['content'], 'Only morning reminders')
        removed=self.ok(await self.http.delete('/ai/memory/'+mid,params={'version':edited['version']},headers=self.key()))
        self.assertEqual(self.ok(await self.http.get('/ai/memory')), [])
        async with unit_of_work() as session:
            record = await session.get(Memory, UUID(mid))
            self.assertEqual(record.content, ''); self.assertEqual(record.provenance, {}); self.assertTrue(record.blocked)
        self.assertEqual((await self.http.post('/ai/memory', json={'category':'context','content':'  ONLY morning   reminders '},headers=self.key())).status_code, 409)
        self.ok(await self.http.delete('/ai/memory/'+mid, params={'block':'false','version':removed['version']},headers=self.key()))
        self.ok(await self.http.post('/ai/memory', json={'category':'context','content':'Only morning reminders'},headers=self.key()))
        self.assertEqual((await self.http.delete('/ai/memory/invalid',params={'version':'a'*64},headers=self.key())).status_code, 404)

    async def test_concurrent_duplicates_and_limit_are_serialized(self):
        body = {'category':'preference', 'content':'Study in the morning'}
        rows = [self.ok(r) for r in await asyncio.gather(*(self.http.post('/ai/memory', json=body,headers=self.key()) for _ in range(6)))]
        self.assertEqual(len({row['memory_id'] for row in rows}), 1)
        async with unit_of_work() as session:
            session.add_all([Memory(user_id=self.uid, kind='context', content='Memory '+str(i), content_hash=fingerprint('Memory '+str(i))) for i in range(48)])
        responses = await asyncio.gather(*(self.http.post('/ai/memory', json={'category':'context','content':'Final '+str(i)},headers=self.key()) for i in range(5)))
        self.assertEqual([r.status_code for r in responses].count(200), 1)
        self.assertEqual([r.status_code for r in responses].count(409), 4)
        self.assertEqual(len(self.ok(await self.http.get('/ai/memory'))), 50)
        current=await self.current(rows[0]['memory_id'])
        self.ok(await self.http.put('/ai/memory/'+rows[0]['memory_id'], json={**body,'content':'Evening instead','expected_version':current['version']},headers=self.key()))
        self.assertEqual((await self.http.post('/ai/memory', json={**body,'content':'   '},headers=self.key())).status_code, 422)

    async def test_legacy_mutations_require_preconditions_and_retry_without_duplicate_audit(self):
        body={'category':'fact','content':'Declared memory'}
        self.assertEqual((await self.http.post('/ai/memory',json=body)).status_code,428)
        row=self.ok(await self.http.post('/ai/memory',json=body,headers=self.key()));mid=row['memory_id'];url='/ai/memory/'+mid
        self.assertEqual((await self.http.put(url,json=body,headers=self.key())).status_code,428)
        self.assertEqual((await self.http.delete(url,headers=self.key())).status_code,428)
        changed={**body,'content':'Latest correction','expected_version':row['version']};headers=self.key()
        first=self.ok(await self.http.put(url,json=changed,headers=headers))
        retry=self.ok(await self.http.put(url,json=changed,headers=headers));self.assertTrue(retry['replayed'])
        self.assertEqual((await self.http.put(url,json={**changed,'content':'Stale overwrite'},headers=self.key())).status_code,409)
        self.assertEqual((await self.http.delete(url,params={'version':row['version']},headers=self.key())).status_code,409)
        headers=self.key();self.ok(await self.http.delete(url,params={'version':first['version']},headers=headers))
        retry=self.ok(await self.http.delete(url,params={'version':first['version']},headers=headers));self.assertTrue(retry['replayed'])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(CommandAudit).where(CommandAudit.user_id==self.uid)),3)
