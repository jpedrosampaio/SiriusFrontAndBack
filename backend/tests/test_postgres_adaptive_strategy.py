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
        self.assertLessEqual(result['scenarios']['A']['minutes'],480)
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

    async def test_two_partial_review_blocks_reach_cost_before_deferral(self):
        from db.models.studies import ReviewEvent
        from datetime import datetime,timezone
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={
            'conteudo_programatico':[{'assunto':'First','subtopicos':[]}]}))
        async with unit_of_work() as session:
            topic=await session.scalar(select(StudyTopic).where(StudyTopic.user_id==self.uid,
                StudyTopic.notebook_id==UUID(self.nid),StudyTopic.archived_at.is_(None)))
            session.add(ReviewEvent(user_id=self.uid,topic_id=topic.id,
                reviewed_at=datetime(2026,9,27,tzinfo=timezone.utc),next_review=self.today-timedelta(days=1),result='practice'))
        result=self.ok(await self.http.post(self.base+'/dated-plan',json={'start_date':self.today.isoformat(),
            'end_date':self.today.isoformat(),'availability':[30]*7,'adaptive':True,'block_minutes':15},
            headers={'Idempotency-Key':'partial-review-completion'}))
        self.assertEqual(len(result['entries']),2)
        self.assertTrue(all(e['minutes']==15 and e['kind']=='Revisão' and e['topic_key']=='0' for e in result['entries']))

    async def test_recovery_includes_day_28_and_preserves_older_automatic_history(self):
        async with unit_of_work() as session:
            plan=StudyPlan(user_id=self.uid,program_id=UUID(self.pid),start_date=self.today-timedelta(days=29),
                end_date=self.today,availability=[60]*7,block_minutes=50)
            session.add(plan); await session.flush()
            rows=[StudyPlanEntry(user_id=self.uid,plan_id=plan.id,notebook_id=UUID(self.nid),
                date=self.today-timedelta(days=age),name=str(age),minutes=60,kind='study') for age in (28,29)]
            session.add_all(rows); await session.flush(); boundary,older=(str(e.id) for e in rows)
        before=self.ok(await self.http.get(self.base+'/strategy'))
        self.assertEqual([e['entry_id'] for e in before['debt']['missed_blocks']],[boundary])
        result=self.ok(await self.http.post(self.base+'/dated-plan',json={'start_date':self.today.isoformat(),
            'end_date':self.today.isoformat(),'availability':[60]*7,'adaptive':True,'recovery':True},
            headers={'Idempotency-Key':'recovery-28-day-boundary'}))
        identities={e['entry_id'] for e in result['entries']}
        self.assertNotIn(boundary,identities);self.assertIn(older,identities)

    async def test_legacy_notebook_without_topics_keeps_explicit_discipline_planning(self):
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={'conteudo_programatico':[]}))
        body={'start_date':self.today.isoformat(),'end_date':self.today.isoformat(),'availability':[60]*7,'block_minutes':60}
        before=self.ok(await self.http.post(self.base+'/dated-plan',json=body))
        self.assertEqual(len(before['entries']),1)
        after=self.ok(await self.http.post(self.base+'/dated-plan',json={**body,'adaptive':True},
            headers={'Idempotency-Key':'legacy-no-active-topics'}))
        self.assertEqual(len(after['entries']),1)
        self.assertIsNone(after['entries'][0]['topic_id'])
        self.assertEqual(after['entries'][0]['minutes'],60)
        self.assertIn('sem prioridade por tópico',after['entries'][0]['reason'])

    async def test_review_history_counts_distinct_prior_local_days(self):
        from db.models.studies import ReviewEvent,QuestionAttempt
        from db.models.exams import Question
        from datetime import datetime,time,timezone
        current=datetime.combine(self.today,time(18),timezone.utc)
        async with unit_of_work() as session:
            topic=await session.scalar(select(StudyTopic).where(StudyTopic.user_id==self.uid,
                StudyTopic.notebook_id==UUID(self.nid),StudyTopic.topic_key=='0'))
            question=Question(user_id=self.uid,notebook_id=UUID(self.nid),topic_id=topic.id,
                statement='History fixture',source='manual',question_type='manual')
            session.add(question); await session.flush()
            session.add_all([QuestionAttempt(user_id=self.uid,notebook_id=UUID(self.nid),topic_id=topic.id,
                question_id=question.id,total=1,correct=1,source='manual',answered_at=current,evidence={'answered':True}) for _ in range(50)])
            session.add_all([ReviewEvent(user_id=self.uid,topic_id=topic.id,reviewed_at=current,
                result='practice',next_review=self.today) for _ in range(20)])
            tid=topic.id
        first=next(c for c in self.ok(await self.http.get(self.base+'/strategy'))['candidates'] if c['id']==str(tid))
        self.assertEqual((first['review_history_days'],first['review_interval_days']),(0,14))
        async with unit_of_work() as session:
            # 01:00 UTC is yesterday22:00 in Sao Paulo, while tomorrow01:00 is today22:00.
            stamps=[datetime.combine(self.today,time(1),timezone.utc)]*3+[
                datetime.combine(self.today+timedelta(days=1),time(1),timezone.utc)]
            session.add_all([ReviewEvent(user_id=self.uid,topic_id=tid,reviewed_at=stamp,
                result='practice',next_review=self.today) for stamp in stamps])
        second=next(c for c in self.ok(await self.http.get(self.base+'/strategy'))['candidates'] if c['id']==str(tid))
        self.assertEqual((second['review_history_days'],second['review_interval_days']),(1,17))

    async def test_mixed_notebooks_keep_legacy_discipline_capacity(self):
        legacy=self.ok(await self.http.post('/api/study/notebooks',json={
            'area_id':self.notebook['area_id'],'program_id':self.pid,'name':'Legacy','weight':2}))
        result=self.ok(await self.http.post(self.base+'/dated-plan',json={
            'start_date':self.today.isoformat(),'end_date':self.today.isoformat(),
            'availability':[200]*7,'adaptive':True,'block_minutes':50},
            headers={'Idempotency-Key':'mixed-legacy-discipline'}))
        canonical=[e for e in result['entries'] if e['notebook_id']==self.nid]
        fallback=[e for e in result['entries'] if e['notebook_id']==legacy['notebook_id']]
        self.assertTrue(canonical);self.assertTrue(fallback)
        self.assertTrue(all(e['topic_id'] and e['topic_key'] in ('0','1') for e in canonical))
        self.assertTrue(all(e['topic_id'] is None and e['topic_key'] is None for e in fallback))
        strategy=self.ok(await self.http.get(self.base+'/strategy'))
        self.assertTrue(strategy['coverage_partial'])
        self.assertEqual([d['id'] for d in strategy['topicless_disciplines']],[legacy['notebook_id']])
        self.assertEqual(len(strategy['debt']['critical_unstarted']),2)

    async def test_protected_topic_contact_prevents_same_date_duplicate(self):
        async with unit_of_work() as session:
            topic=await session.scalar(select(StudyTopic).where(StudyTopic.user_id==self.uid,
                StudyTopic.notebook_id==UUID(self.nid),StudyTopic.topic_key=='0'))
            plan=StudyPlan(user_id=self.uid,program_id=UUID(self.pid),start_date=self.today,
                end_date=self.today,availability=[150]*7,block_minutes=50)
            session.add(plan);await session.flush()
            row=StudyPlanEntry(user_id=self.uid,plan_id=plan.id,notebook_id=UUID(self.nid),topic_id=topic.id,
                date=self.today,name='Protected contact',minutes=50,kind='Teoria e quest\u00f5es',fixed=True)
            session.add(row);await session.flush();identity,tid=str(row.id),str(topic.id)
        result=self.ok(await self.http.post(self.base+'/dated-plan',json={
            'start_date':self.today.isoformat(),'end_date':self.today.isoformat(),
            'availability':[150]*7,'adaptive':True,'block_minutes':50},
            headers={'Idempotency-Key':'protected-full-contact'}))
        same_topic=[e for e in result['entries'] if e['topic_id']==tid]
        self.assertEqual([e['entry_id'] for e in same_topic],[identity])
        self.assertTrue(same_topic[0]['fixed']);self.assertEqual(same_topic[0]['minutes'],50)
        self.assertTrue(any(e['topic_id']!=tid for e in result['entries']))
