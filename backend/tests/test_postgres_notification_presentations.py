"""Durable presentation is account-wide and never substitutes for reading."""
import asyncio
import os
import unittest
from datetime import timedelta
from uuid import UUID, uuid4
from unittest.mock import patch
from sqlalchemy import select
from db.session import unit_of_work
from db.models.agent import Event, EventDelivery, Preferences as StoredPreferences, Insight
from db.models.planning import TaskInstance
from services import notification_presentations as presentations, event_engine as engine
from services.event_sources import candidate
import test_postgres_event_engine as fixtures


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class NotificationPresentations(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.EventEngine.asyncSetUp
    asyncTearDown=fixtures.EventEngine.asyncTearDown
    ok=fixtures.EventEngine.ok
    enable=fixtures.EventEngine.enable
    task=fixtures.EventEngine.task
    queue_task=fixtures.EventEngine.queue_task

    async def ready(self):
        event=await self.queue_task()
        await engine.process(event,dry_run=False)
        async with unit_of_work() as session:
            row=await session.scalar(select(EventDelivery).where(EventDelivery.user_id==self.uid))
            return event,row.id

    async def prefs(self,**changes):
        async with unit_of_work() as session:
            row=await session.scalar(select(StoredPreferences).where(StoredPreferences.user_id==self.uid))
            row.settings={**row.settings,**changes}

    async def reserve(self,key=None,**headers):
        return await self.api.post('/automations/presentations/claim',headers={'Idempotency-Key':key or str(uuid4()),**headers})

    async def test_concurrent_tabs_devices_reload_and_read_are_independent(self):
        _,identity=await self.ready()
        results=[self.ok(r) for r in await asyncio.gather(*(self.reserve() for _ in range(8)))]
        self.assertEqual(sum(r['item'] is not None for r in results),1)
        chosen=next(r['item'] for r in results if r['item'])
        self.assertEqual(chosen['delivery_id'],str(identity));self.assertLessEqual(len(chosen['preview']),140)
        self.assertIsNone(self.ok(await self.reserve())['item'])
        async with unit_of_work() as session:
            row=await session.get(EventDelivery,identity)
            key=next(h['presentation_key'] for h in row.history if h['outcome']==presentations.ATTEMPT)
            self.assertEqual(row.status,'available');self.assertIsNone(row.delivered_at)
        ack=f'/automations/presentations/{identity}'
        responses=await asyncio.gather(*(self.api.post(ack,json={'key':key}) for _ in range(4)))
        self.assertTrue(all(self.ok(r)['state']=='presented' for r in responses))
        async with unit_of_work() as session:
            row=await session.get(EventDelivery,identity)
            self.assertEqual(row.status,'available');self.assertEqual(sum(h['outcome']=='presented' for h in row.history),1)
        with patch.object(presentations,'utc_now',return_value=self.now+timedelta(minutes=5)):
            self.assertIsNone(self.ok(await self.reserve())['item'])
        url=f'/automations/deliveries/{identity}'
        request_key=str(uuid4())
        response=self.ok(await self.api.post(url,json={'action':'read'},headers={'Idempotency-Key':request_key}))
        self.assertEqual(response['status'],'delivered')
        self.assertEqual(response['presentation']['state'],'presented')
        self.assertNotIn('presentation_key',str(response))
        self.ok(await self.api.post(url,json={'action':'read'},headers={'Idempotency-Key':request_key}))
        async with unit_of_work() as session:
            row=await session.get(EventDelivery,identity)
            self.assertEqual(sum(h['outcome']=='delivered' for h in row.history),1)

    async def test_lost_response_replay_and_expiry(self):
        _,identity=await self.ready();key=str(uuid4())
        first=self.ok(await self.reserve(key))['item']
        replay=self.ok(await self.reserve(key))
        self.assertTrue(replay['replayed']);self.assertEqual(replay['item'],first)
        with patch.object(presentations,'utc_now',return_value=self.now+timedelta(minutes=2)):
            self.assertIsNone(self.ok(await self.reserve(key))['item'])
        async with unit_of_work() as session:self.assertEqual((await session.get(EventDelivery,identity)).status,'available')

    async def test_ownership_invalid_key_ack_without_claim_and_safe_history(self):
        _,identity=await self.ready()
        self.assertEqual((await self.api.post('/automations/presentations/claim')).status_code,422)
        self.assertEqual((await self.reserve('bad')).status_code,422)
        self.assertEqual((await self.api.post(f'/automations/presentations/{identity}',json={'key':str(uuid4())})).status_code,409)
        self.assertEqual((await self.api.post(f'/automations/presentations/{identity}',json={'key':str(uuid4())},headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertIsNone(self.ok(await self.reserve(Authorization='Bearer bob'))['item'])
        self.ok(await self.reserve())
        events=self.ok(await self.api.get('/automations/events'))['items']
        self.assertNotIn('presentation_key',str(events));self.assertTrue(events[0]['message'])
        self.assertEqual(self.ok(await self.api.get('/automations/state'))['user_id'],str(self.uid))

    async def test_quiet_disabled_zero_cap_and_all_disabled_rules(self):
        await self.ready()
        for changes in [{'automations':False},{'automations':True,'daily_cap':0},
            {'daily_cap':10,'event_automation':{'quiet_start':'00:00','quiet_end':'23:59','rules':{'task.overdue':{'priority':'high'}}}}]:
            await self.prefs(**changes)
            self.assertIsNone(self.ok(await self.reserve())['item'])
        from event_contracts import CATALOG
        await self.prefs(event_automation={'rules':{kind:{'enabled':False} for kind in CATALOG}})
        self.assertIsNone(self.ok(await self.reserve())['item'])

    async def test_resolved_source_and_feedback_block_stale_popup(self):
        event,_=await self.ready()
        async with unit_of_work() as session:
            session.add(TaskInstance(user_id=self.uid,task_id=UUID(event['entity_id']),date=self.day-timedelta(days=2),completed=True,status='done'))
        self.assertIsNone(self.ok(await self.reserve())['item'])

    async def test_feedback_is_rechecked_and_failed_read_does_not_change_history(self):
        _,identity=await self.ready()
        async with unit_of_work() as session:
            insight=await session.scalar(select(Insight).where(Insight.user_id==self.uid));insight.feedback='dismiss'
        self.assertIsNone(self.ok(await self.reserve())['item'])
        async with unit_of_work() as session:
            insight=await session.scalar(select(Insight).where(Insight.user_id==self.uid));insight.feedback=None
        self.ok(await self.reserve())
        self.assertEqual((await self.api.post(f'/automations/deliveries/{identity}',json={'action':'read'})).status_code,400)
        async with unit_of_work() as session:
            row=await session.get(EventDelivery,identity);self.assertEqual(row.status,'available')
            self.assertEqual(presentations.presentation_state(row)['state'],'claimed')

    async def test_never_feedback_from_previous_period_blocks_same_source_rule(self):
        await self.ready()
        async with unit_of_work() as session:
            insight=await session.scalar(select(Insight).where(Insight.user_id==self.uid))
            insight.feedback='never';insight.date=self.day-timedelta(days=1);insight.evidence={}
        self.assertIsNone(self.ok(await self.reserve())['item'])

    async def test_old_backlog_routine_opt_in_and_grouped_latest_alert(self):
        _,identity=await self.ready()
        async with unit_of_work() as session:
            for n in range(25):
                item=candidate('brief.daily','routine',self.day-timedelta(days=n+1),{},'Resumo antigo')
                event=Event(user_id=self.uid,event_type=item.event_type,status='processed',payload={'candidate':item.model_dump(mode='json')})
                session.add(event);await session.flush()
                session.add(EventDelivery(user_id=self.uid,event_id=event.id,channel='in_app',status='available'))
            item=candidate('brief.daily','routine',self.day,{},'Resumo atual')
            event=Event(user_id=self.uid,event_type=item.event_type,status='processed',payload={'candidate':item.model_dump(mode='json')})
            session.add(event);await session.flush()
            session.add(EventDelivery(user_id=self.uid,event_id=event.id,channel='in_app',status='available'))
        chosen=self.ok(await self.reserve())['item'];self.assertEqual(chosen['delivery_id'],str(identity))
        await self.prefs(event_automation={'routine_popups':True})
        with patch.object(presentations,'utc_now',return_value=self.now+timedelta(minutes=2)):
            chosen=self.ok(await self.reserve())['item']
        self.assertEqual(chosen['event_type'],'brief.daily');self.assertLess(len(chosen['preview']),100)

    async def test_priority_order_groups_other_items_and_old_client_preserves_preference(self):
        await self.ready()
        async with unit_of_work() as session:
            for n in range(3):
                item=candidate('brief.daily','routine',self.day,{},'Resumo atual')
                event=Event(user_id=self.uid,event_type=item.event_type,status='processed',payload={'candidate':item.model_dump(mode='json')})
                session.add(event);await session.flush()
                session.add(EventDelivery(user_id=self.uid,event_id=event.id,channel='in_app',status='available'))
        await self.prefs(event_automation={'routine_popups':True,'rules':{'task.overdue':{'priority':'high'}}})
        selected=self.ok(await self.reserve())['item'];self.assertEqual(selected['event_type'],'task.overdue');self.assertEqual(selected['grouped_count'],3)
        policy=self.ok(await self.api.get('/automations/state'))['policy'];policy.pop('routine_popups')
        key=str(uuid4())
        self.ok(await self.api.put('/automations/policy',json={'enabled':True,'daily_cap':10,'policy':policy},headers={'Idempotency-Key':key}))
        self.assertTrue(self.ok(await self.api.get('/automations/state'))['policy']['routine_popups'])
        self.assertEqual((await self.api.put('/automations/policy',json={'enabled':True,'daily_cap':10,'policy':{**policy,'routine_popups':False}},headers={'Idempotency-Key':key})).status_code,409)
        self.ok(await self.http.put('/ai/preferences',json={'event_automation':policy}))
        self.assertTrue(self.ok(await self.api.get('/automations/state'))['policy']['routine_popups'])

    async def test_ten_pending_deliveries_become_one_preview_and_remain_unread(self):
        await self.ready()
        from services import event_queue as queue
        from services.event_sources import collect
        for _ in range(9):
            identity=await self.task()
            items,_,_=await collect(self.uid,now=self.now,target=candidate('task.overdue','task',self.day-timedelta(days=2),{},'Reason',identity))
            async with unit_of_work() as session:await queue.enqueue(session,self.uid,items[0],self.day)
            event=await queue.claim(self.uid);await engine.process(event,dry_run=False)
        result=self.ok(await self.reserve())['item'];self.assertEqual(result['grouped_count'],9)
        with patch.object(presentations,'utc_now',return_value=self.now+timedelta(minutes=5)):
            self.assertIsNone(self.ok(await self.reserve())['item'])
        async with unit_of_work() as session:
            rows=(await session.scalars(select(EventDelivery).where(EventDelivery.user_id==self.uid))).all()
            self.assertEqual(len(rows),10);self.assertTrue(all(r.status=='available' for r in rows))
            self.assertEqual(sum(presentations.presentation_state(r)['state']=='grouped' for r in rows),9)
