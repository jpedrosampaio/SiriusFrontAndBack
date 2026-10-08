import os
import unittest
from datetime import date, timedelta
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.studies import StudyPlan,StudyPlanEntry,StudyTask,StudyTopic
import test_postgres_runtime_workspace as fixture


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class AdaptiveStrategy(unittest.IsolatedAsyncioTestCase):
    ok=fixture.RuntimeWorkspace.ok
    setup_catalog=fixture.RuntimeWorkspace.setup_catalog

    async def asyncSetUp(self):
        await fixture.RuntimeWorkspace.asyncSetUp(self)
        self.base=f'/api/study/programs/{self.pid}'
        self.today=date(2026,9,28)
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={
            'conteudo_programatico':[{'assunto':'First','subtopicos':[]},{'assunto':'Second','subtopicos':[]}]}))

    async def asyncTearDown(self): await fixture.RuntimeWorkspace.asyncTearDown(self)

    async def test_read_only_simulations_owner_and_invalid_period(self):
        initial=self.ok(await self.http.get(self.base+'/strategy'))
        self.assertEqual(len(initial['candidates']),2)
        self.assertIsNone(initial['candidates'][0]['review_due_date'])
        settings={'start_date':self.today.isoformat(),'end_date':'2026-10-04','availability':[120]*7,'missed_days':3}
        result=self.ok(await self.http.post(self.base+'/strategy/simulate',json=settings))
        self.assertFalse(result['facts_changed'])
        self.assertEqual(result['scenarios']['A']['minutes'],480)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyPlan).where(StudyPlan.user_id==self.uid)),0)
        self.assertEqual((await self.http.get(self.base+'/strategy',headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.post(self.base+'/strategy/simulate',json=settings,headers={'Authorization':'Bearer bob'})).status_code,404)
        for change in ({'start_date':'2026-01-01'},{'availability':[721]*7},{'end_date':'2027-09-01'},{'missed_days':-1}):
            self.assertEqual((await self.http.post(self.base+'/strategy/simulate',json={**settings,**change})).status_code,422)

    async def test_recovery_preserves_protected_blocks_and_replays_same_plan(self):
        async with unit_of_work() as session:
            plan=StudyPlan(user_id=self.uid,program_id=UUID(self.pid),start_date=self.today-timedelta(days=3),
                end_date=self.today+timedelta(days=6),availability=[60]*7,block_minutes=50)
            session.add(plan); await session.flush()
            rows=[StudyPlanEntry(user_id=self.uid,plan_id=plan.id,notebook_id=UUID(self.nid),
                date=self.today-timedelta(days=2),name=kind,kind='study',minutes=60,
                **flags) for kind,flags in [('done',{'completed':True}),('manual',{'manual':True}),('fixed',{'fixed':True}),('missed',{})]]
            session.add_all(rows); await session.flush(); keep={str(r.id) for r in rows[:3]}; missed=str(rows[3].id)
        body={'start_date':self.today.isoformat(),'end_date':'2026-10-04','availability':[60]*7,
            'adaptive':True,'recovery':True,'block_minutes':50}
        headers={'Idempotency-Key':'adaptive-recovery-once'}
        generated=self.ok(await self.http.post(self.base+'/dated-plan',json=body,headers=headers))
        replayed=self.ok(await self.http.post(self.base+'/dated-plan',json=body,headers=headers))
        self.assertTrue(replayed['replayed'])
        self.assertEqual(generated['entries'],replayed['entries'])
        ids={e['entry_id'] for e in generated['entries']}
        self.assertTrue(keep<=ids); self.assertNotIn(missed,ids)
        future=[e for e in generated['entries'] if e['date']>=self.today.isoformat()]
        self.assertTrue(all(e['topic_id'] and e['topic_key'] in ('0','1') for e in future))
        for day in {e['date'] for e in future}: self.assertLessEqual(sum(e['minutes'] for e in future if e['date']==day),60)
        loaded=self.ok(await self.http.get(self.base+'/dated-plan'))
        self.assertEqual(loaded['entries'],generated['entries'])
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={'conteudo_programatico':[]}))
        archived=self.ok(await self.http.get(self.base+'/dated-plan'))
        self.assertTrue(all(e['topic_key'] is None for e in archived['entries'] if e['topic_id']))

    async def test_only_owned_active_uncompleted_milestones_enter_debt(self):
        from db.models.studies import StudyTaskCheck
        from datetime import datetime,timezone
        async with unit_of_work() as session:
            tasks=[StudyTask(user_id=self.uid,notebook_id=UUID(self.nid),title=title,deadline=self.today-timedelta(days=1),
                recurrence=recurrence,archived_at=datetime.now(timezone.utc) if title=='Archived' else None)
                for title,recurrence in [('Late','once'),('Done','once'),('Daily','daily'),('Archived','once')]]
            session.add_all(tasks); await session.flush()
            session.add(StudyTaskCheck(user_id=self.uid,task_id=tasks[1].id,date=self.today,completed_at=datetime.now(timezone.utc),xp_earned=0))
        result=self.ok(await self.http.get(self.base+'/strategy'))
        self.assertEqual([m['title'] for m in result['debt']['late_milestones']],['Late'])
