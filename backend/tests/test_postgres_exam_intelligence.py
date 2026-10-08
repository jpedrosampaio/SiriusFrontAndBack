import os,asyncio,unittest
from uuid import UUID
from sqlalchemy import select,func
from unittest.mock import patch
from db.session import unit_of_work
from db.models.exams import ExamAttempt,Question
from db.models.studies import QuestionAttempt
from db.models.identity import User
import test_postgres_runtime_exams as runtime_tests

@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class ExamIntelligence(unittest.IsolatedAsyncioTestCase):
    ok=runtime_tests.RuntimeExams.ok
    setup_catalog=runtime_tests.RuntimeExams.setup_catalog
    create=runtime_tests.RuntimeExams.create
    async def asyncSetUp(self):await runtime_tests.RuntimeExams.asyncSetUp(self)
    async def asyncTearDown(self):await runtime_tests.RuntimeExams.asyncTearDown(self)
    async def begin(self):
        self.eid=self.ok(await self.create())['simulado']['simulado_id'];self.url='/api/study/simulados/'+self.eid
        return self.ok(await self.http.post(self.url+'/session',json={},headers={'Idempotency-Key':'start-execution'}))
    async def store(self,execution,answers=None,seconds=30,key='save-execution'):
        return await self.http.put(self.url+'/session',json={'session_id':execution['session_id'],'revision':execution['revision'],
            'answers':answers if answers is not None else [{'question_idx':0,'selected_answer':'A','seconds':20,'confidence':'guess'}],
            'current_question':1,'marked':[0],'elapsed_seconds':seconds},headers={'Idempotency-Key':key})
    async def test_resume_cas_foreign_access_and_finish_exactly_once(self):
        d=await self.begin();self.assertEqual(self.ok(await self.http.post(self.url+'/session',json={},headers={'Idempotency-Key':'another-start'}))['session_id'],d['session_id'])
        saved=self.ok(await self.store(d));self.assertEqual(saved['revision'],1)
        self.assertTrue(self.ok(await self.store(d))['replayed'])
        self.assertEqual((await self.store(d,key='stale-tab')).status_code,409)
        self.assertEqual(self.ok(await self.http.get(self.url+'/session'))['answers'][0]['seconds'],20)
        foreign={'Authorization':'Bearer bob','Idempotency-Key':'foreign-start'}
        self.assertEqual((await self.http.get(self.url+'/session',headers=foreign)).status_code,404)
        self.assertEqual((await self.http.post(self.url+'/session',json={},headers=foreign)).status_code,404)
        self.assertEqual((await self.http.post(self.url+'/submit',json={'answers':[]},headers={'Idempotency-Key':'missing-session'})).status_code,409)
        body={'session_id':saved['session_id'],'revision':saved['revision'],'answers':[]}
        responses=await asyncio.gather(*(self.http.post(self.url+'/submit',json=body,headers={'Idempotency-Key':f'finish-{i:08d}'}) for i in range(6)))
        self.assertEqual([r.status_code for r in responses].count(200),1)
        self.assertEqual([r.status_code for r in responses].count(409),5)
        result=self.ok(next(r for r in responses if r.status_code==200));self.assertEqual(result['unanswered'],1)
        self.assertEqual(result['score'],66.7);self.assertEqual(result['time_spent_seconds'],30)
        self.assertEqual(result['post_mortem']['confidence']['guess']['accuracy'],100)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(ExamAttempt).where(ExamAttempt.user_id==self.uid)),1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.user_id==self.uid)),2)
            self.assertEqual((await session.get(User,self.uid)).xp,7)
        self.assertEqual(self.ok(await self.http.get(self.url+'/session'))['status'],'completed')
    async def test_timing_change_flags_validation_and_atomic_completion_failure(self):
        d=await self.begin();s=self.ok(await self.store(d))
        self.assertEqual((await self.store(s,seconds=10,key='time-retrograde')).status_code,422)
        self.assertEqual((await self.store(s,answers=[{'question_idx':0,'selected_answer':'B','seconds':10}],key='question-retrograde')).status_code,422)
        self.assertEqual((await self.store(s,answers=[{'question_idx':0,'selected_answer':'Z','seconds':20}],key='invalid-option')).status_code,422)
        s=self.ok(await self.store(s,answers=[{'question_idx':0,'selected_answer':'B','seconds':20,'changed_answer':False}],key='changed-evidence'))
        self.assertTrue(self.ok(await self.http.get(self.url+'/session'))['answers'][0]['changed_answer'])
        body={'session_id':s['session_id'],'revision':s['revision'],'answers':[]}
        with patch('services.exams.apply_xp',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):await self.http.post(self.url+'/submit',json=body,headers={'Idempotency-Key':'failed-finish'})
        self.assertEqual(self.ok(await self.http.get(self.url+'/session'))['status'],'active')
        result=self.ok(await self.http.post(self.url+'/submit',json=body,headers={'Idempotency-Key':'failed-finish'}))
        self.assertEqual(result['xp_earned'],0);self.assertEqual(result['post_mortem']['changed_answers'],1)
    async def test_assembly_reuses_question_identity_and_weak_scope(self):
        await self.begin()
        async with unit_of_work() as session:
            original=set((await session.scalars(select(Question.id).where(Question.user_id==self.uid))).all())
            for question in (await session.scalars(select(Question).where(Question.user_id==self.uid))).all():
                question.provenance={**question.provenance,'question_number':9}
        path=f'/api/study/v2/programs/{self.pid}/blueprint/simulado'
        body={'title':'Focused','duration_minutes':30,'mode':'discipline','notebook_ids':[self.nid],'num_questions':2}
        assembled=self.ok(await self.http.post(path,json=body,headers={'Idempotency-Key':'assemble-owned'}))
        self.assertEqual({UUID(q['question_id']) for q in assembled['questions']},original)
        target='/api/study/simulados/'+assembled['simulado_id']
        detail=self.ok(await self.http.get(target))
        self.assertEqual([q['question_number'] for q in detail['questions']],[1,2])
        result=self.ok(await self.http.post(target+'/submit',json={'answers':[]},headers={'Idempotency-Key':'assembled-numbering'}))
        self.assertEqual([a['question_number'] for a in result['answers']],[1,2])
        async with unit_of_work() as session:self.assertEqual(await session.scalar(select(func.count()).select_from(Question).where(Question.user_id==self.uid)),2)
        body['notebook_ids']=['00000000-0000-0000-0000-000000000001']
        self.assertEqual((await self.http.post(path,json=body,headers={'Idempotency-Key':'assemble-foreign'})).status_code,422)
        body.update(mode='weak',notebook_ids=[])
        self.assertEqual(len(self.ok(await self.http.post(path,json=body,headers={'Idempotency-Key':'assemble-weak'}))['questions']),2)

    async def test_sourced_penalties_roundtrip_and_legacy_history_unchanged(self):
        await self.begin()
        path=f'/api/study/v2/programs/{self.pid}/blueprint/simulado'
        body={'title':'Sourced','duration_minutes':30,'mode':'discipline','notebook_ids':[self.nid],
            'num_questions':2,'wrong_penalty':1,'blank_penalty':.5}
        self.assertEqual((await self.http.post(path,json=body,headers={'Idempotency-Key':'unconfirmed-rule'})).status_code,422)
        body.update(scoring_source='Edital p4',scoring_excerpt='Desconto informado',confirm_scoring_source=True)
        e=self.ok(await self.http.post(path,json=body,headers={'Idempotency-Key':'sourced-rule'}));url='/api/study/simulados/'+e['simulado_id']
        detail=self.ok(await self.http.get(url));expected=detail['questions'][0]['correct_answer']
        wrong='B' if expected=='A' else 'A'
        r=self.ok(await self.http.post(url+'/submit',json={'answers':[{'question_idx':0,'selected_answer':wrong}]},headers={'Idempotency-Key':'sourced-answer'}))
        self.assertEqual(r['raw_points'],-1.5);self.assertEqual(r['score'],0);self.assertEqual(r['xp_earned'],0)
        historical=self.ok(await self.http.get(url+'/results'))[0]
        self.assertEqual(historical['scoring_rules']['excerpt'],'Desconto informado')
        self.assertEqual(historical['post_mortem']['by_discipline']['Português']['points_lost'],3.5)
