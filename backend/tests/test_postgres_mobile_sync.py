import asyncio
import os
import unittest
from datetime import datetime,timezone
from decimal import Decimal
from uuid import uuid4,UUID
from unittest.mock import patch
from sqlalchemy import select,func,event
from sqlalchemy.orm import Session
from db.session import unit_of_work
from db.models.identity import User,ActivityReceipt
from db.models.planning import Task,Habit,HabitCheck,GoalCheck,TaskInstance
from db.models.finance import FinancialTransaction
import test_postgres_runtime_dashboard as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class MobileSync(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeDashboard.ok
    asyncTearDown=setup.RuntimeDashboard.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeDashboard.asyncSetUp(self)
        async def account(request):
            from fastapi import HTTPException
            if request.headers.get('Authorization')=='Bearer unauthenticated':raise HTTPException(401,'Not authenticated')
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid)}
        p=patch('services.mobile_sync.account',account);p.start();self.patches.append(p)

    def payload(self,kind='tasks',identity=None,operation='INSERT',data=None):
        return {'record_id':str(identity or uuid4()),'operation':operation,'timestamp':datetime.now(timezone.utc).isoformat(),
            'data':data if data is not None else {'title':'Study','date':self.today.isoformat()}}

    async def sync(self,kind,payload,**kwargs):return await self.http.post('/api/sync/'+kind,json=payload,**kwargs)

    async def test_security_owner_ids_fields_and_internal_tables(self):
        payload=self.payload();self.assertEqual((await self.sync('tasks',payload,headers={'Authorization':'Bearer unauthenticated'})).status_code,401)
        for kind in ('users','user_sessions','telegram_links','unknown'):
            self.assertEqual((await self.sync(kind,payload)).status_code,403)
            self.assertEqual((await self.http.get(f'/api/sync/{kind}/{self.uid}')).status_code,403)
        self.assertEqual((await self.http.get(f'/api/sync/tasks/{self.bob}')).status_code,403)
        for data,status in [({'user_id':str(self.bob)},403),({'task_id':str(uuid4())},422),({'password':'injected'},422),({'$set':{}},422),({'title':{'$ne':None}},422)]:
            value={**payload,'data':data};self.assertEqual((await self.sync('tasks',value)).status_code,status)
        for key,value in [('record_id',''),('record_id','$where'),('operation','UPSERT')]:
            self.assertEqual((await self.sync('tasks',{**payload,key:value})).status_code,422)
        self.ok(await self.sync('tasks',payload))
        self.assertEqual((await self.sync('tasks',payload,headers={'Authorization':'Bearer bob'})).status_code,409)
        self.assertEqual((await self.sync('tasks',self.payload(identity=payload['record_id'],operation='UPDATE',data={'completed':True}),headers={'Authorization':'Bearer bob'})).status_code,404)
        pulled=self.ok(await self.http.get(f'/api/sync/tasks/{self.uid}'));self.assertEqual(len(pulled),1)
        self.assertNotIn('password',str(pulled));self.assertNotIn('gemini',str(pulled))

    async def test_task_completion_reward_partial_update_replay_and_delete(self):
        payload=self.payload(data={'title':'Study','date':self.today.isoformat(),'xp_reward':999999})
        self.ok(await self.sync('tasks',payload));identity=payload['record_id']
        update=self.payload(identity=identity,operation='UPDATE',data={'completed':1,'xp_reward':90000})
        values=[self.ok(r) for r in await asyncio.gather(*(self.sync('tasks',update) for _ in range(8)))]
        self.assertEqual(sum(r.get('replayed',False) for r in values),7)
        async with unit_of_work() as session:
            user=await session.get(User,self.uid);self.assertEqual(user.xp,10)
            task=await session.get(Task,UUID(identity));self.assertEqual(task.xp_reward,10);self.assertEqual(task.title,'Study')
            self.assertEqual(await session.scalar(select(func.count()).select_from(TaskInstance).where(TaskInstance.task_id==task.id)),1)
        rows=self.ok(await self.http.get(f'/api/sync/tasks/{self.uid}'));self.assertTrue(rows[0]['completed'])
        self.ok(await self.sync('tasks',self.payload(identity=identity,operation='UPDATE',data={'completed':0})))
        async with unit_of_work() as session:self.assertEqual((await session.get(User,self.uid)).xp,0)
        for _ in range(2):self.ok(await self.sync('tasks',self.payload(identity=identity,operation='DELETE',data={})))
        self.assertEqual(self.ok(await self.http.get(f'/api/sync/tasks/{self.uid}')),[])
        self.assertEqual((await self.sync('tasks',self.payload(operation='UPDATE',data={'completed':1}))).status_code,404)

    async def test_habit_goal_lists_normalized_and_money_atomic(self):
        habit=self.payload(data={'name':'Read','completions':'["2026-10-04","2026-10-04"]'})
        self.ok(await self.sync('habits',habit))
        bad=self.payload(identity=habit['record_id'],operation='UPDATE',data={'completions':'invalid JSON'})
        self.assertEqual((await self.sync('habits',bad)).status_code,422)
        goal=self.payload(data={'title':'Goal','target_date':self.today.isoformat(),'daily_checks':'["2026-10-04"]','sprints':'[]'})
        self.ok(await self.sync('goals',goal))
        money=self.payload(data={'type':'expense','date':self.today.isoformat(),'amount':'0.10','category':'food'})
        self.ok(await self.sync('transactions',money));self.ok(await self.sync('transactions',money))
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User,self.uid)).xp,13)
            self.assertEqual(await session.scalar(select(func.count()).select_from(HabitCheck).where(HabitCheck.user_id==self.uid)),1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(GoalCheck).where(GoalCheck.user_id==self.uid)),1)
            rows=(await session.scalars(select(FinancialTransaction).where(FinancialTransaction.user_id==self.uid))).all()
            self.assertEqual(len(rows),1);self.assertEqual(rows[0].amount,Decimal('0.10'))
        for kind in ('habits','goals','transactions'):self.assertEqual(len(self.ok(await self.http.get(f'/api/sync/{kind}/{self.uid}'))),1)

    async def test_failed_sync_rolls_back_checks_xp_and_receipt(self):
        payload=self.payload(data={'name':'Read','completions':['2026-10-04']})
        def fail(session,*args):
            if any(isinstance(row,HabitCheck) for row in session.new):raise RuntimeError('injected')
        event.listen(Session,'before_flush',fail)
        try:
            with self.assertRaises(RuntimeError):await self.sync('habits',payload)
        finally:event.remove(Session,'before_flush',fail)
        async with unit_of_work() as session:
            self.assertIsNone(await session.get(Habit,UUID(payload['record_id'])))
            self.assertEqual((await session.get(User,self.uid)).xp,0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(ActivityReceipt).where(ActivityReceipt.user_id==self.uid)),0)
        self.ok(await self.sync('habits',payload))
