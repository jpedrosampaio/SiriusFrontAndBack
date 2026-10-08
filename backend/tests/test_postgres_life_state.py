import asyncio
import os
import unittest
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select, func
from db.session import unit_of_work
from db.models.identity import User
from db.models.planning import Task, TaskInstance, CalendarEvent, Habit, Goal
from db.models.studies import StudyPlan, StudyPlanEntry, StudySchedule
from db.models.finance import FinancialTransaction
from db.models.health import WorkoutPlan
from services.life_state import snapshot, preview
from life_contracts import Availability, Scenario
import test_postgres_runtime_catalog as fixtures


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class UnifiedLife(unittest.IsolatedAsyncioTestCase):
    ok=fixtures.RuntimeCatalog.ok
    setup_catalog=fixtures.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await fixtures.RuntimeCatalog.asyncSetUp(self)
        _,program,book=await self.setup_catalog();self.pid=UUID(program['program_id']);self.nid=UUID(book['notebook_id'])
        self.day=datetime.now(timezone.utc).date()+timedelta(days=1)
        async def account(request):
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.auth_life=patch('services.life_routes.account',account);self.auth_life.start()
        self.availability={'weekdays':[[{'start_minute':600,'end_minute':780},{'start_minute':1080,'end_minute':1260}] for _ in range(7)],
            'duration_estimates':{'habits':5}}
        self.ok(await self.http.put('/api/life/availability',json=self.availability,headers={'Idempotency-Key':'availability-first'}))
        async with unit_of_work() as s:
            plan=StudyPlan(user_id=self.uid,program_id=self.pid,start_date=self.day,end_date=self.day,
                availability=[60]*7,block_minutes=30);s.add(plan);await s.flush()
            self.entry=StudyPlanEntry(user_id=self.uid,plan_id=plan.id,notebook_id=self.nid,date=self.day,
                name='Canonical review',minutes=45,kind='review',manual=False,fixed=True)
            s.add(self.entry);s.add(Task(user_id=self.uid,title='Priority task',date=self.day,priority='high',duration_minutes=30))
            s.add(CalendarEvent(user_id=self.uid,title='Work',start_at=datetime.combine(self.day,time(11),timezone.utc),
                end_at=datetime.combine(self.day,time(15),timezone.utc)))
            s.add(FinancialTransaction(user_id=self.uid,type='expense',amount=Decimal('10.01'),category='x',date=self.day))
            s.add(FinancialTransaction(user_id=self.bob,type='expense',amount=Decimal('999.99'),category='x',date=self.day))
            s.add(Habit(user_id=self.uid,name='Habit'));s.add(Goal(user_id=self.uid,title='Goal',target_date=self.day,progress=25))
            self.workout=WorkoutPlan(user_id=self.uid,name='Selected workout',generated_by_ai=False,generation_parameters={})
            s.add(self.workout);await s.flush()
        self.availability.update(training_plan_id=str(self.workout.id),training_weekdays=[self.day.weekday()],
            duration_estimates={'habits':5,'training':45})
        self.ok(await self.http.put('/api/life/availability',json=self.availability,headers={'Idempotency-Key':'availability-workout'}))

    async def asyncTearDown(self):
        self.auth_life.stop();await fixtures.RuntimeCatalog.asyncTearDown(self)

    async def simulate(self,**values):
        return self.ok(await self.http.post('/api/life/simulate',json={'date':str(self.day),**values}))

    async def test_owned_state_decimal_canonical_projection_and_same_core_engine(self):
        result=await self.simulate();state=result['state'];domains={d['domain']:d for d in state['domains']}
        self.assertEqual(len(domains),8);self.assertEqual(domains['finance']['facts']['expense'],'10.01')
        self.assertEqual(domains['preparation']['candidates'][0]['source_id'],str(self.entry.id))
        blocks=result['plan']['blocks'];self.assertTrue(any(b['domain']=='preparation' for b in blocks))
        self.assertTrue(any(b['domain']=='tasks' for b in blocks))
        self.assertTrue(any(b['domain']=='training' for b in blocks))
        for a,b in zip(blocks,blocks[1:]):self.assertLessEqual(a['end_minute'],b['start_minute'])
        other=self.ok(await self.http.get('/api/life/state',params={'date':str(self.day)},headers={'Authorization':'Bearer bob'}))
        self.assertNotIn('Canonical review',str(other));self.assertNotEqual(other['fingerprint'],state['fingerprint'])

    async def test_simulations_have_no_writes_and_confirm_replays_once(self):
        before=await self.counts();result=await self.simulate();self.assertEqual(before,await self.counts())
        body={'scenario':result['plan']['scenario'],'fingerprint':result['state']['fingerprint'],
            'blocks':result['plan']['blocks'],'confirmed':True}
        headers={'Idempotency-Key':'global-confirm-first'}
        responses=await asyncio.gather(*(self.http.post('/api/life/accept',json=body,headers=headers) for _ in range(4)))
        for r in responses:self.ok(r)
        event_ids=responses[0].json()['event_ids'];self.assertTrue(event_ids)
        self.assertTrue(all(r.json()['event_ids']==event_ids for r in responses))
        result2=await self.simulate();self.assertFalse(result2['plan']['blocks'])
        async with unit_of_work() as s:
            self.assertFalse((await s.get(StudyPlanEntry,self.entry.id)).completed)
            self.assertEqual((await s.get(User,self.uid)).xp,0)
            self.assertEqual(await s.scalar(select(func.count()).select_from(CalendarEvent).where(
                CalendarEvent.user_id==self.uid,CalendarEvent.source_type=='global_plan')),len(event_ids))

    async def counts(self):
        async with unit_of_work() as s:
            return tuple([await s.scalar(select(func.count()).select_from(m).where(m.user_id==self.uid)) for m in
                (CalendarEvent,TaskInstance,FinancialTransaction)])

    async def test_stale_fabricated_and_protected_scenarios_are_rejected(self):
        result=await self.simulate();body={'scenario':result['plan']['scenario'],'fingerprint':result['state']['fingerprint'],
            'blocks':result['plan']['blocks'],'confirmed':True}
        async with unit_of_work() as s:s.add(Task(user_id=self.uid,title='New fixed',date=self.day,scheduled_time=time(18),duration_minutes=60))
        self.assertEqual((await self.http.post('/api/life/accept',json=body,headers={'Idempotency-Key':'stale-confirm-key'})).status_code,409)
        identity=next(c['id'] for d in result['state']['domains'] for c in d['candidates'] if c['date_locked'])
        self.assertEqual((await self.http.post('/api/life/simulate',json={'date':str(self.day),'exclude':[identity]})).status_code,422)
        self.assertEqual((await self.http.post('/api/life/simulate',json={'date':str(self.day),'durations':{'foreign':50}})).status_code,422)
        self.assertEqual((await self.http.post('/api/life/accept',json=body)).status_code,428)

    async def test_overnight_commitments_fixed_tasks_and_unknown_duration_fail_closed(self):
        async with unit_of_work() as s:
            s.add(CalendarEvent(user_id=self.uid,title='Overnight',start_at=datetime.combine(self.day-timedelta(days=1),time(23),timezone.utc),
                end_at=datetime.combine(self.day,time(12),timezone.utc)))
            s.add(Task(user_id=self.uid,title='Unknown fixed',date=self.day,scheduled_time=time(17)))
        result=await self.simulate();self.assertFalse(result['state']['planning_safe']);self.assertFalse(result['plan']['blocks'])
        self.assertTrue(any(c['title']=='Overnight' and c['start_minute']==0 for c in result['plan']['constraints']))

    async def test_existing_study_schedule_covers_canonical_budget_without_duplicate(self):
        async with unit_of_work() as s:
            labels=('monday','tuesday','wednesday','thursday','friday','saturday','sunday')
            s.add(StudySchedule(user_id=self.uid,notebook_id=self.nid,day_of_week=labels[self.day.weekday()],start_time=time(18),end_time=time(19),repeat=True))
        result=await self.simulate()
        self.assertFalse(any(b['domain']=='preparation' for b in result['plan']['blocks']))
        self.assertTrue(any(c['domain']=='preparation' for c in result['plan']['constraints']))

    async def test_dst_day_is_not_allocated_and_empty_availability_is_not_invented(self):
        async with unit_of_work() as s:
            user=await s.get(User,self.uid);user.timezone='America/New_York';user.preferences={'life_availability':self.availability}
        state=await snapshot(self.uid,day=date(2026,11,1),now=datetime(2026,10,8,12,tzinfo=timezone.utc))
        self.assertFalse(state.planning_safe);self.assertFalse(preview(state,now=datetime(2026,10,8,12,tzinfo=timezone.utc))['blocks'])
        self.ok(await self.http.put('/api/life/availability',json={'weekdays':[[] for _ in range(7)]},headers={'Idempotency-Key':'clear-availability'}))
        result=await self.simulate();self.assertEqual(result['plan']['available_minutes'],0)

    async def test_old_overdue_tasks_preserve_completion_and_query_count_is_bounded(self):
        async with unit_of_work() as s:
            done=Task(user_id=self.uid,title='Done old task',date=self.day-timedelta(days=90),duration_minutes=20)
            pending=Task(user_id=self.uid,title='Old overdue task',date=self.day-timedelta(days=90),duration_minutes=20)
            s.add_all([done,pending]);await s.flush();s.add(TaskInstance(user_id=self.uid,task_id=done.id,date=done.date,status='done',completed=True))
        from sqlalchemy import event
        from db.engine import get_engine
        engine=get_engine().sync_engine;queries=[]
        def record(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('SELECT'):queries.append(statement)
        event.listen(engine,'before_cursor_execute',record)
        try:
            result=await self.simulate();small=len(queries);queries.clear()
            async with unit_of_work() as s:s.add_all([Task(user_id=self.uid,title='Extra'+str(i),date=self.day,duration_minutes=5) for i in range(90)])
            await self.simulate();large=len(queries)
        finally:event.remove(engine,'before_cursor_execute',record)
        self.assertEqual(small,large);self.assertLessEqual(large,25)
        text=str(result['state']);self.assertIn('Old overdue task',text);self.assertNotIn('Done old task',text)

    async def test_temporal_truncation_and_foreign_workout_fail_closed(self):
        async with unit_of_work() as s:s.add_all([CalendarEvent(user_id=self.uid,title='Fixed'+str(i),
            start_at=datetime.combine(self.day,time(20),timezone.utc),end_at=datetime.combine(self.day,time(21),timezone.utc)) for i in range(1001)])
        result=await self.simulate();self.assertFalse(result['state']['planning_safe']);self.assertFalse(result['plan']['blocks'])
        response=await self.http.put('/api/life/availability',json=self.availability,
            headers={'Idempotency-Key':'foreign-workout-choice','Authorization':'Bearer bob'})
        self.assertEqual(response.status_code,404)

    async def test_explicit_release_preserves_fixed_history_domain_records_and_receipt(self):
        result=await self.simulate();body={'scenario':result['plan']['scenario'],'fingerprint':result['state']['fingerprint'],
            'blocks':result['plan']['blocks'],'confirmed':True}
        accepted=self.ok(await self.http.post('/api/life/accept',json=body,headers={'Idempotency-Key':'release-setup-plan'}))
        event_id=accepted['event_ids'][0];url='/api/life/allocations/'+event_id
        self.assertEqual((await self.http.delete(url,params={'confirmed':'true'},headers={'Authorization':'Bearer bob','Idempotency-Key':'foreign-release'})).status_code,404)
        self.assertEqual((await self.http.delete(url,headers={'Idempotency-Key':'unconfirmed-release'})).status_code,422)
        headers={'Idempotency-Key':'release-confirmed-slot'}
        self.ok(await self.http.delete(url,params={'confirmed':'true'},headers=headers))
        self.assertTrue(self.ok(await self.http.delete(url,params={'confirmed':'true'},headers=headers))['replayed'])
        async with unit_of_work() as s:
            fixed=await s.scalar(select(CalendarEvent).where(CalendarEvent.user_id==self.uid,CalendarEvent.title=='Work'))
            self.assertIsNotNone(fixed);self.assertFalse((await s.get(StudyPlanEntry,self.entry.id)).completed)
        self.assertEqual((await self.http.delete('/api/life/allocations/'+str(fixed.id),params={'confirmed':'true'},headers={'Idempotency-Key':'cannot-release-fixed'})).status_code,404)
