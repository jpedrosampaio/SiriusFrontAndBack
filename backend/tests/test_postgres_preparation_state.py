import asyncio
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from unittest.mock import patch
from db.session import unit_of_work
from db.models.studies import StudySession, StudyPlan, StudyPlanEntry
import test_postgres_runtime_catalog as catalog


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class PreparationStateTests(unittest.IsolatedAsyncioTestCase):
    ok = catalog.RuntimeCatalog.ok
    setup_catalog = catalog.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await catalog.RuntimeCatalog.asyncSetUp(self)
        async def account(request):
            return {'user_id': str(self.bob if request.headers.get('Authorization') == 'Bearer bob' else self.uid), 'timezone': 'America/Sao_Paulo'}
        self.patches = [patch('services.studies_v2_routes.account', account), patch('services.study_activity_routes.account', account)]
        for p in self.patches: p.start()
        _, self.program, self.notebook = await self.setup_catalog()
        self.pid = self.program['program_id']; self.nid = self.notebook['notebook_id']
        self.base = '/api/study/v2/programs/' + self.pid
        self.ok(await self.http.patch('/api/study/notebooks/' + self.nid, json={
            'conteudo_programatico': [{'assunto': 'Main', 'subtopicos': ['Child']}] }))

    async def asyncTearDown(self):
        for p in reversed(self.patches): p.stop()
        await catalog.RuntimeCatalog.asyncTearDown(self)

    async def test_empty_hierarchy_and_coverage_do_not_invent_mastery(self):
        initial = self.ok(await self.http.get(self.base + '/state'))
        nodes = initial['syllabus_graph']['topics']
        self.assertEqual(len(nodes), 2)
        parent = next(t for t in nodes if t['topic_key'] == '0')
        child = next(t for t in nodes if t['topic_key'] == '0_0')
        self.assertEqual(child['parent_id'], parent['id'])
        self.assertIsNone(initial['mastery']['score'])
        self.assertIsNone(initial['required_pace']['minutes_per_week'])
        self.assertEqual(initial['health']['status'], 'insufficient')
        self.ok(await self.http.post('/api/study/notebooks/' + self.nid + '/topic-progress', json={'topic_key': '0', 'status': 'studied', 'checked': True}))
        after = self.ok(await self.http.get(self.base + '/state'))
        self.assertEqual(after['coverage']['percent'], 50)
        self.assertIsNone(after['mastery']['score'])
        self.assertEqual(next(t for t in after['syllabus_graph']['topics'] if t['topic_key'] == '0')['stage'], 'exposed')
        self.assertEqual({t['id'] for t in nodes}, {t['id'] for t in after['syllabus_graph']['topics']})

    async def test_evidence_pace_debt_and_owner_isolation(self):
        today = date(2026, 10, 7)
        async with unit_of_work() as session:
            session.add(StudySession(user_id=self.uid, notebook_id=UUID(self.nid), date=today, duration_minutes=25, completed=True))
            session.add(StudySession(user_id=self.uid, notebook_id=UUID(self.nid), date=today, duration_minutes=100, completed=False))
            plan = StudyPlan(user_id=self.uid, program_id=UUID(self.pid), start_date=today-timedelta(days=1), end_date=today+timedelta(days=7), availability=[30]*7, block_minutes=30)
            session.add(plan); await session.flush()
            session.add(StudyPlanEntry(user_id=self.uid, plan_id=plan.id, notebook_id=UUID(self.nid), date=today-timedelta(days=1), name='Pending', minutes=30, kind='study'))
        self.ok(await self.http.post('/api/study/questions/log', json={'notebook_id': self.nid, 'total': 100, 'correct': 100}))
        response = self.ok(await self.http.post('/api/study/v2/attempts', json={'notebook_id': self.nid, 'topic_key': '0', 'question': 'Q', 'correct': False}, headers={'Idempotency-Key': 'prep-evidence-once'}))
        with patch('services.studies_v2_routes.local_today', return_value=today):
            state = self.ok(await self.http.get(self.base + '/state'))
        self.assertEqual(state['current_pace']['minutes_per_week'], 25)
        self.assertEqual(state['study_debt']['minutes'], 30)
        self.assertEqual(state['mastery']['samples'], 1)
        self.assertEqual(state['performance']['questions'], 101)
        self.assertIn(response['attempt_id'], next(t for t in state['syllabus_graph']['topics'] if t['topic_key'] == '0')['evidence_ids'])
        self.assertEqual({e['kind'] for e in state['evidence_ledger']}, {'session', 'practice', 'question', 'review'})
        foreign = {'Authorization': 'Bearer bob'}
        self.assertEqual((await self.http.get(self.base + '/state', headers=foreign)).status_code, 404)
        self.assertEqual((await self.http.put(self.base + '/primary', headers={**foreign, 'Idempotency-Key': 'foreign-primary'})).status_code, 404)
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={'conteudo_programatico':[]}))
        archived=self.ok(await self.http.get(self.base+'/state'))
        self.assertIsNone(archived['mastery']['score'])
        self.assertEqual(archived['performance']['questions'],101)
        self.ok(await self.http.delete('/api/study/notebooks/'+self.nid))
        with patch('services.studies_v2_routes.local_today',return_value=today):
            hidden=self.ok(await self.http.get(self.base+'/state'))
        self.assertEqual(hidden['study_debt']['overdue_blocks'],0)
        self.assertEqual(hidden['required_pace']['minutes_per_week'],0)
        self.assertIsNone(hidden['candidate_model']['consistency'])
        self.assertIsNone(hidden['next_session'])

    async def test_primary_is_single_replay_safe_and_preserves_preferences(self):
        from db.models.identity import User
        async with unit_of_work() as session:
            user = await session.get(User, self.uid); user.preferences = {'health_condition': 'kept'}
        result = await asyncio.gather(*(self.http.put(self.base + '/primary', headers={'Idempotency-Key': 'primary-once'}) for _ in range(5)))
        for response in result: self.ok(response)
        targets = self.ok(await self.http.get('/api/study/v2/targets'))
        self.assertEqual(sum(t['is_primary'] for t in targets), 1)
        other = self.ok(await self.http.post('/api/study/v2/targets', json={'name': 'Generic', 'kind': 'custom'}, headers={'Idempotency-Key': 'generic-target'}))
        self.ok(await self.http.put('/api/study/v2/programs/' + other['program_id'] + '/primary', headers={'Idempotency-Key': 'primary-other'}))
        targets = self.ok(await self.http.get('/api/study/v2/targets'))
        self.assertEqual([t['program_id'] for t in targets if t['is_primary']], [other['program_id']])
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User, self.uid)).preferences['health_condition'], 'kept')
        self.assertEqual((await self.http.put(self.base + '/primary')).status_code, 422)
        self.assertEqual((await self.http.put(self.base + '/primary', headers={'Idempotency-Key': 'primary-other'})).status_code, 409)
        self.ok(await self.http.delete('/api/study/programs/' + other['program_id']))
        self.assertFalse(any(t['is_primary'] for t in self.ok(await self.http.get('/api/study/v2/targets'))))

    async def test_projection_query_count_does_not_grow_per_topic(self):
        from sqlalchemy import event
        from db.engine import get_engine
        counts=[]
        def measure(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('SELECT'): counts.append(1)
        engine=get_engine().sync_engine
        event.listen(engine,'before_cursor_execute',measure)
        try:
            first=await self.http.get(self.base+'/state'); self.ok(first); small=len(counts)
            self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={
                'conteudo_programatico':[{'assunto':f'Topic {i}','subtopicos':[]} for i in range(100)]}))
            counts.clear(); expanded=await self.http.get(self.base+'/state'); state=self.ok(expanded)
            self.assertEqual(len(counts),small)
            self.assertLessEqual(small,25)
            self.assertEqual(state['coverage']['total'],100)
            self.assertLess(len(expanded.content),250000)
            print(f'Preparation projection: {small} SELECTs for 2 and 100 topics; 100-topic payload {len(expanded.content)} bytes')
        finally: event.remove(engine,'before_cursor_execute',measure)

    async def test_flashcard_and_exam_activity_do_not_invent_individual_mastery(self):
        from db.models.studies import Flashcard, FlashcardReview, StudyNote
        from db.models.exams import Exam, ExamAttempt, Question
        from db.models.studies import QuestionAttempt
        now=datetime.now(timezone.utc)
        async with unit_of_work() as session:
            card=Flashcard(user_id=self.uid,notebook_id=UUID(self.nid),deck_name='Deck',front='Front',back='Back',next_review=date(2026,1,1))
            exam=Exam(user_id=self.uid,program_id=UUID(self.pid),title='Exam',kind='simulado',status='ready')
            session.add_all([card,exam]); await session.flush()
            session.add(FlashcardReview(user_id=self.uid,flashcard_id=card.id,reviewed_at=now,quality=5))
            session.add(ExamAttempt(user_id=self.uid,exam_id=exam.id,completed_at=now,duration_seconds=60,score=100,scoring_version='test',result_details={}))
            session.add(StudyNote(user_id=self.uid,notebook_id=UUID(self.nid),title='Note',content='Not returned by this projection'))
            blank=Question(user_id=self.uid,notebook_id=UUID(self.nid),statement='Blank answer',question_type='manual',source='manual')
            session.add(blank); await session.flush()
            session.add(QuestionAttempt(user_id=self.uid,notebook_id=UUID(self.nid),question_id=blank.id,total=1,correct=0,
                source='simulado',answered_at=now,evidence={'answered':False}))
        state=self.ok(await self.http.get(self.base+'/state'))
        self.assertIsNone(state['mastery']['score'])
        self.assertEqual(state['performance'],{'questions':0,'correct':0,'accuracy':None})
        self.assertIsNone(next(c for c in state['health']['components'] if c['key']=='questions')['value'])
        self.assertEqual(state['reviews_due']['flashcards'],1)
        self.assertEqual({r['kind'] for r in state['evidence_ledger']},{'flashcard','exam'})
        self.assertTrue(all(not r['affects_mastery'] for r in state['evidence_ledger']))
        self.assertEqual({m['kind'] for m in state['syllabus_graph']['disciplines'][0]['materials']},{'note','flashcard'})

    async def test_truncated_hierarchy_keeps_every_selected_child_parent(self):
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={
            'conteudo_programatico':[{'assunto':'A','subtopicos':['A child']},{'assunto':'B','subtopicos':['B child']}]}))
        with patch('services.preparation_state.LIMIT',3):
            state=self.ok(await self.http.get(self.base+'/state'))
        topics=state['syllabus_graph']['topics']; selected={t['id'] for t in topics}
        self.assertTrue(state['truncated'])
        self.assertEqual({t['topic_key'] for t in topics if t['parent_id']==self.nid},{'0','1'})
        self.assertTrue(all(t['parent_id']==self.nid or t['parent_id'] in selected for t in topics))

    async def test_todays_pending_blocks_do_not_lower_past_consistency(self):
        today=date(2026,10,7)
        async with unit_of_work() as session:
            plan=StudyPlan(user_id=self.uid,program_id=UUID(self.pid),start_date=today-timedelta(days=1),end_date=today+timedelta(days=7),availability=[30]*7,block_minutes=30)
            session.add(plan); await session.flush()
            for day,completed in ((today-timedelta(days=1),True),(today,False)):
                session.add(StudyPlanEntry(user_id=self.uid,plan_id=plan.id,notebook_id=UUID(self.nid),date=day,name='Block',minutes=30,kind='study',completed=completed))
        with patch('services.studies_v2_routes.local_today',return_value=today):
            state=self.ok(await self.http.get(self.base+'/state'))
        self.assertEqual(state['candidate_model']['consistency'],100)
        self.assertEqual(state['study_debt']['overdue_blocks'],0)
        self.assertEqual(state['next_session']['date'],today.isoformat())
