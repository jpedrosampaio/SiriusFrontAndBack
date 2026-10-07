import os
import asyncio
import unittest
from unittest.mock import patch
from sqlalchemy import select,func
from db.models.health import WorkoutLog
from db.models.identity import User
from db.session import unit_of_work
import test_postgres_runtime_workout_logs as log_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeWorkoutDaily(unittest.IsolatedAsyncioTestCase):
    ok=log_tests.RuntimeWorkoutLogs.ok
    asyncTearDown=log_tests.RuntimeWorkoutLogs.asyncTearDown

    async def asyncSetUp(self):
        await log_tests.RuntimeWorkoutLogs.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        p=patch('services.workout_daily_routes.account',account);p.start();self.patches.append(p)
        self.plan=self.ok(await self.http.post('/api/workout-plans',json={'name':'Diário','exercises':[{'name':'Supino'},{'name':'Remada'}]}))
        self.url='/api/daily-workout-status/'+self.plan['plan_id']

    async def test_concurrent_completion_without_key_one_log_xp_and_reset(self):
        self.assertFalse(self.ok(await self.http.get(self.url))['completed'])
        self.ok(await self.http.post(self.url+'/toggle/0'))
        results=[self.ok(r) for r in await asyncio.gather(*(self.http.post(self.url+'/complete',json={'duration_minutes':30}) for _ in range(8)))]
        self.assertEqual(len({r['log_id'] for r in results}),1)
        self.assertEqual(results[0]['xp_earned'],35)
        self.assertTrue(self.ok(await self.http.get(self.url))['completed'])
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User,self.uid)).xp,35)
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutLog).where(WorkoutLog.user_id==self.uid)),1)
        self.ok(await self.http.post(self.url+'/reset'))
        status=self.ok(await self.http.get(self.url));self.assertFalse(status['completed']);self.assertEqual(status['exercises_status'],{})
        self.assertEqual(self.ok(await self.http.get('/api/workouts')),[])
        async with unit_of_work() as session:self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_owner_invalid_index_and_transaction_rollback(self):
        for method,suffix,kwargs in [('get','',{}),('post','/toggle/0',{}),('post','/complete',{'json':{}}),('post','/reset',{})]:
            response=await getattr(self.http,method)(self.url+suffix,headers={'Authorization':'Bearer bob'},**kwargs)
            self.assertEqual(response.status_code,404)
        self.assertEqual((await self.http.post(self.url+'/toggle/2')).status_code,422)
        with patch('services.workout_logs.apply_xp',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):await self.http.post(self.url+'/complete',json={})
        self.assertFalse(self.ok(await self.http.get(self.url))['completed']);self.assertEqual(self.ok(await self.http.get('/api/workouts')),[])

    async def test_deleting_completed_log_clears_daily_link(self):
        result=self.ok(await self.http.post(self.url+'/complete',json={}))
        self.ok(await self.http.delete('/api/workouts/'+result['log_id']))
        self.assertFalse(self.ok(await self.http.get(self.url))['completed'])
        self.ok(await self.http.post(self.url+'/complete',json={}))
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User,self.uid)).xp,20)
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutLog).where(WorkoutLog.user_id==self.uid)),1)
