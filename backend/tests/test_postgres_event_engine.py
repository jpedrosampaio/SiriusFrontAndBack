"""Disposable PostgreSQL integration: leases, ownership, factual sources and channel uncertainty."""
import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI, HTTPException
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func
from db.session import unit_of_work
from db.engine import get_engine
from db.models.agent import Event, EventDelivery, Insight, Preferences as StoredPreferences
from db.models.identity import User
from db.models.planning import Task, TaskInstance
from db.models.finance import Budget, FinancialTransaction
from db.models.telegram import TelegramLink, TelegramUpdate
from services import event_queue as queue, event_engine as engine, event_delivery as delivery
from services.event_sources import collect, candidate
from services.event_reports import briefing
from services.telegram import TelegramService
from services.telegram_delivery import deliver_reply, claim_reply
from event_contracts import Rule
import test_postgres_runtime_agent_actions as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class EventEngine(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeAgentActions.ok

    async def asyncSetUp(self):
        self.flags=patch.dict(os.environ,{'AUTOMATION_DRY_RUN':'false'});self.flags.start()
        await setup.RuntimeAgentActions.asyncSetUp(self)
        from services.event_routes import router,reports
        app=FastAPI();app.include_router(router);app.include_router(reports)
        async def auth(request):return {'user_id':str(self.other if request.headers.get('Authorization')=='Bearer bob' else self.uid)}
        self.auth_patch=patch('services.event_routes.account',auth);self.auth_patch.start()
        self.api=AsyncClient(transport=ASGITransport(app),base_url='https://events.test')
        self.now=queue.utc_now();self.day=self.now.astimezone(__import__('zoneinfo').ZoneInfo('America/Sao_Paulo')).date()
        self.chat=uuid4().int%10**14

    async def asyncTearDown(self):
        await self.api.aclose();self.auth_patch.stop()
        await setup.RuntimeAgentActions.asyncTearDown(self)
        self.flags.stop()

    async def enable(self,channels=None,cap=10):
        prefs={'automations':True,'quiet_start':0,'quiet_end':0,'daily_cap':cap,'event_automation':{'rules':
            {'task.overdue':{'channels':channels or ['in_app']}}}}
        self.ok(await self.http.put('/ai/preferences',json=prefs))

    async def task(self,owner=None,recurrence='once'):
        async with unit_of_work() as session:
            row=Task(user_id=owner or self.uid,title='Owned task',date=self.day-timedelta(days=2),recurrence=recurrence,xp_reward=10)
            session.add(row);await session.flush();return row.id

    async def queue_task(self,channels=None):
        await self.enable(channels);identity=await self.task()
        items,_,_=await collect(self.uid,now=self.now,target=candidate('task.overdue','task',self.day-timedelta(days=2),{},'Reason',identity))
        self.assertEqual(len(items),1)
        async with unit_of_work() as session:await queue.enqueue(session,self.uid,items[0],self.day)
        return await queue.claim(self.uid)

    async def paired_delivery(self):
        async with unit_of_work() as session:session.add(TelegramLink(user_id=self.uid,chat_id=self.chat,telegram_name='Alice',linked_at=self.now))
        event=await self.queue_task(['in_app','telegram'])
        await engine.process(event,dry_run=False)
        claim=await delivery.claim_delivery(user_id=self.uid);self.assertIsNotNone(claim)
        return claim

    async def test_concurrent_claim_expiry_attempt_exhaustion(self):
        event=await self.queue_task();self.assertIsNone(await queue.claim(self.uid))
        async with unit_of_work() as session:
            row=await session.get(Event,UUID(event['event_id']));row.lease_until=self.now-timedelta(seconds=1)
        claims=await asyncio.gather(*(queue.claim(self.uid) for _ in range(4)))
        self.assertEqual(sum(x is not None for x in claims),1);fresh=next(x for x in claims if x)
        self.assertFalse(await queue.finish(event));self.assertTrue(await queue.finish(fresh,error='processing_failed'))
        async with unit_of_work() as session:
            row=await session.get(Event,UUID(event['event_id']));self.assertEqual(row.status,'pending');self.assertGreater(row.available_at,self.now)
            row.status='processing';row.attempts=5;row.lease_until=self.now-timedelta(seconds=1)
        self.assertIsNone(await queue.claim(self.uid))
        async with unit_of_work() as session:self.assertEqual((await session.get(Event,UUID(event['event_id']))).status,'failed')

    async def test_replay_preserves_single_insight_channels_and_no_domain_writes(self):
        event=await self.queue_task(['in_app','telegram'])
        await asyncio.gather(*(queue.publish(event,__import__('event_contracts').EventCandidate.model_validate(event['payload']['candidate']),dry_run=True) for _ in range(4)))
        await queue.finish(event)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Insight).where(Insight.user_id==self.uid)),1)
            rows=(await session.scalars(select(EventDelivery).where(EventDelivery.user_id==self.uid))).all()
            self.assertEqual({r.status for r in rows},{'available','cancelled'})
            self.assertEqual(await session.scalar(select(func.count()).select_from(TaskInstance).where(TaskInstance.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_resolved_disabled_and_zero_cap_do_not_deliver(self):
        event=await self.queue_task()
        async with unit_of_work() as session:
            session.add(TaskInstance(user_id=self.uid,task_id=UUID(event['entity_id']),date=self.day-timedelta(days=2),completed=True,status='done'))
        await engine.process(event,dry_run=False)
        async with unit_of_work() as session:
            self.assertEqual((await session.get(Event,UUID(event['event_id']))).payload['outcome'],'resolved')
            self.assertEqual(await session.scalar(select(func.count()).select_from(EventDelivery).where(EventDelivery.user_id==self.uid)),0)
        await self.enable(cap=0)
        identity=await self.task();item=candidate('task.overdue','task',self.day-timedelta(days=2),{},'Fact',identity)
        async with unit_of_work() as session:await queue.enqueue(session,self.uid,item,self.day)
        event=await queue.claim(self.uid);await engine.process(event,dry_run=False)
        async with unit_of_work() as session:self.assertEqual((await session.get(Event,UUID(event['event_id']))).payload['outcome'],'cancelled')

    async def test_rotating_scans_restart_and_recurring_occurrences(self):
        await self.enable()
        async with unit_of_work() as session:
            session.add_all([Task(user_id=self.uid,title=str(i),date=self.day-timedelta(days=1),xp_reward=5) for i in range(45)])
            await queue.ensure_scan(session,self.uid)
        for _ in range(3):
            async with unit_of_work() as session:
                row=await session.scalar(select(Event).where(Event.user_id==self.uid,Event.event_type=='system.scan'))
                row.available_at=self.now-timedelta(days=1)
            scan=await queue.claim(self.uid);self.assertEqual(scan['type'],'system.scan');await engine.scan(scan)
        async with unit_of_work() as session:
            seen=(await session.scalars(select(Event.entity_id).where(Event.user_id==self.uid,Event.event_type=='task.overdue'))).all()
        self.assertEqual(len(set(seen)),45)
        identity=await self.task(recurrence='daily')
        target=candidate('task.overdue','task',self.day-timedelta(days=1),{},'Fact',identity)
        items,_,_=await collect(self.uid,now=self.now,target=target);self.assertEqual(len(items),1)

    async def test_receipts_ownership_idempotent_read_and_retry_confirmation(self):
        event=await self.queue_task();await engine.process(event,dry_run=False)
        inbox=self.ok(await self.api.get('/automations/inbox'));self.assertEqual(len(inbox),1)
        did=inbox[0]['delivery_id'];headers={'Idempotency-Key':'read-event-001'}
        self.assertEqual(self.ok(await self.api.get('/automations/inbox',headers={'Authorization':'Bearer bob'})),[])
        self.assertEqual((await self.api.post('/automations/deliveries/'+did,json={'action':'read'},headers={**headers,'Authorization':'Bearer bob'})).status_code,404)
        first=self.ok(await self.api.post('/automations/deliveries/'+did,json={'action':'read'},headers=headers))
        replay=self.ok(await self.api.post('/automations/deliveries/'+did,json={'action':'read'},headers=headers))
        self.assertEqual(first['status'],'delivered');self.assertTrue(replay['replayed']);self.assertEqual(self.ok(await self.api.get('/automations/inbox')),[])

    async def test_policy_replay_preserves_agent_fields_and_late_old_client(self):
        self.ok(await self.http.put('/ai/preferences',json={'profile':'proactive','quiet_start':0,'quiet_end':0}))
        body={'enabled':True,'daily_cap':4,'policy':{'quiet_start':'22:30','quiet_end':'07:30','rules':{'task.overdue':{'frequency':'weekly','priority':'high'}}}}
        headers={'Idempotency-Key':'events-policy-001'}
        self.ok(await self.api.put('/automations/policy',json=body,headers=headers))
        self.assertTrue(self.ok(await self.api.put('/automations/policy',json=body,headers=headers))['replayed'])
        prefs=self.ok(await self.http.get('/ai/preferences'));self.assertEqual(prefs['profile'],'proactive')
        self.ok(await self.http.put('/ai/preferences',json={'profile':'balanced'}))
        state=self.ok(await self.api.get('/automations/state'));self.assertEqual(state['policy']['quiet_start'],'22:30')
        self.assertFalse(self.ok(await self.api.get('/automations/state',headers={'Authorization':'Bearer bob'}))['enabled'])

    async def test_provider_receipt_and_io_has_no_checked_out_transaction(self):
        claim=await self.paired_delivery()
        self.assertEqual((await delivery.prepare(claim))[0],self.chat)
        self.assertEqual(get_engine().pool.checkedout(),0)
        self.assertTrue(await delivery.record_result(claim,result={'ok':True,'result':{'message_id':42,'chat':{'id':self.chat}}}))
        self.assertFalse(await delivery.record_result(claim,result={'ok':False}))
        async with unit_of_work() as session:
            row=await session.get(EventDelivery,UUID(claim['id']));self.assertEqual(row.status,'delivered');self.assertEqual(row.provider_receipt,'42')

    async def test_ambiguous_send_does_not_retry_and_owner_explicit_retry_is_bounded(self):
        claim=await self.paired_delivery();await delivery.prepare(claim);await delivery.record_result(claim,result={'ok':True})
        self.assertIsNone(await delivery.claim_delivery(user_id=self.uid))
        path='/automations/deliveries/'+claim['id'];headers={'Idempotency-Key':'explicit-retry-001'}
        self.assertEqual((await self.api.post(path,json={'action':'retry'},headers=headers)).status_code,409)
        self.ok(await self.api.post(path,json={'action':'retry','accept_duplicate_risk':True},headers=headers))
        next_claim=await delivery.claim_delivery(user_id=self.uid);await delivery.prepare(next_claim);await delivery.record_result(next_claim,ambiguous=True)
        async with unit_of_work() as session:
            row=await session.get(EventDelivery,UUID(claim['id']));row.attempts=8
        self.assertEqual((await self.api.post(path,json={'action':'retry','accept_duplicate_risk':True},headers={'Idempotency-Key':'explicit-retry-002'})).status_code,409)

    async def test_crash_in_dispatch_window_is_uncertain_not_resent(self):
        claim=await self.paired_delivery();await delivery.prepare(claim)
        async with unit_of_work() as session:
            row=await session.get(EventDelivery,UUID(claim['id']));row.lease_until=self.now-timedelta(seconds=1)
        self.assertIsNone(await delivery.claim_delivery(user_id=self.uid))
        async with unit_of_work() as session:self.assertEqual((await session.get(EventDelivery,UUID(claim['id']))).status,'uncertain')

    async def test_known_429_persists_backoff_and_pair_change_cancels(self):
        claim=await self.paired_delivery();await delivery.prepare(claim)
        await delivery.record_result(claim,result={'ok':False,'error_code':429,'parameters':{'retry_after':45}})
        async with unit_of_work() as session:
            row=await session.get(EventDelivery,UUID(claim['id']));self.assertEqual(row.status,'pending');self.assertGreater(row.available_at,self.now)
            row.available_at=self.now-timedelta(seconds=1)
            link=await session.scalar(select(TelegramLink).where(TelegramLink.user_id==self.uid));await session.delete(link)
        fresh=await delivery.claim_delivery(user_id=self.uid);self.assertIsNone(await delivery.prepare(fresh))
        async with unit_of_work() as session:self.assertEqual((await session.get(EventDelivery,UUID(claim['id']))).last_error,'pairing_changed')

    async def test_pairing_is_busy_only_during_real_dispatch(self):
        claim=await self.paired_delivery();await delivery.prepare(claim)
        async with unit_of_work() as session:self.assertTrue(await delivery.pairing_busy(session,uid=self.uid))
        await delivery.record_result(claim,ambiguous=True)
        async with unit_of_work() as session:self.assertFalse(await delivery.pairing_busy(session,uid=self.uid))

    async def test_briefing_aggregates_owned_rows_no_fake_adherence(self):
        async with unit_of_work() as session:
            session.add_all([FinancialTransaction(user_id=self.uid,type='expense',category='Food',amount=Decimal('0.10'),date=self.day) for _ in range(1001)])
            session.add(FinancialTransaction(user_id=self.other,type='expense',category='Secret',amount=9999,date=self.day))
        report=await briefing(self.uid,mode='weekly',now=self.now)
        self.assertEqual(report.facts['finance']['recorded_expense'],'100.10');self.assertIsNone(report.facts['finance']['bank_balance'])
        self.assertTrue(report.read_only);self.assertTrue(report.confirmation_required)
        self.assertIsNone(report.facts['training']['planned_days']);self.assertNotIn('adherence',report.facts['preparation'])
        self.assertEqual((await self.api.get('/dashboard/daily-briefing?mode=bad')).status_code,422)
        old=await briefing(self.uid,day=self.day-timedelta(days=1),now=self.now)
        self.assertNotIn('life_state',old.facts)

    async def test_telegram_read_queries_no_ai_financial_writes_and_duplicate_receipt(self):
        async with unit_of_work() as session:session.add(TelegramLink(user_id=self.uid,chat_id=self.chat,telegram_name='Alice',linked_at=self.now))
        service=TelegramService()
        with patch('server.call_llm',AsyncMock(side_effect=AssertionError('Read must not call AI'))):
            for text in ('O que faço hoje?','Qual meu treino?','Quanto gastei esta semana?','Revisões atrasadas'):
                reply,_=await service.process(uuid4().int%10**15,self.chat,text);self.assertTrue(reply)
        update=uuid4().int%10**15;await service.process(update,self.chat,'/hoje')
        sender=AsyncMock(return_value={'ok':True,'result':{'message_id':1,'chat':{'id':self.chat}}})
        await asyncio.gather(*(deliver_reply(update_id=update,sender=sender) for _ in range(4)));self.assertEqual(sender.await_count,1)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id==self.uid)),0)
            self.assertEqual((await session.get(TelegramUpdate,update)).delivery_status,'delivered')

    async def test_reply_binding_change_and_origin_are_rejected(self):
        async with unit_of_work() as session:session.add(TelegramLink(user_id=self.uid,chat_id=self.chat,telegram_name='Alice',linked_at=self.now))
        service=TelegramService();update=uuid4().int%10**15;await service.process(update,self.chat,'/hoje')
        async with unit_of_work() as session:
            link=await session.scalar(select(TelegramLink).where(TelegramLink.user_id==self.uid));await session.delete(link)
        self.assertIsNone(await claim_reply(update))
        with self.assertRaises(HTTPException):await service.webhook({'update_id':uuid4().int%10**15,
            'message':{'chat':{'id':self.chat,'type':'private'},'text':'/hoje','from':{'id':self.chat+1}}})

    async def test_canonical_producer_and_scanner_share_dedup_and_rollback(self):
        from services.planning import set_task_completion
        identity=await self.task()
        await set_task_completion(self.uid,identity,self.day-timedelta(days=2),'done','complete-event-001')
        async with unit_of_work() as session:
            rows=(await session.scalars(select(Event).where(Event.user_id==self.uid))).all();self.assertEqual(len(rows),1)
            self.assertEqual(rows[0].payload['schema'],'domain-event/2')
        items,_,_=await collect(self.uid,now=self.now)
        async with unit_of_work() as session:
            for item in items:await queue.enqueue(session,self.uid,item,self.day)
        async with unit_of_work() as session:self.assertEqual(await session.scalar(select(func.count()).select_from(Event).where(Event.user_id==self.uid,Event.event_type=='task.completed')),1)

    async def test_finance_known_due_dates_prefixed_ids_and_confirmed_targets_only(self):
        from db.models.finance import CreditCard,Invoice,MonthlyBill
        async with unit_of_work() as session:
            card=CreditCard(user_id=self.uid,name='Own card',limit=1000,closing_day=1,due_day=self.day.day)
            session.add(card);await session.flush()
            session.add(Invoice(user_id=self.uid,card_id=card.id,month=self.day.replace(day=1),amount=100))
            session.add(MonthlyBill(user_id=self.uid,month=self.day.replace(day=1),amount=50,category='Food',description='Unknown day'))
            session.add(Budget(user_id=self.uid,month=self.day.replace(day=1),category='Food',limit=100))
            session.add(FinancialTransaction(user_id=self.uid,date=self.day,type='expense',amount=80,category='Food'))
        items,_,warnings=await collect(self.uid)
        self.assertEqual(len([c for c in items if c.event_type=='budget.threshold_reached']),1)
        bills=[c for c in items if c.event_type=='bill.due'];self.assertEqual(len(bills),1)
        self.assertEqual(bills[0].facts['source_type'],'invoice');self.assertIsInstance(bills[0].entity_id,UUID)
        fresh,_,_=await collect(self.uid,target=bills[0]);self.assertEqual(len(fresh),1)
        self.assertTrue(any('sem dia' in w for w in warnings));self.assertFalse(any(c.event_type=='nutrition.target_remaining' for c in items))
        async with unit_of_work() as session:session.add(FinancialTransaction(user_id=self.uid,date=self.day,type='expense',amount=21,category='Food'))
        items,_,_=await collect(self.uid);self.assertEqual([c.facts['spent'] for c in items if c.event_type=='budget.exceeded'],['101.00'])

    async def test_snoozed_previous_day_suppresses_today_without_false_delivery(self):
        event=await self.queue_task()
        item=__import__('event_contracts').EventCandidate.model_validate(event['payload']['candidate'])
        import hashlib
        source=f'{item.event_type}:{item.entity_type}:{item.entity_id}:{item.occurrence}'
        async with unit_of_work() as session:session.add(Insight(user_id=self.uid,rule='event:'+hashlib.sha256(source.encode()).hexdigest(),
            title='Old insight',evidence={},link='/tasks',date=self.day-timedelta(days=1),feedback='snooze',snoozed_until=self.now+timedelta(days=1),dry_run=True))
        await engine.process(event,dry_run=False)
        async with unit_of_work() as session:
            self.assertEqual((await session.get(Event,UUID(event['event_id']))).payload['outcome'],'cancelled')
            self.assertEqual(await session.scalar(select(func.count()).select_from(EventDelivery).where(EventDelivery.user_id==self.uid)),0)

    async def test_priority_and_weekly_routine_dedup_are_explicit(self):
        a=await self.task();b=await self.task()
        async with unit_of_work() as session:
            await queue.enqueue(session,self.uid,candidate('task.overdue','task',self.day,{},'Reason',a),self.day,priority='low')
            await queue.enqueue(session,self.uid,candidate('task.overdue','task',self.day,{},'Reason',b),self.day,priority='high')
        event=await queue.claim(self.uid);self.assertEqual(event['entity_id'],str(b));await queue.finish(event)
        async with unit_of_work() as session:
            monday=self.day-timedelta(days=self.day.weekday())
            for i in range(7):
                d=monday+timedelta(days=i);await queue.enqueue(session,self.uid,candidate('brief.daily','routine',d,{},'Summary'),d,'weekly')
        async with unit_of_work() as session:self.assertEqual(await session.scalar(select(func.count()).select_from(Event).where(Event.user_id==self.uid,Event.event_type=='brief.daily')),1)

    async def test_scan_transaction_rolls_back_events_and_cursors_together(self):
        await self.enable();await self.task()
        async with unit_of_work() as session:await queue.ensure_scan(session,self.uid)
        event=await queue.claim(self.uid);original=queue.enqueue
        async def fail(*args,**kwargs):await original(*args,**kwargs);raise RuntimeError('Injected after first insert')
        with patch('services.event_queue.enqueue',fail):
            with self.assertRaises(RuntimeError):await engine.scan(event)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Event).where(Event.user_id==self.uid)),1)
            self.assertEqual((await session.get(Event,UUID(event['event_id']))).payload,{'cursors':{}})
        await queue.finish(event,error='processing_failed')
        async with unit_of_work() as session:
            row=await session.get(Event,UUID(event['event_id']));row.available_at=self.now-timedelta(seconds=1)
        await engine.scan(await queue.claim(self.uid))
        async with unit_of_work() as session:self.assertGreater(await session.scalar(select(func.count()).select_from(Event).where(Event.user_id==self.uid)),1)

    async def test_composite_fk_rejects_other_owners_event(self):
        from sqlalchemy.exc import IntegrityError
        event=await self.queue_task()
        with self.assertRaises(IntegrityError):
            async with unit_of_work() as session:
                session.add(EventDelivery(user_id=self.other,event_id=UUID(event['event_id']),channel='in_app',status='available'))
                await session.flush()

    async def test_telegram_timeout_and_worker_restart_never_resend_blindly(self):
        async with unit_of_work() as session:session.add(TelegramLink(user_id=self.uid,chat_id=self.chat,telegram_name='Alice',linked_at=self.now))
        update=uuid4().int%10**15;await TelegramService().process(update,self.chat,'/semana')
        sender=AsyncMock(side_effect=TimeoutError('ambiguous'))
        await deliver_reply(update_id=update,sender=sender);await deliver_reply(update_id=update,sender=sender)
        self.assertEqual(sender.await_count,1)
        async with unit_of_work() as session:
            row=await session.get(TelegramUpdate,update);self.assertEqual(row.delivery_status,'uncertain');self.assertEqual(len(row.delivery_history),2)

    async def test_deleted_owner_reply_cannot_be_delivered_as_anonymous(self):
        async with unit_of_work() as session:session.add(TelegramLink(user_id=self.uid,chat_id=self.chat,telegram_name='Alice',linked_at=self.now))
        update=uuid4().int%10**15;await TelegramService().process(update,self.chat,'/semana')
        async with unit_of_work() as session:
            user=await session.get(User,self.uid);await session.delete(user)
        self.assertIsNone(await claim_reply(update))
        async with unit_of_work() as session:self.assertEqual((await session.get(TelegramUpdate,update)).delivery_error,'owner_deleted')

    async def test_legacy_reply_without_owner_and_already_delivered_window_are_safe(self):
        leaked=uuid4().int%10**15;confirmed=uuid4().int%10**15
        async with unit_of_work() as session:
            session.add(TelegramUpdate(update_id=leaked,chat_id=self.chat,user_id=None,request_hash='legacy',lease_until=self.now,
                completed_at=self.now,reply='Saldo total: PRIVATE',delivery_status='pending'))
            session.add(TelegramUpdate(update_id=confirmed,chat_id=self.chat,user_id=None,request_hash='legacy-confirmed',lease_until=self.now,
                completed_at=self.now,reply='Sirius: /vincular CODIGO',delivered_at=self.now,delivery_status='pending'))
        self.assertIsNone(await claim_reply(leaked));self.assertIsNone(await claim_reply(confirmed))

    async def test_global_simulation_toggle_cancels_previously_queued_telegram(self):
        claim=await self.paired_delivery()
        with patch.dict(os.environ,{'AUTOMATION_DRY_RUN':'true'}):self.assertIsNone(await delivery.prepare(claim))
        async with unit_of_work() as session:self.assertEqual((await session.get(EventDelivery,UUID(claim['id']))).last_error,'simulation_only')

    async def test_transition_dedup_survives_new_day_and_edited_date(self):
        identity=uuid4()
        async with unit_of_work() as session:
            for offset in range(7):
                day=self.day+timedelta(days=offset)
                await queue.enqueue(session,self.uid,candidate('expense.created','transaction',day,{},'Registered',identity),day)
        async with unit_of_work() as session:self.assertEqual(await session.scalar(select(func.count()).select_from(Event).where(Event.user_id==self.uid)),1)

    async def test_study_sources_latest_review_and_manual_exam_date_preserve_origins(self):
        from db.models.studies import StudyArea,StudyProgram,StudyTarget,Notebook,StudyTopic,ReviewEvent,StudySession,StudyPlan,StudyPlanEntry
        from db.models.contests import ContestSource,ContestUpdate
        async with unit_of_work() as session:
            area=StudyArea(user_id=self.uid,name='Own area');session.add(area);await session.flush()
            program=StudyProgram(user_id=self.uid,area_id=area.id,name='Own preparation');session.add(program);await session.flush()
            session.add(StudyTarget(user_id=self.uid,program_id=program.id,name='Own exam',kind='contest',exam_date=self.day+timedelta(days=7),metadata_origin='manual'))
            nb=Notebook(user_id=self.uid,area_id=area.id,program_id=program.id,name='Own notebook');session.add(nb);await session.flush()
            topic=StudyTopic(user_id=self.uid,notebook_id=nb.id,topic_key='0',name='Own topic',position=0);session.add(topic);await session.flush()
            session.add_all([ReviewEvent(user_id=self.uid,topic_id=topic.id,reviewed_at=self.now-timedelta(days=2),result='practice',next_review=self.day-timedelta(days=1)),
                ReviewEvent(user_id=self.uid,topic_id=topic.id,reviewed_at=self.now-timedelta(days=1),result='practice',next_review=self.day+timedelta(days=1))])
            session.add(StudySession(user_id=self.uid,notebook_id=nb.id,date=self.day,duration_minutes=25,completed=True))
            plan=StudyPlan(user_id=self.uid,program_id=program.id,start_date=self.day-timedelta(days=1),end_date=self.day+timedelta(days=7),availability=[30]*7,block_minutes=30)
            session.add(plan);await session.flush()
            session.add(StudyPlanEntry(user_id=self.uid,plan_id=plan.id,notebook_id=nb.id,topic_id=topic.id,date=self.day-timedelta(days=1),name='Protected block',minutes=30,kind='study',fixed=True))
            source=ContestSource(user_id=self.uid,program_id=program.id,url='https://example.test/official',url_hash='fake',title='Own source',trust='confirmed',provider='manual',terms_confirmed_at=self.now,next_poll=self.now,enabled=False)
            session.add(source);await session.flush()
            session.add(ContestUpdate(user_id=self.uid,program_id=program.id,source_id=source.id,source='manual',title='Registered update',url=source.url,document_type='rectification',content_hash='registered',hash_basis='page_text',source_type='official_page',official=True,detected_at=self.now,summary='Existing source',changes={'categories':['syllabus']}))
        items,_,_=await collect(self.uid)
        kinds={i.event_type for i in items};self.assertTrue({'exam.approaching','study.session.completed','study.block.missed','edital.updated'}.issubset(kinds))
        self.assertNotIn('study.review.overdue',kinds)
        exam=next(i for i in items if i.event_type=='exam.approaching');self.assertEqual(exam.facts['origin'],'manual');self.assertEqual(exam.facts['days_remaining'],7)
        async with unit_of_work() as session:
            target=await session.scalar(select(StudyTarget).where(StudyTarget.user_id==self.uid));target.metadata_origin='inferred'
            session.add(ReviewEvent(user_id=self.uid,topic_id=topic.id,reviewed_at=self.now,result='practice',next_review=self.day-timedelta(days=1)))
        items,_,_=await collect(self.uid);self.assertNotIn('exam.approaching',{i.event_type for i in items})
        self.assertEqual(len([i for i in items if i.event_type=='study.review.overdue']),1)
        async with unit_of_work() as session:
            block=await session.scalar(select(StudyPlanEntry).where(StudyPlanEntry.user_id==self.uid));self.assertTrue(block.fixed);self.assertFalse(block.completed)

    async def test_question_cluster_resolves_after_correct_attempt_without_new_mastery(self):
        from db.models.studies import StudyArea,Notebook,StudyTopic,QuestionAttempt
        from db.models.exams import Question
        async with unit_of_work() as session:
            area=StudyArea(user_id=self.uid,name='Area');session.add(area);await session.flush()
            nb=Notebook(user_id=self.uid,area_id=area.id,name='Book');session.add(nb);await session.flush()
            topic=StudyTopic(user_id=self.uid,notebook_id=nb.id,topic_key='0',name='Topic',position=0);session.add(topic);await session.flush()
            questions=[]
            for statement in ('First factual question','Second factual question','Third factual question'):
                q=Question(user_id=self.uid,notebook_id=nb.id,topic_id=topic.id,statement=statement,question_type='multiple_choice',source='manual');session.add(q);await session.flush();questions.append(q)
                session.add(QuestionAttempt(user_id=self.uid,notebook_id=nb.id,topic_id=topic.id,question_id=q.id,source='manual',answered_at=self.now-timedelta(minutes=2),correct=0,error_cause='content',evidence={'answered':True}))
            session.add(QuestionAttempt(user_id=self.uid,notebook_id=nb.id,total=50,correct=0,source='legacy',answered_at=self.now-timedelta(minutes=1)))
        items,_,_=await collect(self.uid);cluster=next(i for i in items if i.event_type=='question.failed');self.assertEqual(cluster.facts['question_count'],3)
        async with unit_of_work() as session:session.add(QuestionAttempt(user_id=self.uid,notebook_id=nb.id,topic_id=topic.id,question_id=questions[0].id,source='manual',answered_at=self.now,correct=1,evidence={'answered':True}))
        fresh,_,_=await collect(self.uid,target=cluster);self.assertEqual(fresh,[])

    async def test_goal_pages_and_nutrition_require_confirmed_known_data(self):
        from db.models.planning import Goal
        from db.models.health import NutritionGoal
        from zoneinfo import ZoneInfo
        evening=datetime.combine(self.day,__import__('datetime').time(19),ZoneInfo('America/Sao_Paulo'))
        async with unit_of_work() as session:
            session.add_all([Goal(user_id=self.uid,title=str(i),target_date=self.day-timedelta(days=1),progress=20) for i in range(45)])
            goal=NutritionGoal(user_id=self.uid,daily_calories=2000,confirmed_fields=[],confirmed_at=None);session.add(goal);await session.flush();gid=goal.id
        items,cursors,_=await collect(self.uid,now=evening);self.assertEqual(len([i for i in items if i.event_type=='goal.off_track']),40)
        self.assertFalse(any(i.event_type=='nutrition.target_remaining' for i in items))
        second,_,_=await collect(self.uid,now=evening,cursors=cursors);self.assertEqual(len([i for i in second if i.event_type=='goal.off_track']),5)
        async with unit_of_work() as session:
            goal=await session.get(NutritionGoal,gid);goal.confirmed_fields=['daily_calories'];goal.confirmed_at=self.now
        items,_,_=await collect(self.uid,now=evening);nutrition=next(i for i in items if i.event_type=='nutrition.target_remaining')
        self.assertEqual(set(nutrition.facts['remaining']),{'calories'})

    async def test_monthly_overdue_task_is_not_lost_after_one_week(self):
        due=self.day-timedelta(days=20)
        async with unit_of_work() as session:
            row=Task(user_id=self.uid,title='Monthly overdue',date=due,recurrence='monthly',xp_reward=10)
            session.add(row);await session.flush();identity=row.id
        target=candidate('task.overdue','task',due,{},'Due',identity)
        items,_,_=await collect(self.uid,target=target);self.assertEqual(len(items),1);self.assertEqual(items[0].facts['due_date'],str(due))

    async def test_worker_publishes_all_three_reports_using_existing_planner_only(self):
        await self.enable()
        async with unit_of_work() as session:
            for kind in ('brief.daily','review.night','coach.weekly'):
                await queue.enqueue(session,self.uid,candidate(kind,'routine',self.day,{},'Owned report'),self.day)
        sender=AsyncMock(side_effect=AssertionError('No Telegram opt-in'))
        self.assertEqual(await engine.tick(self.runtime.automations,user_id=self.uid,sender=sender,bootstrap=False),3)
        self.assertEqual(sender.await_count,0)
        async with unit_of_work() as session:
            rows=(await session.scalars(select(Event).where(Event.user_id==self.uid))).all();self.assertEqual(len(rows),3)
            for row in rows:
                self.assertEqual(row.status,'processed');facts=row.payload['candidate']['facts']
                self.assertEqual(facts['version'],'event-briefing/2');self.assertTrue(facts['read_only']);self.assertTrue(facts['confirmation_required'])
                self.assertIn('global_plan',facts['facts']);self.assertIsNone(facts['facts']['finance']['bank_balance'])
            self.assertEqual((await session.get(User,self.uid)).xp,0)
