import os
import asyncio
import unittest
from datetime import timedelta
from unittest.mock import patch
from sqlalchemy import select,func
from db.models.health import WorkoutLog,WorkoutLogExercise,WorkoutSet
from db.models.identity import User
from db.session import unit_of_work
from services.time import local_today
import test_postgres_runtime_workout_plans as plan_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeWorkoutLogs(unittest.IsolatedAsyncioTestCase):
    ok=plan_tests.RuntimeWorkoutPlans.ok
    asyncTearDown=plan_tests.RuntimeWorkoutPlans.asyncTearDown

    async def asyncSetUp(self):
        await plan_tests.RuntimeWorkoutPlans.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        p=patch('services.workout_logs.account',account); p.start(); self.patches.append(p)

    def payload(self):
        return {'activity_type':'weightlifting','name':'Treino','date':local_today('America/Sao_Paulo').isoformat(),'duration_minutes':30,
            'exercises_completed':[{'name':'Supino','sets':3,'reps':12,'completed':True,
                'sets_data':[{'reps':12,'weight':'10.125','rpe':8,'completed':True}]}]}

    async def test_manual_log_replay_toggle_delete_and_owner(self):
        responses=await asyncio.gather(*(self.http.post('/api/workouts',json=self.payload(),headers={'Idempotency-Key':'manual-workout-001'}) for _ in range(6)))
        values=[self.ok(r) for r in responses]; self.assertEqual(len({v['log_id'] for v in values}),1)
        row=self.ok(await self.http.get('/api/workouts'))[0]; self.assertEqual(row['exercises_completed'][0]['sets_data'][0]['weight'],'10.125')
        path='/api/workouts/'+row['log_id']
        self.assertEqual((await self.http.patch(path+'/toggle',headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual(self.ok(await self.http.get('/api/workouts',headers={'Authorization':'Bearer bob'})),[])
        self.assertFalse(self.ok(await self.http.patch(path+'/toggle'))['completed'])
        self.assertEqual(self.ok(await self.http.get('/api/workout-stats'))['total_workouts'],0)
        self.ok(await self.http.delete(path))
        async with unit_of_work() as session:
            for model in (WorkoutLog,WorkoutLogExercise,WorkoutSet):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_session_log_uses_snapshot_without_duplicate_exercises(self):
        plan=self.ok(await self.http.post('/api/workout-plans',json={'name':'Sessão','exercises':[{'name':'Supino'}]}))
        started=self.ok(await self.http.post('/api/workout-sessions/start',json={'plan_id':plan['plan_id']})); sid=started['session_id']
        self.ok(await self.http.patch('/api/workout-sessions/'+sid+'/exercise/0',json={'completed':True,'sets_data':[{'reps':8,'weight':20,'completed':True}]}))
        self.ok(await self.http.post('/api/workout-sessions/'+sid+'/complete',json={}))
        row=self.ok(await self.http.get('/api/workouts'))[0]
        self.assertEqual(row['session_id'],sid); self.assertEqual(row['exercises_completed'][0]['sets_data'][0]['reps'],8)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutLogExercise).where(WorkoutLogExercise.user_id==self.uid)),0)

    async def test_period_stats_empty_state_and_failed_write_rollback(self):
        self.assertEqual(self.ok(await self.http.get('/api/workout-stats'))['total_workouts'],0)
        with patch('services.workout_logs.apply_xp',side_effect=RuntimeError('after sets')):
            with self.assertRaises(RuntimeError):await self.http.post('/api/workouts',json=self.payload())
        self.assertEqual(self.ok(await self.http.get('/api/workouts')),[])
        today=local_today('America/Sao_Paulo')
        for delta in (0,1,40):self.ok(await self.http.post('/api/workouts',json={**self.payload(),'date':(today-timedelta(days=delta)).isoformat()}))
        stats=self.ok(await self.http.get('/api/workout-stats'))
        self.assertEqual(stats['total_workouts'],2); self.assertEqual(stats['total_duration_minutes'],60)
        detail=self.ok(await self.http.get('/api/workout-stats/detailed'))
        self.assertEqual(len(detail['daily_data']),30); self.assertEqual(detail['current_streak'],2); self.assertEqual(detail['trained_days'],2)
