import asyncio
import os
import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock,patch
from sqlalchemy import select,func,event
from sqlalchemy.orm import Session
from fastapi import HTTPException
from db.session import unit_of_work
from db.models.telegram import TelegramLink,TelegramCode,TelegramUpdate
from db.models.finance import FinancialTransaction
from services.telegram import TelegramService
import test_postgres_runtime_dashboard as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class Telegram(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeDashboard.ok
    asyncTearDown=setup.RuntimeDashboard.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeDashboard.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid)}
        for target,value in [('services.telegram.account',account),('services.telegram.username',AsyncMock(return_value='test_bot'))]:
            p=patch(target,value);p.start();self.patches.append(p)
        self.service=TelegramService();self.chat=uuid4().int%10**14

    def update_id(self):return uuid4().int%10**15

    async def bind(self):
        row=self.ok(await self.http.post('/api/telegram/link'))
        reply,_=await self.service.process(self.update_id(),self.chat,'/vincular '+row['code'],'Alice')
        self.assertIn('sucesso',reply)
        return row

    async def test_codes_hash_rotation_expiry_one_time_binding_and_unlink(self):
        first=self.ok(await self.http.post('/api/telegram/link'));second=self.ok(await self.http.post('/api/telegram/link'))
        async with unit_of_work() as session:
            codes=(await session.scalars(select(TelegramCode).where(TelegramCode.user_id==self.uid))).all()
            self.assertEqual(len(codes),1);self.assertNotEqual(codes[0].code_hash,second['code']);self.assertEqual(len(codes[0].code_hash),64)
        reply,_=await self.service.process(self.update_id(),self.chat,'/vincular '+first['code']);self.assertIn('inválido',reply)
        replies=await asyncio.gather(*(self.service.process(self.update_id(),self.chat,'/vincular '+second['code']) for _ in range(4)))
        self.assertEqual(sum('sucesso' in r[0] for r in replies),1)
        self.assertTrue(self.ok(await self.http.get('/api/telegram/status'))['linked'])
        self.assertFalse(self.ok(await self.http.get('/api/telegram/status',headers={'Authorization':'Bearer bob'}))['linked'])
        self.assertTrue(self.ok(await self.http.post('/api/telegram/link'))['already_linked'])
        self.ok(await self.http.post('/api/telegram/unlink'))
        third=self.ok(await self.http.post('/api/telegram/link'))
        async with unit_of_work() as session:
            row=await session.scalar(select(TelegramCode).where(TelegramCode.user_id==self.uid));row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        reply,_=await self.service.process(self.update_id(),self.chat,'/vincular '+third['code']);self.assertIn('expirado',reply)

    async def test_financial_replay_decimal_validation_and_atomic_rollback(self):
        await self.bind();update=self.update_id()
        with patch('server.call_llm',AsyncMock(return_value='[{"type":"expense","amount":48.01,"description":"Lunch","category":"food"}]')):
            values=await asyncio.gather(*(self.service.process(update,self.chat,'Gastei 48,01 no almoço') for _ in range(6)),return_exceptions=True)
            self.assertTrue(any(isinstance(v,tuple) for v in values))
            self.assertTrue(all(not isinstance(v,Exception) or isinstance(v,HTTPException) and v.status_code==503 for v in values))
            await self.service.process(update,self.chat,'Gastei 48,01 no almoço')
        async with unit_of_work() as session:
            rows=(await session.scalars(select(FinancialTransaction).where(FinancialTransaction.user_id==self.uid))).all()
            self.assertEqual(len(rows),1);self.assertEqual(rows[0].amount,Decimal('48.01'))
        with self.assertRaises(HTTPException):await self.service.process(update,self.chat,'different')
        for invalid in ('[{"type":"expense","amount":0,"description":"Bad"}]','[{"type":"expense","amount":1.001,"description":"Bad"}]'):
            with patch('server.call_llm',AsyncMock(return_value=invalid)):
                reply,_=await self.service.process(self.update_id(),self.chat,'Gastei');self.assertIn('válidas',reply)
        retry=self.update_id()
        def fail(session,*args):
            if any(isinstance(row,FinancialTransaction) for row in session.new):raise RuntimeError('injected rollback')
        with patch('server.call_llm',AsyncMock(return_value='[{"type":"income","amount":0.10,"description":"Income"},{"type":"expense","amount":0.20,"description":"Expense"}]')):
            event.listen(Session,'before_flush',fail)
            try:
                with self.assertRaises(RuntimeError):await self.service.process(retry,self.chat,'Recebi e gastei')
            finally:event.remove(Session,'before_flush',fail)
            async with unit_of_work() as session:
                receipt=await session.get(TelegramUpdate,retry);self.assertIsNone(receipt.completed_at)
                self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id==self.uid)),1)
            await self.service.process(retry,self.chat,'Recebi e gastei')
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id==self.uid)),3)

    async def test_unlink_during_ai_prevents_write(self):
        await self.bind();entered=asyncio.Event();resume=asyncio.Event()
        async def provider(*args,**kwargs):
            entered.set();await resume.wait();return '[{"type":"expense","amount":50,"description":"Food"}]'
        with patch('server.call_llm',provider):
            task=asyncio.create_task(self.service.process(self.update_id(),self.chat,'Gastei 50'))
            await entered.wait();self.ok(await self.http.post('/api/telegram/unlink'));resume.set();reply,_=await task
        self.assertIn('Vínculo alterado',reply)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id==self.uid)),0)

    async def test_webhook_secret_private_chat_retry_and_daily_owner(self):
        await self.bind();update={'update_id':self.update_id(),'message':{'chat':{'id':self.chat,'type':'private'},'text':'/saldo','from':{'first_name':'Alice'}}}
        headers={'X-Telegram-Bot-Api-Secret-Token':'a'*32}
        with patch('server.TELEGRAM_BOT_TOKEN','test'),patch('server.TELEGRAM_BOT_WEBHOOK_SECRET','a'*32),patch('server.send_telegram_message',AsyncMock(return_value={'ok':True})) as sender:
            self.assertEqual((await self.http.post('/api/telegram/webhook',json=update)).status_code,403)
            self.ok(await self.http.post('/api/telegram/webhook',json=update,headers=headers))
            self.ok(await self.http.post('/api/telegram/webhook',json=update,headers=headers));self.assertEqual(sender.await_count,1)
            update['update_id']=self.update_id();update['message']['chat']['type']='group'
            self.ok(await self.http.post('/api/telegram/webhook',json=update,headers=headers));self.assertEqual(sender.await_count,1)
            result=await self.service.daily(str(self.bob));self.assertEqual(result,{'sent':0,'total':0});self.assertEqual(sender.await_count,1)
            result=await self.service.daily(str(self.uid));self.assertEqual(result,{'sent':1,'total':1});self.assertEqual(sender.call_args.args[0],self.chat)

    async def test_finance_summary_full_aggregate_and_future_exclusion(self):
        await self.bind()
        async with unit_of_work() as session:
            session.add_all([FinancialTransaction(user_id=self.uid,date=self.today,type='expense',amount=Decimal('1.01'),category='Food') for _ in range(1005)])
            session.add(FinancialTransaction(user_id=self.bob,date=self.today,type='expense',amount=Decimal('99999'),category='Secret'))
            session.add(FinancialTransaction(user_id=self.uid,date=self.today+timedelta(days=1),type='expense',amount=Decimal('99999'),category='Future'))
        for command in ('/saldo','/mes','/resumo'):
            reply,_=await self.service.process(self.update_id(),self.chat,command)
            self.assertIn('1,015.05',reply);self.assertNotIn('99,999',reply);self.assertNotIn('Secret',reply)
