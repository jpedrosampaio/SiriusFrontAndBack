import os
import unittest
from datetime import timedelta
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select, func, event, update
from db.models.health import WorkoutLog, WorkoutSet, WorkoutSession, WorkoutPlan, WorkoutDay, SessionExercise
from services.workout_origin import snapshot
from db.models.identity import User, ActivityReceipt
from db.engine import get_engine
from db.session import unit_of_work
from services.training_intelligence import TrainingEngine, life_facts
from services.time import local_today
from ai.core import Core
import test_postgres_runtime_workout_logs as fixtures


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class TrainingIntelligence(unittest.IsolatedAsyncioTestCase):
    ok = fixtures.RuntimeWorkoutLogs.ok
    asyncTearDown = fixtures.RuntimeWorkoutLogs.asyncTearDown

    async def asyncSetUp(self):
        await fixtures.RuntimeWorkoutLogs.asyncSetUp(self)
        async def account(request):
            return {'user_id': str(self.bob if request.headers.get('Authorization') == 'Bearer bob' else self.uid), 'timezone': 'America/Sao_Paulo'}
        for target in ('services.training_intelligence_routes.account', 'services.workout_history_routes.account'):
            mocked = patch(target, account); mocked.start(); self.patches.append(mocked)
        self.day = local_today('America/Sao_Paulo')
        self.plan = self.ok(await self.http.post('/api/workout-plans', json={'name': 'Factual', 'objective': 'hipertrofia', 'days': [
            {'day_label': 'A', 'exercises': [{'name': 'Supino', 'muscle_group': 'Peito', 'sets': 3, 'reps': '8-12', 'weight': '20'},
             {'name': 'Supino reto com halteres', 'muscle_group': 'Peito', 'sets': 3, 'reps': '8-12'},
             {'name': 'Desenvolvimento', 'muscle_group': 'Peito', 'sets': 3},
             {'name': 'Exercício desconhecido', 'muscle_group': 'Peito', 'sets': 3}]}]}))
        self.pid = self.plan['plan_id']
        # Manual PlanBody intentionally has no objective; emulate persisted generated metadata.
        async with unit_of_work() as session:
            (await session.get(WorkoutPlan, UUID(self.pid))).objective = 'hipertrofia'

    async def add(self, delta=0, *, weight='20', rpe=8, owner=None, request_key=None):
        body = {'plan_id': self.pid if owner is None else None, 'name': 'Actual', 'activity_type': 'weightlifting', 'duration_minutes': 30,
            'date': str(self.day - timedelta(days=delta)), 'exercises_completed': [{'name': 'Supino', 'muscle_group': 'Peito', 'sets': 3,
            'reps': '8-12', 'sets_data': [{'weight': weight, 'reps': 12, 'rpe': rpe, 'completed': True} for _ in range(3)]}]}
        headers = {'Authorization': 'Bearer bob'} if owner else {}
        if request_key: headers['Idempotency-Key'] = request_key
        return self.ok(await self.http.post('/api/workouts', json=body, headers=headers))

    async def state(self, **kwargs):
        return self.ok(await self.http.get('/api/workouts/intelligence/state', **kwargs))

    async def session_log(self, delta=0, day_index=0):
        from datetime import datetime, timezone
        async with unit_of_work() as session:
            origin = await session.scalar(select(WorkoutDay).where(WorkoutDay.plan_id == UUID(self.pid), WorkoutDay.position == day_index))
            row = WorkoutSession(user_id=self.uid, plan_id=UUID(self.pid), plan_name='Factual', day_index=day_index,
                feedback=snapshot(self.pid, origin.id, day_index),
                status='completed', started_at=datetime.now(timezone.utc)-timedelta(days=delta, minutes=30),
                completed_at=datetime.now(timezone.utc)-timedelta(days=delta), total_duration_seconds=1800)
            session.add(row); await session.flush()
            ex = SessionExercise(user_id=self.uid, session_id=row.id, position=0, name='Supino', muscle_group='Peito',
                sets=3, reps='8-12', weight='20', completed=True, sets_completed=3)
            session.add(ex); await session.flush()
            session.add_all([WorkoutSet(user_id=self.uid, exercise_id=ex.id, position=i, weight=20, reps=12, rpe=8, completed=True) for i in range(3)])
            session.add(WorkoutLog(user_id=self.uid, session_id=row.id, plan_id=UUID(self.pid), activity_type='weightlifting',
                name='Factual', date=self.day-timedelta(days=delta), duration_minutes=30, completed=True))

    async def counts(self):
        async with unit_of_work() as session:
            values = [await session.scalar(select(func.count()).select_from(model).where(model.user_id == self.uid)) for model in (WorkoutLog, WorkoutSet, WorkoutSession, ActivityReceipt)]
            owner = await session.get(User, self.uid)
            plan = await session.get(WorkoutPlan, UUID(self.pid))
            return values + [owner.xp, plan.updated_at]

    async def test_owned_readonly_state_replay_toggle_delete_and_agent(self):
        first = await self.add(5, request_key='training-first'); await self.add(5, request_key='training-first'); latest = await self.add()
        await self.add(owner=self.bob, weight='999')
        before = await self.counts(); state = await self.state()
        self.assertEqual(state['completed_workouts'], 2); self.assertEqual(state['set_adherence'], 100)
        self.assertIsNone(state['exercises'][0]['progression']['suggested_weight'])
        self.assertIsNone(state['exercises'][0]['progression']['day_index'])
        self.assertEqual(state['exercises'][0]['volume'], '1440.000')
        self.assertEqual((await self.state(headers={'Authorization': 'Bearer bob'}))['exercises'][0]['records'][0]['value'], '999.000')
        for _ in range(2):
            facts = await Core().read('get_training_state', str(self.uid)); self.assertEqual(facts['completed_workouts'], 2)
        self.assertEqual(before, await self.counts())
        self.ok(await self.http.patch('/api/workouts/' + latest['log_id'] + '/toggle'))
        self.assertEqual((await self.state())['completed_workouts'], 1)
        self.ok(await self.http.delete('/api/workouts/' + first['log_id']))
        self.assertEqual((await self.state())['exercises'], [])

    async def test_session_snapshot_once_active_abandoned_and_deleted_logs(self):
        started = self.ok(await self.http.post('/api/workout-sessions/start', json={'plan_id': self.pid}))
        path = '/api/workout-sessions/' + started['session_id']
        self.ok(await self.http.patch(path + '/exercise/0', json={'revision': 0, 'sets_data': [{'weight': '25', 'reps': 8, 'rpe': 7, 'completed': True}]}))
        self.assertEqual((await self.state())['completed_workouts'], 0)
        self.ok(await self.http.post(path + '/complete', json={}))
        state = await self.state(); self.assertEqual(state['completed_workouts'], 1)
        self.assertEqual(next(e for e in state['exercises'] if e['name'] == 'Supino')['recorded_sets'], 1)
        partial = next(e for e in state['exercises'] if e['name'] == 'Supino')
        self.assertIsNone(partial['volume']); self.assertEqual(partial['known_volume'], '200.000')
        self.assertFalse(any(r['kind'] == 'max_volume' for r in partial['records']))
        row = self.ok(await self.http.get('/api/workouts'))[0]
        self.ok(await self.http.delete('/api/workouts/' + row['log_id']))
        self.assertEqual((await self.state())['completed_workouts'], 0)
        started = self.ok(await self.http.post('/api/workout-sessions/start', json={'plan_id': self.pid}))
        self.ok(await self.http.post('/api/workout-sessions/' + started['session_id'] + '/abandon'))
        self.assertEqual((await self.state())['exercises'], [])

    async def test_substitution_ownership_movement_and_unknown_without_writes(self):
        body = {'plan_id': self.pid, 'day_index': 0, 'exercise_index': 0}; before = await self.counts()
        result = self.ok(await self.http.post('/api/workouts/intelligence/substitutions', json=body))
        self.assertEqual([s['name'] for s in result['suggestions']], ['Supino reto com halteres'])
        self.assertTrue(result['suggestions'][0]['movement_confirmed']); self.assertFalse(result['automatic'])
        result = await Core().read('get_exercise_substitutions', str(self.uid), body | {'exercise_index': 3})
        self.assertTrue(result['suggestions']); self.assertFalse(any(s['movement_confirmed'] for s in result['suggestions']))
        self.assertEqual((await self.http.post('/api/workouts/intelligence/substitutions', json=body, headers={'Authorization': 'Bearer bob'})).status_code, 404)
        for invalid in ({'day_index': 900}, {'exercise_index': 900}, {'day_index': True}, {'user_id': str(self.bob)}):
            self.assertEqual((await self.http.post('/api/workouts/intelligence/substitutions', json=body | invalid)).status_code, 422)
        self.assertEqual(before, await self.counts())

    async def test_window_timezone_query_bound_life_integration_and_next_load_contract(self):
        await self.add(100); await self.add(5); await self.add(); await self.add(-1)
        statements = []
        def capture(*args): statements.append(args[2])
        event.listen(get_engine().sync_engine, 'before_cursor_execute', capture)
        try:
            state = await TrainingEngine().get_state(self.uid)
        finally: event.remove(get_engine().sync_engine, 'before_cursor_execute', capture)
        self.assertEqual(state.completed_workouts, 2); self.assertLessEqual(len(statements), 10)
        async with unit_of_work() as session:
            facts = await life_facts(session, self.uid, self.day)
            self.assertEqual(facts['completed_workouts'], 2)
        loads = self.ok(await self.http.get('/api/workouts/next-loads', params={'plan_id': self.pid}))
        self.assertIsNone(loads['suggestions'][0]['next_weight'])
        async with unit_of_work() as session:
            (await session.get(User, self.uid)).timezone = 'Pacific/Kiritimati'
        state = await self.state(); self.assertEqual(state['timezone'], 'Pacific/Kiritimati')
        self.assertEqual(state['as_of'], str(local_today('Pacific/Kiritimati')))
        for days in (0, 366): self.assertEqual((await self.http.get('/api/workouts/intelligence/state', params={'days': days})).status_code, 422)

    async def test_missing_objective_no_equivalence_and_real_auth_guard(self):
        async with unit_of_work() as session: (await session.get(WorkoutPlan, UUID(self.pid))).objective = None
        result = self.ok(await self.http.post('/api/workouts/intelligence/substitutions', json={'plan_id': self.pid, 'day_index': 0, 'exercise_index': 0}))
        self.assertEqual(result['suggestions'], [])
        from services.auth_routes import account
        with patch('services.training_intelligence_routes.account', account):
            self.assertEqual((await self.http.get('/api/workouts/intelligence/state')).status_code, 401)
            self.assertEqual((await self.http.post('/api/workouts/intelligence/substitutions', json={'plan_id': self.pid, 'day_index': 0, 'exercise_index': 0})).status_code, 401)

    async def test_child_budget_discloses_partial_coverage_without_loading_sets(self):
        await self.session_log(5); await self.session_log()
        before = await self.counts()
        with patch('services.training_intelligence.SET_BUDGET', 2):
            state = await self.state()
        self.assertTrue(state['truncated']); self.assertEqual(state['completed_workouts'], 2)
        self.assertEqual(state['analyzed_workouts'], 0); self.assertEqual(state['exercises'], [])
        self.assertIsNone(state['set_adherence']); self.assertEqual(before, await self.counts())

    async def test_prescription_changes_do_not_reuse_old_load_suggestions(self):
        await self.session_log(5); await self.session_log()
        before = self.ok(await self.http.get('/api/workouts/next-loads', params={'plan_id': self.pid}))
        self.assertEqual(before['suggestions'][0]['next_weight'], 20.5)
        updated = dict(self.plan)
        updated['days'][0]['exercises'][0]['reps'] = '20'
        self.ok(await self.http.patch('/api/workout-plans/' + self.pid, json=updated))
        result = self.ok(await self.http.get('/api/workouts/next-loads', params={'plan_id': self.pid}))
        self.assertIsNone(result['suggestions'][0]['next_weight'])

    async def test_read_snapshot_survives_concurrent_set_change(self):
        await self.add(5); await self.add()
        from services.workout_logs import serialize_logs
        async def concurrent_change(session, uid, rows, **kwargs):
            async with unit_of_work() as writer:
                await writer.execute(update(WorkoutSet).where(WorkoutSet.user_id == uid).values(weight=99))
            return await serialize_logs(session, uid, rows, **kwargs)
        with patch('services.workout_logs.serialize_logs', concurrent_change):
            snapshot = await self.state()
        self.assertEqual(snapshot['exercises'][0]['records'][0]['value'], '20.000')
        refreshed = await self.state()
        self.assertEqual(refreshed['exercises'][0]['records'][0]['value'], '99.000')

    async def test_archived_plan_keeps_history_and_different_goals_are_excluded(self):
        await self.add()
        other = self.ok(await self.http.post('/api/workout-plans', json={'name': 'Different goal', 'exercises': [
            {'name': 'Supino reto com barra', 'muscle_group': 'Peito'}]}))
        async with unit_of_work() as session:
            (await session.get(WorkoutPlan, UUID(other['plan_id']))).objective = 'força'
        body = {'plan_id': self.pid, 'day_index': 0, 'exercise_index': 0}
        result = self.ok(await self.http.post('/api/workouts/intelligence/substitutions', json=body))
        self.assertNotIn('Supino reto com barra', [s['name'] for s in result['suggestions']])
        self.ok(await self.http.delete('/api/workout-plans/' + self.pid))
        self.assertEqual((await self.state())['completed_workouts'], 1)
        self.assertEqual((await self.http.post('/api/workouts/intelligence/substitutions', json=body)).status_code, 404)

    async def test_next_loads_require_two_executions_of_the_requested_workout_day(self):
        # Same Supino prescription in two separate days of one plan.
        updated = dict(self.plan)
        updated['days'].append({'day_label': 'B', 'exercises': [dict(updated['days'][0]['exercises'][0])]})
        self.ok(await self.http.patch('/api/workout-plans/' + self.pid, json=updated))
        await self.session_log(7, 0); await self.session_log(3, 1)
        loads = self.ok(await self.http.get('/api/workouts/next-loads', params={'plan_id': self.pid}))
        self.assertTrue(all(s['next_weight'] is None for s in loads['suggestions']))
        await self.session_log(0, 0)
        loads = self.ok(await self.http.get('/api/workouts/next-loads', params={'plan_id': self.pid}))
        self.assertEqual(loads['suggestions'][0]['next_weight'], 20.5)
        self.assertIsNone(loads['suggestions'][-1]['next_weight'])
        # Serializer opt-in does not change the legacy logs API contract.
        logs = self.ok(await self.http.get('/api/workouts'))
        self.assertTrue(all('day_index' not in row for row in logs))

    async def test_replaced_days_never_reuse_old_ordinal_history(self):
        await self.session_log(10); await self.session_log(7)
        before = self.ok(await self.http.get('/api/workouts/next-loads', params={'plan_id': self.pid}))
        self.assertEqual(before['suggestions'][0]['next_weight'], 20.5)
        old_id = before['suggestions'][0]['day_id']
        updated = dict(self.plan)
        updated['days'][0]['day_label'] = 'B'
        self.ok(await self.http.patch('/api/workout-plans/' + self.pid, json=updated))
        after = self.ok(await self.http.get('/api/workouts/next-loads', params={'plan_id': self.pid}))
        self.assertNotEqual(after['suggestions'][0]['day_id'], old_id)
        self.assertIsNone(after['suggestions'][0]['next_weight'])
        self.assertEqual((await self.state())['completed_workouts'], 2)
        await self.session_log(3)
        one = self.ok(await self.http.get('/api/workouts/next-loads', params={'plan_id': self.pid}))
        self.assertIsNone(one['suggestions'][0]['next_weight'])
        await self.session_log()
        two = self.ok(await self.http.get('/api/workouts/next-loads', params={'plan_id': self.pid}))
        self.assertEqual(two['suggestions'][0]['next_weight'], 20.5)
        self.assertEqual((await self.state())['completed_workouts'], 4)

    async def test_session_origin_survives_completion_and_replay_without_public_metadata(self):
        started = self.ok(await self.http.post('/api/workout-sessions/start', json={'plan_id': self.pid, 'day_index': 0}))
        self.assertIsNotNone(started['day_id']); self.assertIsNone(started['feedback'])
        path = '/api/workout-sessions/' + started['session_id']
        first = self.ok(await self.http.post(path + '/complete', json={'difficulty': 3, 'notes': 'real'}))
        replay = self.ok(await self.http.post(path + '/complete', json={'difficulty': 3, 'notes': 'real'}))
        self.assertTrue(replay['replayed'])
        self.assertNotIn('_training_origin_v1', first['feedback'])
        history = self.ok(await self.http.get('/api/workout-sessions'))
        self.assertEqual(history[0]['day_id'], started['day_id'])
        self.assertEqual(history[0]['feedback']['notes'], 'real')
        self.assertNotIn('_training_origin_v1', history[0]['feedback'])
