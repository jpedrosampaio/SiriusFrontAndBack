import os
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.models.health import WorkoutPlan
from db.models.identity import User
from db.session import unit_of_work
import test_postgres_runtime_workout_plans as plan_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeWorkoutGeneration(unittest.IsolatedAsyncioTestCase):
    ok=plan_tests.RuntimeWorkoutPlans.ok
    asyncTearDown=plan_tests.RuntimeWorkoutPlans.asyncTearDown

    async def asyncSetUp(self):
        await plan_tests.RuntimeWorkoutPlans.asyncSetUp(self)
        async def authenticate(authorization=None,**kwargs): return SimpleNamespace(user_id=str(self.bob if authorization=='Bearer bob' else self.uid))
        self.llm=AsyncMock()
        extra=[patch('services.workout_generation_routes.get_current_user',authenticate),patch('services.workout_generation_routes.call_llm',self.llm),
            patch('services.workout_generation_routes.get_user_api_key',AsyncMock(return_value='test-only'))]
        for p in extra:p.start()
        self.patches.extend(extra)

    def period(self,count=20):
        return {'days':[{'exercises':[{'name':f'Exercício {i}','sets':3,'reps':12} for i in range(8)]} for _ in range(count)]}

    async def generate(self,headers=None):
        return await self.http.post('/api/workout-plans/generate',json={'objective':'hipertrofia','level':'iniciante','duration':'mes'},headers=headers or {})

    async def test_four_weeks_retry_and_atomic_reward_replay(self):
        self.llm.side_effect=[json.dumps(self.period(10)),json.dumps(self.period()),json.dumps(self.period())]
        result=self.ok(await self.generate({'Idempotency-Key':'generate-plan-001'}))
        self.assertEqual(len(result['plan']['days']),20); self.assertEqual(len(result['plan']['exercises']),160)
        self.assertEqual(result['plan']['days'][5]['week'],2)
        self.ok(await self.http.patch('/api/workout-plans/'+result['plan']['plan_id'],json=result['plan']))
        self.assertEqual(self.llm.call_args.kwargs['user_id'],str(self.uid))
        replay=self.ok(await self.generate({'Idempotency-Key':'generate-plan-001'}))
        self.assertEqual(result['plan']['plan_id'],replay['plan']['plan_id'])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,5)

    async def test_repeated_partial_and_write_failure_leave_no_plan(self):
        self.llm.side_effect=[json.dumps(self.period(10))]*2
        self.assertEqual((await self.generate()).status_code,502)
        self.llm.side_effect=None; self.llm.return_value=json.dumps(self.period())
        with patch('services.workout_plan_writes.apply_xp',side_effect=RuntimeError('rollback')):
            self.assertEqual((await self.generate()).status_code,500)
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans')),[])
        async with unit_of_work() as session:self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_file_import_and_temporary_cleanup(self):
        paths=[]
        async def upload(path,uid):
            paths.append(path); self.assertTrue(Path(path).exists()); return SimpleNamespace(uri='test://file')
        data={'name':'Importado','exercises':[{'name':'Supino','sets':3,'reps':'12'}]}
        with patch('services.study_material_routes._upload',upload),patch('services.study_material_routes._part',return_value={}),\
             patch('services.workout_generation_routes.request_gemini',AsyncMock(return_value=SimpleNamespace(text=json.dumps(data)))):
            result=self.ok(await self.http.post('/api/workouts/import-plan',files={'file':('treino.pdf',b'%PDF fake','application/pdf')}))
        self.assertTrue(all(not Path(p).exists() for p in paths))
        self.assertEqual(result['plan']['source_filename'],'treino.pdf'); self.assertEqual(result['xp_earned'],10)
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans'))[0]['plan_id'],result['plan']['plan_id'])

    async def test_health_condition_saved_with_plan_and_rolled_back_on_failure(self):
        from services.auth import AuthService
        self.llm.return_value=json.dumps(self.period())
        body={'objective':'hipertrofia','level':'iniciante','duration':'mes','health_condition':'Adaptar por lesão anterior'}
        result=self.ok(await self.http.post('/api/workout-plans/generate',json=body))
        self.assertEqual(result['plan']['health_condition'],body['health_condition'])
        self.assertEqual((await AuthService().profile(self.uid))['health_condition'],body['health_condition'])
        with patch('services.workout_plan_writes.apply_xp',side_effect=RuntimeError('rollback')):
            response=await self.http.post('/api/workout-plans/generate',json={**body,'health_condition':'Outra condição'})
            self.assertEqual(response.status_code,500)
        self.assertEqual((await AuthService().profile(self.uid))['health_condition'],body['health_condition'])

    async def test_improve_owned_plan_preserves_four_weeks_and_parent(self):
        self.llm.return_value=json.dumps(self.period())
        original=self.ok(await self.generate())['plan']; pid=original['plan_id']
        self.llm.reset_mock()
        url='/api/workout-plans/'+pid+'/improve'
        self.assertEqual((await self.http.post(url,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.llm.assert_not_awaited()
        self.llm.side_effect=[json.dumps(self.period(10)),json.dumps({**self.period(),'improvements_summary':'Progressão controlada'})]
        result=self.ok(await self.http.post(url))
        self.assertEqual(len(result['plan']['days']),20); self.assertEqual(result['plan']['cycle_weeks'],4)
        self.assertEqual(result['plan']['improved_from'],pid); self.assertEqual(result['improvements_summary'],'Progressão controlada')
        self.assertEqual(self.llm.await_count,2); self.assertEqual(self.llm.call_args.kwargs['user_id'],str(self.uid))
        plans=self.ok(await self.http.get('/api/workout-plans')); self.assertEqual(len(plans),2)
        self.assertEqual(next(p for p in plans if p['plan_id']==pid)['days'],original['days'])
