import os
import asyncio
import unittest
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func
from db.models.health import WorkoutLog,WorkoutSession,WorkoutSet
from db.models.identity import User
from db.repositories.health import HealthRepository
from db.session import unit_of_work
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeWorkoutSessions(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        async with unit_of_work() as session:
            days=[{'week':week,'day_label':f'Semana {week} - Dia {day}','exercises':[{'name':'Supino','sets':3,'reps':12}]} for week in range(1,5) for day in range(1,6)]
            self.pid=(await HealthRepository(session).create_plan(self.uid,name='4 semanas',days=days)).id
        async def account(request): return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.workout_auth=patch('services.workout_session_routes.account',account); self.workout_auth.start()

    async def asyncTearDown(self):
        self.workout_auth.stop(); await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def start(self,headers=None):
        return await self.http.post('/api/workout-sessions/start',json={'plan_id':str(self.pid),'day_index':5},headers=headers or {})

    async def test_start_revision_and_completion_serialize_and_replay(self):
        starts=await asyncio.gather(*(self.start() for _ in range(8)))
        self.assertEqual(sum(r.status_code==200 for r in starts),1)
        self.assertTrue(all(r.status_code in (200,409) for r in starts))
        started=next(r.json() for r in starts if r.status_code==200); sid=started['session_id']
        self.assertEqual(started['day_index'],5); self.assertIn('Semana 2',started['plan_name'])
        self.assertEqual(started['exercises'][0]['sets_data'],[])
        path='/api/workout-sessions/'+sid
        changes=await asyncio.gather(*(self.http.patch(path+'/exercise/0',json={'sets_data':[{'weight':str(weight),'reps':12,'rpe':'','completed':True}],
            'completed':True,'revision':0}) for weight in (10,12)))
        self.assertEqual(sorted(r.status_code for r in changes),[200,409])
        active=self.ok(await self.http.get('/api/workout-sessions/active'))['session']
        self.assertEqual(active['revision'],1); self.assertEqual(active['exercises'][0]['sets_completed'],1)
        completed=await asyncio.gather(*(self.http.post(path+'/complete',json={'difficulty':3}) for _ in range(10)))
        for r in completed: self.ok(r)
        self.assertEqual(sum(bool(r.json().get('replayed')) for r in completed),9)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutLog).where(WorkoutLog.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,12)
        self.assertFalse(self.ok(await self.http.get('/api/workout-sessions/active'))['active'])
        self.assertEqual(self.ok(await self.http.get('/api/workout-sessions'))[0]['session_id'],sid)

    async def test_owner_validation_and_abandon(self):
        foreign={'Authorization':'Bearer bob'}
        self.assertEqual((await self.start(foreign)).status_code,404)
        for index in (-1,20,'2',True):
            response=await self.http.post('/api/workout-sessions/start',json={'plan_id':str(self.pid),'day_index':index})
            self.assertEqual(response.status_code,422,response.text)
        self.assertFalse(self.ok(await self.http.get('/api/workout-sessions/active'))['active'])
        sid=self.ok(await self.start())['session_id']; path='/api/workout-sessions/'+sid
        for endpoint in ('complete','abandon'):
            self.assertEqual((await self.http.post(path+'/'+endpoint,json={},headers=foreign)).status_code,404)
        self.assertEqual((await self.http.patch(path+'/exercise/0',json={'completed':True},headers=foreign)).status_code,404)
        self.assertEqual(self.ok(await self.http.get('/api/workout-sessions',headers=foreign)),[])
        for body in ({'completed':'yes'},{'sets_completed':4},{'sets_data':[{'weight':'nan'}]}, {'sets_data':[{}]*4},{'current_exercise_idx':10}):
            self.assertEqual((await self.http.patch(path+'/exercise/0',json=body)).status_code,422)
        self.ok(await self.http.post(path+'/abandon'))
        self.assertEqual(self.ok(await self.http.get('/api/workout-sessions'))[0]['status'],'abandoned')

    async def test_completion_failure_rolls_back_log_status_and_xp(self):
        sid=self.ok(await self.start())['session_id']; path='/api/workout-sessions/'+sid
        with patch('services.workouts.apply_xp',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError): await self.http.post(path+'/complete',json={})
        self.assertTrue(self.ok(await self.http.get('/api/workout-sessions/active'))['active'])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutLog).where(WorkoutLog.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)
        self.ok(await self.http.post(path+'/complete',json={}))

    async def test_set_replacement_is_normalized_and_not_duplicated(self):
        sid=self.ok(await self.start())['session_id']; path='/api/workout-sessions/'+sid+'/exercise/0'
        for revision,weight in [(0,'10.125'),(1,'12.500')]:
            result=self.ok(await self.http.patch(path,json={'revision':revision,'sets_data':[{'weight':weight,'reps':8,'rpe':'8','completed':True}]}))
            self.assertEqual(result['exercises'][0]['sets_data'][0]['weight'],weight)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutSet).where(WorkoutSet.user_id==self.uid)),1)
