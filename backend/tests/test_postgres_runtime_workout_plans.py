import os
import unittest
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func
from db.models.health import WorkoutPlan,WorkoutDay,PlanExercise
from db.session import unit_of_work
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeWorkoutPlans(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        async def account(request): return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.patches=[patch(module+'.account',account) for module in ('services.workout_plan_routes','services.workout_session_routes')]
        for p in self.patches: p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches): p.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    def payload(self):
        return {'name':'Quatro semanas','plan_duration':'mes','days':[{'week':week,'day_label':f'Semana {week}, dia {day}',
            'split_label':'A','progression_notes':'Progressão','exercises':[{'name':'Supino','sets':3,'reps':12,'rest_seconds':0}]}
            for week in range(1,5) for day in range(1,6)]}

    async def test_calendar_normalized_and_edit_preserves_session_snapshot(self):
        body=self.payload(); plan=self.ok(await self.http.post('/api/workout-plans',json=body)); pid=plan['plan_id']
        self.assertEqual(len(plan['days']),20); self.assertEqual(plan['days'][5]['week'],2)
        self.assertEqual(plan['days'][5]['split_label'],'A'); self.assertEqual(plan['days'][0]['exercises'][0]['rest_seconds'],0)
        start=self.ok(await self.http.post('/api/workout-sessions/start',json={'plan_id':pid,'day_index':5}))
        body['days'][5]['exercises'][0]['name']='Novo exercício'
        self.ok(await self.http.patch('/api/workout-plans/'+pid,json=body))
        updated=self.ok(await self.http.get('/api/workout-plans'))[0]
        self.assertEqual(updated['days'][5]['exercises'][0]['name'],'Novo exercício')
        active=self.ok(await self.http.get('/api/workout-sessions/active'))['session']
        self.assertEqual(active['exercises'][0]['name'],'Supino')
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutDay).where(WorkoutDay.user_id==self.uid)),20)
            self.assertEqual(await session.scalar(select(func.count()).select_from(PlanExercise).where(PlanExercise.user_id==self.uid)),20)
        self.ok(await self.http.delete('/api/workout-plans/'+pid))
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans')),[])
        self.ok(await self.http.post('/api/workout-sessions/'+start['session_id']+'/complete',json={}))
        self.assertEqual((await self.http.post('/api/workout-sessions/start',json={'plan_id':pid})).status_code,404)

    async def test_plan_owner_and_empty_schedule(self):
        self.assertFalse(self.ok(await self.http.get('/api/workouts/today-schedule'))['scheduled'])
        body=self.payload(); plan=self.ok(await self.http.post('/api/workout-plans',json=body)); pid=plan['plan_id']; foreign={'Authorization':'Bearer bob'}
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans',headers=foreign)),[])
        self.assertEqual((await self.http.patch('/api/workout-plans/'+pid,json=body,headers=foreign)).status_code,404)
        self.assertEqual((await self.http.delete('/api/workout-plans/'+pid,headers=foreign)).status_code,404)
        schedule=self.ok(await self.http.get('/api/workouts/today-schedule'))
        self.assertEqual(schedule['day_index'],0); self.assertFalse(schedule['already_completed'])

    async def test_update_failure_rolls_back_day_replacement(self):
        body=self.payload(); plan=self.ok(await self.http.post('/api/workout-plans',json=body)); pid=plan['plan_id']
        from db.repositories.health import HealthRepository
        original=HealthRepository.replace_days
        async def fail(repo,*args,**kwargs):
            await original(repo,*args,**kwargs); raise RuntimeError('after replacement')
        body['name']='Must roll back'
        with patch.object(HealthRepository,'replace_days',fail):
            with self.assertRaises(RuntimeError): await self.http.patch('/api/workout-plans/'+pid,json=body)
        saved=self.ok(await self.http.get('/api/workout-plans'))[0]
        self.assertEqual(saved['name'],plan['name']); self.assertEqual(len(saved['days']),20)
