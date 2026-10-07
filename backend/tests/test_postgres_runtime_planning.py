"""SQL ports of task/habit activity and reliability regressions, using server.app."""
import asyncio
import os
import sys
import unittest
from datetime import date, datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from fastapi import HTTPException
from sqlalchemy import select, func, event
from sqlalchemy.exc import IntegrityError
from db.engine import dispose_engine, get_engine
from db.session import unit_of_work
from db.models.identity import User, ActivityReceipt
from db.models.planning import Task, TaskInstance, HabitCheck, CalendarEvent
from db.models.health import WorkoutLog, Meal, MealItem
from db.models.studies import StudySession
from db.repositories.identity import IdentityRepository
from db.repositories.planning import PlanningRepository
from db.activity import run_activity
from services.planning import apply_xp

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class RuntimePlanning(unittest.IsolatedAsyncioTestCase):
    async def test_calendar_date_contract(self):
        good=await self.http.get('/api/calendar/events',params={'start':'2024-02-29','end':'2024-02-29'})
        self.assertEqual(good.status_code,200,good.text)
        for value in ('2026-02-29','2026-9-14','2026-09-14T00:00:00','123'):
            result=await self.http.get('/api/calendar/events',params={'start':value,'end':'2026-09-14'})
            self.assertEqual(result.status_code,422,result.text)

    async def asyncSetUp(self):
        import server
        self.http = AsyncClient(transport=ASGITransport(server.app), base_url='https://sirius.test')
        async with unit_of_work() as session:
            repo = IdentityRepository(session)
            alice = await repo.create(email=f'{uuid4()}@example.test', name='Alice', password_hash='test-only')
            bob = await repo.create(email=f'{uuid4()}@example.test', name='Bob', password_hash='test-only')
            self.uid, self.bob = alice.id, bob.id
            planning = PlanningRepository(session)
            self.task_id = (await planning.create_task(self.uid, title='Study', date=date(2026,9,1), recurrence='daily')).id
            self.habit_id = (await planning.create_habit(self.uid, name='Daily')).id
        # Authentication has its own real-server tests. Use deterministic identities
        # here so 20 concurrent mutations do not need 20 session lookups.
        async def account(request):
            uid = self.bob if request.headers.get('Authorization') == 'Bearer bob' else self.uid
            return {'user_id':str(uid), 'timezone':'America/Sao_Paulo'}
        self.auth_patch = patch('services.planning_routes.account', account)
        self.auth_patch.start()

    async def asyncTearDown(self):
        self.auth_patch.stop()
        await self.http.aclose()
        await dispose_engine()

    async def task(self, completed=True, key=None, day='2026-09-14', headers=None):
        headers = dict(headers or {})
        if key: headers['Idempotency-Key'] = key
        return await self.http.patch(f'/api/tasks/{self.task_id}', params={'completed':completed,'date':day}, headers=headers)

    async def habit(self, completed=True, key=None, day='2026-09-14', headers=None):
        headers = dict(headers or {})
        if key: headers['Idempotency-Key'] = key
        params = {'date':day}
        if completed is not None: params['completed'] = completed
        return await self.http.post(f'/api/habits/{self.habit_id}/complete', params=params, headers=headers)

    async def count(self, model):
        async with unit_of_work() as session:
            return await session.scalar(select(func.count()).select_from(model).where(model.user_id == self.uid))

    async def balance(self, expected):
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User, self.uid)).xp, expected)

    def successes(self, results):
        for result in results: self.assertEqual(result.status_code, 200, result.text)

    async def listing(self, day='2026-09-14', **params):
        response = await self.http.get('/api/tasks', params={'date':day, **params})
        self.successes([response])
        return response.json()

    async def test_repeated_task_and_habit_completion_and_undo_each_apply_once(self):
        for operation, reward in ((self.task,10),(self.habit,8)):
            results = await asyncio.gather(*(operation() for _ in range(20)))
            self.successes(results)
            self.assertEqual(sum(r.json()['xp_earned'] for r in results), reward)
            await self.balance(reward)
            results = await asyncio.gather(*(operation(False) for _ in range(20)))
            self.successes(results)
            self.assertEqual(sum(r.json()['xp_earned'] for r in results), -reward)
            await self.balance(0)
        self.assertEqual(await self.count(TaskInstance),1)
        self.assertEqual(await self.count(HabitCheck),0)

    async def test_checkbox_kanban_reload_and_day_isolation(self):
        path = f'/api/tasks/{self.task_id}/status'
        self.successes(await asyncio.gather(self.task(),self.http.patch(path,json={'status':'done','date':'2026-09-14'})))
        await self.balance(10)
        self.successes([await self.http.patch(path,json={'status':'in_progress','date':'2026-09-14'})])
        await self.balance(0)
        self.assertEqual((await self.listing())[0]['status'],'in_progress')
        self.assertFalse((await self.listing())[0]['completed'])
        self.assertEqual((await self.listing('2026-09-15'))[0]['status'],'todo')
        for completed,status in ((True,'done'),(False,'todo')):
            self.successes([await self.task(completed)])
            self.assertEqual((await self.listing())[0]['status'],status)

    async def test_opposite_states_leave_matching_xp(self):
        self.successes(await asyncio.gather(*(self.task(value) for value in [True,False]*10)))
        await self.balance(10 if (await self.listing())[0]['completed'] else 0)

    async def test_distinct_habit_dates_and_independent_task_rewards(self):
        dates = [f'2026-09-{day:02}' for day in range(1,11)]
        self.successes(await asyncio.gather(*(self.habit(day=day) for day in dates)))
        rows = (await self.http.get('/api/habits')).json()
        self.assertEqual(rows[0]['completions'],dates)
        self.assertEqual(rows[0]['best_streak'],10)
        self.successes(await asyncio.gather(self.task(),self.task(day='2026-09-15')))
        await self.balance(100)
        self.assertEqual(await self.count(TaskInstance),2)

    async def test_other_xp_writers_coexist(self):
        async def award(session,user):
            apply_xp(user,2)
            return {'xp':user.xp}
        results = await asyncio.gather(self.task(),self.habit(),
            *(run_activity(self.uid,None,['award',2],award) for _ in range(10)))
        self.successes(results[:2])
        await self.balance(38)

    async def test_same_key_replays_after_lost_response_and_after_undo(self):
        results = await asyncio.gather(*(self.task(key='original-request') for _ in range(12)))
        self.successes(results)
        self.assertEqual(sum(not r.json().get('replayed',False) for r in results),1)
        self.assertEqual(await self.count(ActivityReceipt),1)
        await self.balance(10)
        self.successes([await self.task(False,key='undo-request-001')])
        self.assertTrue((await self.task(key='original-request')).json()['replayed'])
        await self.balance(0)
        self.assertFalse((await self.listing())[0]['completed'])

    async def test_key_conflict_and_user_isolation(self):
        self.successes([await self.task(key='original-request')])
        for result in (await self.task(False,key='original-request'),await self.habit(key='original-request')):
            self.assertEqual(result.status_code,409)
        for result in (await self.task(headers={'Authorization':'Bearer bob'}),await self.habit(headers={'Authorization':'Bearer bob'})):
            self.assertEqual(result.status_code,404)
        self.assertEqual((await self.http.get('/api/tasks',headers={'Authorization':'Bearer bob'})).json(),[])
        async with unit_of_work() as session:
            bob_task = await PlanningRepository(session).create_task(self.bob,title='Own',date=date(2026,9,14))
            bob_id = bob_task.id
        result = await self.http.patch(f'/api/tasks/{bob_id}',params={'completed':True,'date':'2026-09-14'},
            headers={'Authorization':'Bearer bob','Idempotency-Key':'original-request'})
        self.successes([result])
        await self.balance(10)

    async def test_task_and_habit_failure_roll_back_state_xp_receipt(self):
        def fail_after_award(user,delta):
            apply_xp(user,delta)
            raise HTTPException(503,'Injected failure')
        for operation,model in ((self.task,TaskInstance),(self.habit,HabitCheck)):
            with patch('services.planning.apply_xp',fail_after_award):
                self.assertEqual((await operation(key='rollback-request')).status_code,503)
            await self.balance(0)
            self.assertEqual(await self.count(model),0)
            self.assertEqual(await self.count(ActivityReceipt),0)
        self.successes([await self.task(key='rollback-request')])
        await self.balance(10)

    async def test_toggle_requires_key_and_replay_is_safe(self):
        self.assertEqual((await self.habit(None)).status_code,428)
        self.successes([await self.habit(None,key='legacy-toggle-001')])
        self.assertTrue((await self.habit(None,key='legacy-toggle-001')).json()['replayed'])
        await self.balance(8)

    async def test_invalid_inputs_do_not_write(self):
        for result in (await self.task(day='2026-02-30'),await self.habit(day='not-a-date'),
            await self.task(key='short'),await self.http.patch(f'/api/tasks/{self.task_id}/status',json=[])):
            self.assertIn(result.status_code,(400,422))
        self.assertEqual(await self.count(TaskInstance),0)
        await self.balance(0)

    async def test_instances_loaded_in_one_query_and_recurrence_filter(self):
        async with unit_of_work() as session:
            session.add_all([Task(user_id=self.uid,title=f'Task {i}',date=date(2026,9,1),recurrence='daily') for i in range(99)])
        statements = []
        def capture(conn,cursor,statement,parameters,context,executemany):
            statements.append(statement)
        engine = get_engine().sync_engine
        event.listen(engine,'before_cursor_execute',capture)
        try:
            self.assertEqual(len(await self.listing()),100)
        finally:
            event.remove(engine,'before_cursor_execute',capture)
        self.assertEqual(len(statements),1)
        self.assertEqual(await self.listing(recurrence='weekly'),[])

    async def test_create_archive_preserves_evidence_and_hides_deleted_templates(self):
        task = await self.http.post('/api/tasks',json={'title':'Create','date':'2026-09-14'})
        habit = await self.http.post('/api/habits',json={'name':'Create'})
        self.successes([task,habit,await self.task(),await self.habit()])
        foreign = await self.http.delete(f'/api/tasks/{self.task_id}',headers={'Authorization':'Bearer bob'})
        self.assertEqual(foreign.status_code,404)
        self.successes([await self.http.delete(f'/api/tasks/{self.task_id}'),await self.http.delete(f'/api/habits/{self.habit_id}')])
        self.assertEqual(len(await self.listing()),1)
        self.assertEqual(len((await self.http.get('/api/habits')).json()),1)
        self.assertEqual(await self.count(TaskInstance),1)
        self.assertEqual(await self.count(HabitCheck),1)
        self.assertEqual((await self.task()).status_code,404)
        self.assertEqual((await self.habit()).status_code,404)

    async def test_database_rejects_duplicate_and_foreign_instances(self):
        self.successes([await self.task()])
        for owner in (self.uid,self.bob):
            with self.assertRaises(IntegrityError):
                async with unit_of_work() as session:
                    session.add(TaskInstance(user_id=owner,task_id=self.task_id,date=date(2026,9,14)))

    async def test_calendar_period_ownership_empty_state_and_timezone(self):
        self.successes([await self.task(),await self.habit()])
        async with unit_of_work() as session:
            for owner,day in ((self.uid,date(2026,9,14)),(self.bob,date(2026,9,14)),(self.uid,date(2026,8,14))):
                meal = Meal(user_id=owner,name='Lunch',meal_type='almoço',date=day)
                session.add(meal)
                await session.flush()
                session.add_all([
                    MealItem(user_id=owner,meal_id=meal.id,position=0,name='Food',quantity=1,unit='portion',
                        calories=300,protein=10,carbs=50,fat=5),
                    StudySession(user_id=owner,date=day,duration_minutes=25,completed=True),
                    WorkoutLog(user_id=owner,date=day,name='Walk',activity_type='walk',duration_minutes=30),
                ])
            session.add(CalendarEvent(user_id=self.uid,title='Evening',
                start_at=datetime(2026,9,15,1,tzinfo=timezone.utc),end_at=datetime(2026,9,15,2,tzinfo=timezone.utc)))
        response = await self.http.get('/api/calendar/events',params={'start':'2026-09-14','end':'2026-09-14'})
        self.successes([response])
        events = response.json()['events']
        self.assertEqual(len(events),6)
        self.assertEqual({row['type'] for row in events},{'task','habit','study','workout','meal','commitment'})
        self.assertTrue(all(row['date']=='2026-09-14' for row in events))
        self.assertEqual(next(row for row in events if row['type']=='meal')['calories'],300)
        self.assertEqual(next(row for row in events if row['type']=='commitment')['title'],'22:00 · Evening')
        empty = await self.http.get('/api/calendar/events',params={'start':'2025-01-01','end':'2025-01-02'})
        self.assertEqual(empty.json()['events'],[])
        for start,end in (('2026-09-15','2026-09-14'),('2025-01-01','2026-09-14')):
            self.assertEqual((await self.http.get('/api/calendar/events',params={'start':start,'end':end})).status_code,422)
