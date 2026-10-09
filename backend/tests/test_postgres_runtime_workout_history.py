import os
import unittest
from unittest.mock import patch
import test_postgres_runtime_workout_logs as log_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeWorkoutHistory(unittest.IsolatedAsyncioTestCase):
    ok=log_tests.RuntimeWorkoutLogs.ok
    payload=log_tests.RuntimeWorkoutLogs.payload
    asyncTearDown=log_tests.RuntimeWorkoutLogs.asyncTearDown

    async def asyncSetUp(self):
        await log_tests.RuntimeWorkoutLogs.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        p=patch('services.workout_history_routes.account',account);p.start();self.patches.append(p)

    async def test_exact_literal_exercise_history_and_owner(self):
        body=self.payload(); ex=body['exercises_completed'][0]
        body['exercises_completed']=[{**ex,'name':'Supino (barra) inclinado'},{**ex,'name':'Supino (barra)'}]
        self.ok(await self.http.post('/api/workouts',json=body))
        result=self.ok(await self.http.get('/api/workouts/exercise-history',params={'exercise_name':'supino (barra)'}))
        self.assertEqual(len(result['history']),1);self.assertEqual(result['history'][0]['exercise_name'],'Supino (barra)')
        self.assertEqual(self.ok(await self.http.get('/api/workouts/exercise-history',params={'exercise_name':'.*'}))['history'],[])
        self.assertEqual(self.ok(await self.http.get('/api/workouts/exercise-history',params={'exercise_name':'Supino (barra)'},headers={'Authorization':'Bearer bob'}))['history'],[])

    async def test_evolution_does_not_double_count_session_and_log(self):
        plan=self.ok(await self.http.post('/api/workout-plans',json={'name':'Plan','exercises':[{'name':'Supino','sets':1}]}))
        started=self.ok(await self.http.post('/api/workout-sessions/start',json={'plan_id':plan['plan_id']}));url='/api/workout-sessions/'+started['session_id']
        self.ok(await self.http.patch(url+'/exercise/0',json={'sets_data':[{'weight':'25','reps':8,'completed':True}],'completed':True}))
        self.ok(await self.http.post(url+'/complete',json={}))
        result=self.ok(await self.http.get('/api/workout-stats/exercise-evolution'))
        self.assertEqual(len(result['exercises']['Supino']),1);self.assertEqual(result['exercises']['Supino'][0]['source'],'session')
        self.assertEqual(self.ok(await self.http.get('/api/workout-stats/exercise-evolution',params={'exercise_name':'%'}))['exercises'],{})
        loads=self.ok(await self.http.get('/api/workouts/next-loads',params={'plan_id':plan['plan_id']}))
        # One execution without RPE no longer proves that progression is appropriate.
        self.assertIsNone(loads['suggestions'][0]['next_weight'])
        self.assertFalse(loads['suggestions'][0]['progress_possible'])
        self.assertEqual(self.ok(await self.http.get('/api/workouts/next-loads',params={'plan_id':plan['plan_id']},headers={'Authorization':'Bearer bob'}))['suggestions'],[])

    async def test_next_load_handles_empty_or_incomplete_sets(self):
        self.assertEqual(self.ok(await self.http.get('/api/workouts/next-loads'))['suggestions'],[])
        plan=self.ok(await self.http.post('/api/workout-plans',json={'name':'Plan','exercises':[{'name':'Supino','sets':3}]}))
        self.ok(await self.http.post('/api/workouts',json={**self.payload(),'plan_id':plan['plan_id']}))
        result=self.ok(await self.http.get('/api/workouts/next-loads'))['suggestions'][0]
        self.assertFalse(result['progress_possible']);self.assertIsNone(result['next_weight'])
