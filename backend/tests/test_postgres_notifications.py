import asyncio
import os
import unittest
from datetime import datetime,timezone,timedelta,time
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func,delete
from sqlalchemy.dialects.postgresql import insert
from db.models.agent import Preferences as StoredPreferences
from db.session import unit_of_work
from db.models.notifications import Notification,NotificationDelivery
from db.models.studies import StudyArea,StudyProgram,Notebook,StudySchedule
import test_postgres_runtime_dashboard as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class Notifications(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeDashboard.ok
    asyncTearDown=setup.RuntimeDashboard.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeDashboard.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid)}
        p=patch('services.notifications.account',account);p.start();self.patches.append(p)
        # Midnight delivery tests explicitly opt out of quiet hours.
        async with unit_of_work() as session:
            await session.execute(insert(StoredPreferences).values(user_id=self.uid,settings={'quiet_start':0,'quiet_end':0})
                .on_conflict_do_update(index_elements=['user_id'],set_={'settings':{'quiet_start':0,'quiet_end':0}}))

    async def test_quiet_hours_defer_one_shot_daily_weekly_and_claim_after_silence(self):
        rows=[await self.create(scheduled_time='23:59',repeat=repeat,repeat_days=['sunday'] if repeat=='weekly' else [])
            for repeat in ('none','daily','weekly')]
        instant=datetime(2026,10,5,2,59,tzinfo=timezone.utc)
        async with unit_of_work() as session:
            prefs=await session.scalar(select(StoredPreferences).where(StoredPreferences.user_id==self.uid))
            prefs.settings={'quiet_start':22,'quiet_end':8}
            for row in rows:(await session.get(Notification,UUID(row['notification_id']))).created_at=instant-timedelta(minutes=10)
        with patch('services.notifications.utc_now',return_value=instant):
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check')),[])
        async with unit_of_work() as session:
            for row in rows:
                saved=await session.get(Notification,UUID(row['notification_id']))
                self.assertIsNone(saved.last_sent);self.assertIsNone(saved.last_occurrence)
        with patch('services.notifications.utc_now',return_value=datetime(2026,10,5,11,tzinfo=timezone.utc)):
            results=[self.ok(r) for r in await asyncio.gather(*(self.http.get('/api/notifications/check') for _ in range(6)))]
            self.assertEqual(sum(len(r) for r in results),3)
            self.assertEqual({r['occurrence_date'] for batch in results for r in batch},{'2026-10-04'})
        with patch('services.notifications.utc_now',return_value=datetime(2026,10,6,11,tzinfo=timezone.utc)):
            self.assertEqual([r['repeat'] for r in self.ok(await self.http.get('/api/notifications/check'))],['daily'])
        with patch('services.notifications.utc_now',return_value=datetime(2026,10,12,11,tzinfo=timezone.utc)):
            self.assertEqual({r['repeat'] for r in self.ok(await self.http.get('/api/notifications/check'))},{'daily','weekly'})

    async def test_browser_only_occurrence_waits_for_permission_and_other_channels_are_not_consumed(self):
        instant=datetime(2026,10,15,12,tzinfo=timezone.utc)
        browser=await self.create(scheduled_time='08:59',channels=['browser'])
        email=await self.create(scheduled_time='08:59',channels=['email'])
        async with unit_of_work() as session:
            for row in (browser,email):(await session.get(Notification,UUID(row['notification_id']))).created_at=instant-timedelta(days=1)
        with patch('services.notifications.utc_now',return_value=instant):
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check')),[])
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check?browser_allowed=true',headers={'Authorization':'Bearer bob'})),[])
            values=self.ok(await self.http.get('/api/notifications/check?browser_allowed=true'))
            self.assertEqual([r['notification_id'] for r in values],[browser['notification_id']])
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check?browser_allowed=true')),[])
        async with unit_of_work() as session:
            self.assertIsNone((await session.get(Notification,UUID(email['notification_id']))).last_sent)

    async def test_lookahead_cannot_cross_into_quiet_hours_or_starve_already_due_rows(self):
        instant=datetime(2026,10,16,0,59,tzinfo=timezone.utc) # 21:59 in the account timezone
        future=await self.create(scheduled_time='22:00')
        past=await self.create(scheduled_time='21:58')
        async with unit_of_work() as session:
            prefs=await session.scalar(select(StoredPreferences).where(StoredPreferences.user_id==self.uid))
            prefs.settings={'quiet_start':22,'quiet_end':8}
            for row in (future,past):(await session.get(Notification,UUID(row['notification_id']))).created_at=instant-timedelta(minutes=10)
            session.add_all([Notification(user_id=self.uid,title='Future quiet slot',message='Defer',type='reminder',category='custom',
                repeat='daily',scheduled_time=time(22),created_at=instant-timedelta(minutes=9)) for _ in range(50)])
        with patch('services.notifications.utc_now',return_value=instant):
            self.assertEqual([r['notification_id'] for r in self.ok(await self.http.get('/api/notifications/check'))],[past['notification_id']])
        with patch('services.notifications.utc_now',return_value=instant+timedelta(minutes=1)):
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check')),[])
        async with unit_of_work() as session:self.assertIsNone((await session.get(Notification,UUID(future['notification_id']))).last_sent)
        with patch('services.notifications.utc_now',return_value=datetime(2026,10,16,11,tzinfo=timezone.utc)):
            values=[*self.ok(await self.http.get('/api/notifications/check')),*self.ok(await self.http.get('/api/notifications/check'))]
            self.assertEqual(len(values),51)
            self.assertEqual({r['occurrence_date'] for r in values},{'2026-10-15'})
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check')),[])

    async def test_future_rows_do_not_starve_old_due_one_shot_in_bounded_query(self):
        instant=datetime(2026,10,15,12,tzinfo=timezone.utc)
        old=await self.create(scheduled_time='08:30')
        async with unit_of_work() as session:
            (await session.get(Notification,UUID(old['notification_id']))).created_at=instant-timedelta(days=2,hours=2)
            session.add_all([Notification(user_id=self.uid,title='Future',message='Not due',type='reminder',category='custom',
                repeat='daily',scheduled_time=time(18),created_at=instant-timedelta(hours=1)) for _ in range(500)])
        with patch('services.notifications.utc_now',return_value=instant):
            values=self.ok(await self.http.get('/api/notifications/check'))
            self.assertEqual([r['notification_id'] for r in values],[old['notification_id']])

    async def test_one_shot_created_during_its_scheduled_minute_is_not_delayed_a_day(self):
        instant=datetime(2026,10,15,12,0,45,tzinfo=timezone.utc)
        row=await self.create(scheduled_time='09:00')
        async with unit_of_work() as session:(await session.get(Notification,UUID(row['notification_id']))).created_at=instant-timedelta(seconds=15)
        with patch('services.notifications.utc_now',return_value=instant):
            values=self.ok(await self.http.get('/api/notifications/check'))
            self.assertEqual([r['notification_id'] for r in values],[row['notification_id']])
            self.assertEqual(values[0]['occurrence_date'],'2026-10-15')
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check')),[])

    async def native_row(self):
        instant=datetime(2026,10,15,12,tzinfo=timezone.utc)
        row=await self.create(scheduled_time='08:59',channels=['browser'])
        async with unit_of_work() as session:
            (await session.get(Notification,UUID(row['notification_id']))).created_at=instant-timedelta(days=1)
        return row,instant

    async def test_native_reservation_confirmation_and_lost_ack_are_separate_and_idempotent(self):
        row,instant=await self.native_row()
        with patch('services.notifications.utc_now',return_value=instant):
            values=[self.ok(r) for r in await asyncio.gather(*(self.http.get('/api/notifications/check?browser_allowed=true') for _ in range(5)))]
            self.assertEqual(sum(map(len,values)),1)
            claim=next(batch[0]['native_claim'] for batch in values if batch)
            async with unit_of_work() as session:
                saved=await session.get(Notification,UUID(row['notification_id']))
                self.assertIsNone(saved.last_sent);self.assertIsNone(saved.last_occurrence)
            listing=self.ok(await self.http.get('/api/notifications'))[0]
            self.assertEqual(listing['native_presentation']['state'],'reserved')
            self.assertNotIn('claim_id',listing['native_presentation'])
            ack={'claims':[claim],'outcome':'accepted'}
            for response in await asyncio.gather(*(self.http.post('/api/notifications/native-presentations',json=ack) for _ in range(4))):self.ok(response)
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check?browser_allowed=true')),[])
            self.assertEqual((await self.http.post('/api/notifications/native-presentations',json={**ack,'outcome':'failed'})).status_code,409)
        async with unit_of_work() as session:
            saved=await session.get(Notification,UUID(row['notification_id']));self.assertEqual(saved.last_sent,instant)
            self.assertEqual(await session.scalar(select(func.count()).select_from(NotificationDelivery).where(NotificationDelivery.user_id==self.uid)),1)

    async def test_failed_native_attempt_preserves_occurrence_for_another_capable_device_and_fences_old_nonce(self):
        row,instant=await self.native_row()
        with patch('services.notifications.utc_now',return_value=instant):
            old=self.ok(await self.http.get('/api/notifications/check?browser_allowed=true'))[0]['native_claim']
            self.ok(await self.http.post('/api/notifications/native-presentations',json={'claims':[old],'outcome':'failed'}))
            async with unit_of_work() as session:self.assertIsNone((await session.get(Notification,UUID(row['notification_id']))).last_sent)
            new=self.ok(await self.http.get('/api/notifications/check?browser_allowed=true'))[0]['native_claim']
            self.assertNotEqual(old['claim_id'],new['claim_id'])
            self.assertEqual((await self.http.post('/api/notifications/native-presentations',json={'claims':[old],'outcome':'accepted'})).status_code,409)
            self.ok(await self.http.post('/api/notifications/native-presentations',json={'claims':[new],'outcome':'accepted'}))

    async def test_native_batch_foreign_owner_rolls_back_all_acknowledgements(self):
        from uuid import uuid4
        row,instant=await self.native_row()
        with patch('services.notifications.utc_now',return_value=instant):
            claim=self.ok(await self.http.get('/api/notifications/check?browser_allowed=true'))[0]['native_claim']
            foreign={**claim,'notification_id':str(uuid4())}
            self.assertEqual((await self.http.post('/api/notifications/native-presentations',json={'claims':[claim,foreign],'outcome':'accepted'})).status_code,404)
            self.assertEqual((await self.http.post('/api/notifications/native-presentations',headers={'Authorization':'Bearer bob'},json={'claims':[claim],'outcome':'accepted'})).status_code,404)
            async with unit_of_work() as session:self.assertIsNone((await session.get(Notification,UUID(row['notification_id']))).last_sent)
            self.assertEqual(self.ok(await self.http.get('/api/notifications'))[0]['native_presentation']['state'],'reserved')

    async def test_native_uncertain_retry_requires_explicit_risk_and_preserves_history(self):
        from uuid import uuid4
        from db.models.identity import ActivityReceipt
        row,instant=await self.native_row()
        with patch('services.notifications.utc_now',return_value=instant):
            claim=self.ok(await self.http.get('/api/notifications/check?browser_allowed=true'))[0]['native_claim']
            self.ok(await self.http.post('/api/notifications/native-presentations',json={'claims':[claim],'outcome':'uncertain'}))
            prior=self.ok(await self.http.get('/api/notifications'))[0]['native_presentation']
            url='/api/notifications/'+row['notification_id']+'/retry-native'
            body={'occurrence':prior['occurrence'],'attempted_at':prior['attempted_at']}
            self.assertEqual((await self.http.post(url,json=body,headers={'Idempotency-Key':str(uuid4())})).status_code,409)
            headers={'Idempotency-Key':str(uuid4())};body['duplicate_risk_accepted']=True
            first=self.ok(await self.http.post(url,json=body,headers=headers))
            replay=self.ok(await self.http.post(url,json=body,headers=headers))
            self.assertEqual(first['item']['native_claim'],replay['item']['native_claim'])
            self.assertNotEqual(first['item']['native_claim']['claim_id'],claim['claim_id'])
            self.assertEqual((await self.http.post('/api/notifications/native-presentations',json={'claims':[claim],'outcome':'accepted'})).status_code,409)
        async with unit_of_work() as session:
            ledger=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==self.uid,ActivityReceipt.request_key.like('native_notice_%')))
            self.assertEqual([h['state'] for h in ledger.result['history']],['reserved','uncertain','reserved'])

    async def test_native_reserved_rows_do_not_starve_other_channels_and_failures_have_bounded_retries(self):
        _,instant=await self.native_row()
        async with unit_of_work() as session:
            session.add_all([Notification(user_id=self.uid,title='Native',message='Private',type='reminder',category='custom',
                channels=['browser'],repeat='none',scheduled_time=time(8,59),created_at=instant-timedelta(days=1)) for _ in range(50)])
        with patch('services.notifications.utc_now',return_value=instant):
            first=self.ok(await self.http.get('/api/notifications/check?browser_allowed=true'))
            second=self.ok(await self.http.get('/api/notifications/check?browser_allowed=true'))
            self.assertEqual(len(first),50);self.assertEqual(len(second),1)
            claim=second[0]['native_claim']
            for attempt in range(3):
                self.ok(await self.http.post('/api/notifications/native-presentations',json={'claims':[claim],'outcome':'failed'}))
                values=self.ok(await self.http.get('/api/notifications/check?browser_allowed=true'))
                if attempt<2:claim=values[0]['native_claim']
                else:self.assertEqual(values,[])
            async with unit_of_work() as session:
                self.assertEqual(await session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id==self.uid,Notification.last_sent.is_not(None))),0)

    async def test_ambiguous_dst_occurrence_is_claimed_once_in_account_timezone(self):
        from db.models.identity import User
        row=await self.create(scheduled_time='01:30',repeat='daily')
        async with unit_of_work() as session:
            (await session.get(User,self.uid)).timezone='America/New_York'
            (await session.get(Notification,UUID(row['notification_id']))).created_at=datetime(2026,11,1,4,tzinfo=timezone.utc)
        with patch('services.notifications.utc_now',return_value=datetime(2026,11,1,6,31,tzinfo=timezone.utc)):
            self.assertEqual(len(self.ok(await self.http.get('/api/notifications/check?timezone_offset=999'))),1)
        with patch('services.notifications.utc_now',return_value=datetime(2026,11,1,7,tzinfo=timezone.utc)):
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check')),[])

    async def create(self,**values):
        return self.ok(await self.http.post('/api/notifications',json={'title':'Reminder','message':'Study',**values}))

    async def test_crud_owner_validation_toggle_and_delivery_receipt(self):
        row=await self.create(scheduled_time='08:00',repeat='daily');url='/api/notifications/'+row['notification_id']
        for method,suffix in [('patch','/toggle'),('delete',''),('post','/send?channel=browser')]:
            self.assertEqual((await getattr(self.http,method)(url+suffix,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.post('/api/notifications',json={'title':'X','message':'','scheduled_time':'24:00'})).status_code,422)
        toggles=[self.ok(r) for r in await asyncio.gather(*(self.http.patch(url+'/toggle') for _ in range(4)))]
        self.assertEqual(sum(r['enabled'] for r in toggles),2)
        logs=[self.ok(r) for r in await asyncio.gather(*(self.http.post(url+'/send?channel=browser') for _ in range(6)))]
        self.assertEqual(len({r['log_id'] for r in logs}),1)
        self.assertEqual((await self.http.post(url+'/send?channel=invalid')).status_code,422)
        self.ok(await self.http.delete(url))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(NotificationDelivery).where(NotificationDelivery.user_id==self.uid)),0)

    async def test_claim_concurrency_local_midnight_weekday_and_one_shot(self):
        instant=datetime(2026,10,5,2,59,tzinfo=timezone.utc) # Sunday 23:59, next slot Monday midnight
        row=await self.create(scheduled_time='00:00',repeat='weekly',repeat_days=['monday'])
        once=await self.create(scheduled_time='23:59')
        async with unit_of_work() as session:
            for value in (row,once):(await session.get(Notification,UUID(value['notification_id']))).created_at=instant-timedelta(minutes=10)
        with patch('services.notifications.utc_now',return_value=instant):
            results=[self.ok(r) for r in await asyncio.gather(*(self.http.get('/api/notifications/check?timezone_offset=0') for _ in range(6)))]
            self.assertEqual(sum(len(r) for r in results),2)
        with patch('services.notifications.utc_now',return_value=instant+timedelta(minutes=1)):
            self.assertEqual(self.ok(await self.http.get('/api/notifications/check')),[])
        with patch('services.notifications.utc_now',return_value=instant+timedelta(days=7)):
            values=self.ok(await self.http.get('/api/notifications/check'));self.assertEqual([v['notification_id'] for v in values],[row['notification_id']])
        async with unit_of_work() as session:
            saved=await session.get(Notification,UUID(once['notification_id']));self.assertIsNotNone(saved.last_sent.tzinfo)

    async def test_schedule_reminders_dedup_prior_day_archive_and_cascade(self):
        async with unit_of_work() as session:
            area=StudyArea(user_id=self.uid,name='Study');session.add(area);await session.flush()
            program=StudyProgram(user_id=self.uid,area_id=area.id,name='Exam');session.add(program);await session.flush();pid=program.id
            book=Notebook(user_id=self.uid,area_id=area.id,program_id=pid,name='Law');session.add(book);await session.flush()
            schedule=StudySchedule(user_id=self.uid,notebook_id=book.id,day_of_week='monday',start_time=time(0,2),end_time=time(1));session.add(schedule);await session.flush();sid=schedule.id
        url=f'/api/study/programs/{pid}/create-reminders'
        results=[self.ok(r) for r in await asyncio.gather(*(self.http.post(url,json={'minutes_before':5,'include_end_reminder':True}) for _ in range(5)))]
        self.assertEqual(sum(r['created'] for r in results),2)
        values=self.ok(await self.http.get('/api/notifications'));self.assertEqual(len(values),2)
        first=next(n for n in values if n['scheduled_time']=='23:57');self.assertEqual(first['repeat_days'],['sunday'])
        self.assertEqual((await self.http.post(url,json={},headers={'Authorization':'Bearer bob'})).status_code,404)
        async with unit_of_work() as session:
            row=await session.get(StudyProgram,pid);row.archived_at=datetime.now(timezone.utc)
        self.assertEqual(self.ok(await self.http.get('/api/notifications')),[])
        async with unit_of_work() as session:
            await session.execute(delete(StudySchedule).where(StudySchedule.id==sid))
            self.assertEqual(await session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id==self.uid)),0)
