import asyncio
import os
import unittest
from datetime import datetime,timezone,timedelta,time
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func,delete
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
