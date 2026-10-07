import asyncio
import json
import os
import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func
from db.models.agent import Conversation, Message, ConversationReceipt
from db.session import unit_of_work
from services.conversations import Conversations
import test_postgres_runtime_agent_actions as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class SQLConversations(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = setup.RuntimeAgentActions.asyncSetUp
    asyncTearDown = setup.RuntimeAgentActions.asyncTearDown
    ok = setup.RuntimeAgentActions.ok

    def body(self, request='request-001', message='Remember grammar'):
        return SimpleNamespace(conversation_id='primary', request_id=request, message=message)

    async def test_replay_owner_context_and_runtime_routes(self):
        llm = AsyncMock(return_value='Response'); service=Conversations(llm)
        body=self.body()
        first=await service.send(self.uid, body, 'system')
        self.assertEqual(first['user_message']['request_id'],body.request_id)
        self.assertEqual((await service.read(self.uid))['messages'][0]['request_id'],body.request_id)
        self.assertEqual(first, await service.send(self.uid, body, 'system'))
        self.assertEqual(llm.await_count, 1)
        with self.assertRaises(HTTPException) as error: await service.send(self.uid, self.body(message='changed'), 'system')
        self.assertEqual(error.exception.status_code, 409)
        await service.send(self.uid, self.body('request-002','What did I mention?'), 'system')
        self.assertIn('Remember grammar', llm.call_args.args[0])
        self.assertEqual(len((await service.read(self.uid))['messages']), 4)
        self.assertEqual((await service.read(self.other))['messages'], [])
        rows=self.ok(await self.http.get('/ai/conversations'));self.assertEqual(rows[0]['conversation_id'], 'primary')
        history=self.ok(await self.http.get('/ai/conversations/primary/history'))
        self.assertEqual([m['role'] for m in history['messages']], ['user','assistant','user','assistant'])
        self.assertEqual(self.ok(await self.http.get('/ai/conversations',headers={'Authorization':'Bearer bob'})), [])
        self.runtime.agent.respond=AsyncMock(return_value={'reply':'From runtime','facts':{'count':1}})
        response=await self.runtime.chat(str(self.uid), self.body('request-runtime','Runtime'))
        self.assertEqual(response['reply'], 'From runtime')
        self.assertEqual((await service.read(self.uid))['messages'][-1]['facts'], {'count':1})

    async def test_concurrent_lease_provider_failure_and_cancellation_release(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def provider(*args, **kwargs):
            entered.set(); await release.wait(); return 'Done'
        service=Conversations(provider)
        running=asyncio.create_task(service.send(self.uid,self.body(),'system'))
        await entered.wait()
        with self.assertRaises(HTTPException) as error: await service.send(self.uid,self.body('parallel'),'system')
        self.assertEqual(error.exception.status_code,409)
        running.cancel()
        with self.assertRaises(asyncio.CancelledError): await running
        async with unit_of_work() as session:
            row=await session.scalar(select(Conversation).where(Conversation.user_id==self.uid))
            self.assertIsNone(row.lease_token)
            self.assertEqual(await session.scalar(select(func.count()).select_from(Message).where(Message.user_id==self.uid)),0)
        failing=Conversations(AsyncMock(side_effect=RuntimeError('provider failed')))
        with self.assertRaises(RuntimeError): await failing.send(self.uid,self.body(),'system')
        self.assertEqual((await service.read(self.uid))['messages'],[])
        retry=Conversations(AsyncMock(return_value='Retry'))
        self.assertEqual((await retry.send(self.uid,self.body(),'system'))['reply'],'Retry')

    async def test_expired_lease_takeover_rejects_old_writer(self):
        entered, release=asyncio.Event(),asyncio.Event()
        async def slow(*args,**kwargs):
            entered.set(); await release.wait(); return 'Stale'
        old=asyncio.create_task(Conversations(slow).send(self.uid,self.body(),'system'))
        await entered.wait()
        async with unit_of_work() as session:
            row=await session.scalar(select(Conversation).where(Conversation.user_id==self.uid))
            row.lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)
        fresh=Conversations(AsyncMock(return_value='Fresh'))
        await fresh.send(self.uid,self.body('takeover'),'system')
        release.set()
        with self.assertRaises(HTTPException) as error: await old
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual([m['content'] for m in (await fresh.read(self.uid))['messages']], ['Remember grammar','Fresh'])

    async def test_context_retention_receipts_and_archive_pagination(self):
        llm=AsyncMock(return_value='Reply'); service=Conversations(llm)
        with patch.dict(os.environ, {'AI_CONTEXT_MESSAGES':'2'}):
            for i in range(102): await service.send(self.uid,self.body(f'request-{i:04d}',f'Message {i}'),'system')
        current=await service.read(self.uid)
        self.assertEqual(len(current['messages']),2);self.assertTrue(current['has_summary'])
        prompt=json.loads(llm.call_args.args[0]);self.assertEqual(len(prompt['history']),2)
        self.assertLessEqual(len(prompt['summary_extracts']),4000)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Message).where(Message.user_id==self.uid)),200)
            self.assertEqual(await session.scalar(select(func.count()).select_from(ConversationReceipt).where(ConversationReceipt.user_id==self.uid)),12)
        collected=[]; offset=0
        while True:
            page=await service.history(self.uid,offset=offset);collected.extend(m['message_id'] for m in page['messages'])
            if page['next_offset'] is None:break
            offset=page['next_offset']
        self.assertEqual(len(collected),200);self.assertEqual(len(set(collected)),200)
        archive=[];before=None
        while True:
            page=await service.archive(self.uid,before);archive.extend(m['message_id'] for m in page['messages'])
            if page['next_cursor'] is None:break
            before=page['next_cursor']
        self.assertEqual(len(set(archive)),200)
        with self.assertRaises(HTTPException):await service.archive(self.uid,'not-a-date')

    async def test_message_actions_refresh_from_owned_sql_state(self):
        action=await self.runtime.actions.propose(self.uid,'message-action',0,'record_expense',
            {'amount':'48.00','category':'food','date':'2026-10-01'},'Requested')
        service=Conversations(AsyncMock(return_value={'reply':'Review this proposal','actions':[action]}))
        await service.send(self.uid,self.body(),'system')
        await self.runtime.actions.confirm(self.uid,action['action_id'])
        messages=(await service.read(self.uid))['messages']
        self.assertEqual(messages[-1]['actions'][0]['status'],'executed')
        self.assertEqual((await service.read(self.other))['messages'],[])

    async def test_legacy_chat_aliases_share_sql_conversation_and_image_requires_new_flow(self):
        import server
        async def auth(**kwargs): return SimpleNamespace(user_id=str(self.uid))
        with patch.object(server,'get_current_user',auth), patch.object(server.agent_runtime.agent,'respond',AsyncMock(return_value={'reply':'Review before saving'})) as provider:
            async with AsyncClient(transport=ASGITransport(server.app),base_url='https://sirius.test') as http:
                first=self.ok(await http.post('/api/chat/send',json={'content':'Record expense'},headers={'Idempotency-Key':'legacy-request-001'}))
                replay=self.ok(await http.post('/api/chat/send',json={'content':'Record expense'},headers={'Idempotency-Key':'legacy-request-001'}))
                self.assertEqual(first,replay);self.assertEqual(provider.await_count,1)
                self.assertEqual(len(self.ok(await http.get('/api/chat/messages'))),2)
                self.assertEqual(len(self.ok(await http.get('/api/ai/conversation'))['messages']),2)
                self.assertEqual(len(self.ok(await http.get('/api/chat/general/archive'))['messages']),2)
                response=await http.post('/api/chat/analyze-image',files={'image':('receipt.png',b'not-an-image','image/png')})
                self.assertEqual(response.status_code,410)
                self.assertIn('/api/ai/attachments',response.json()['detail'])
