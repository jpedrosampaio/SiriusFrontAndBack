import asyncio
import os
import unittest
from datetime import date,timedelta
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.studies import StudyProgram,StudyTarget,QuestionAttempt,ReviewEvent
from db.models.exams import Exam,Question,ExamQuestion
from services.time import local_today
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeStudiesV2(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok
    setup_catalog=catalog_tests.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        async def account(request):
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.patches=[patch('services.studies_v2_routes.account',account),patch('services.study_activity_routes.account',account)]
        for item in self.patches: item.start()
        _,self.program,self.notebook=await self.setup_catalog(); self.nid=self.notebook['notebook_id']; self.pid=self.program['program_id']
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={'conteudo_programatico':[{'assunto':'Crase','subtopicos':[]}],'num_questoes_edital':2,'weight':3}))

    async def asyncTearDown(self):
        for item in reversed(self.patches): item.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def test_attempt_concurrent_replay_counts_once_and_owner_isolation(self):
        body={'notebook_id':self.nid,'topic_key':'0','question':'Questão','correct':False,'error_reason':'forgot'}
        results=await asyncio.gather(*(self.http.post('/api/study/v2/attempts',json=body,headers={'Idempotency-Key':'attempt-once'}) for _ in range(8)))
        for result in results: self.ok(result)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.user_id==self.uid)),1)
        self.assertEqual(self.ok(await self.http.get('/api/study/notebooks'))[0]['total_questions'],1)
        foreign={'Authorization':'Bearer bob','Idempotency-Key':'foreign-owner-attempt'}
        self.assertEqual((await self.http.post('/api/study/v2/attempts',json=body,headers=foreign)).status_code,404)
        self.assertEqual(self.ok(await self.http.get('/api/study/v2/performance',headers=foreign))['summary']['samples'],0)
        self.assertEqual((await self.http.get('/api/study/v2/performance',params={'program_id':self.pid},headers=foreign)).status_code,404)
        result=self.ok(await self.http.get('/api/study/v2/performance'))
        self.assertEqual(result['error_causes'],{'forgot':1})
        self.ok(await self.http.patch('/api/study/v2/attempts/'+results[0].json()['attempt_id']+'/error',json={'reason':'attention'}))
        self.assertEqual(self.ok(await self.http.get('/api/study/v2/performance'))['error_causes'],{'attention':1})

    async def test_target_creation_replay_does_not_duplicate_program(self):
        body={'name':'Certificação X','kind':'certification','exam_date':'2027-01-01'}
        for _ in range(2): self.ok(await self.http.post('/api/study/v2/targets',json=body,headers={'Idempotency-Key':'target-once'}))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyTarget).where(StudyTarget.user_id==self.uid)),1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyProgram).where(StudyProgram.user_id==self.uid)),2)
        self.assertEqual(len(self.ok(await self.http.get('/api/study/v2/targets'))),2)

    async def test_overview_library_recommendations_reviews_and_empty_states(self):
        url=f'/api/study/v2/programs/{self.pid}'
        empty=self.ok(await self.http.get(url+'/overview'))
        self.assertEqual(empty['coverage'],{'studied':0,'total':1,'percent':0})
        self.assertIsNone(empty['mastery']['score'])
        self.assertEqual(self.ok(await self.http.get('/api/study/v2/today'))['studied_minutes'],0)
        self.ok(await self.http.post('/api/study/notes',json={'notebook_id':self.nid,'title':'Note','content':'Test'}))
        self.assertEqual(self.ok(await self.http.get('/api/study/v2/library'))['items'][0]['kind'],'note')
        self.assertEqual(len(self.ok(await self.http.get(url+'/recommendations'))['items']),1)
        body={'notebook_id':self.nid,'topic_key':'0','question':'Question','correct':False}
        self.ok(await self.http.post('/api/study/v2/attempts',json=body,headers={'Idempotency-Key':'review-attempt'}))
        future=local_today('America/Sao_Paulo')+timedelta(days=2)
        with patch('services.studies_v2_routes.local_today',return_value=future):
            reviews=self.ok(await self.http.get('/api/study/v2/reviews'))['items']
        self.assertEqual({r['kind'] for r in reviews},{'topic','wrong_question'})
        self.assertEqual(self.ok(await self.http.get(url+'/overview'))['questions'],1)

    async def test_blueprint_creates_normalized_exam_and_replays(self):
        url=f'/api/study/v2/programs/{self.pid}/blueprint'
        self.assertEqual(self.ok(await self.http.get(url))['total'],2)
        payload={'title':'Blueprint','duration_minutes':60,'confirm_provisional':True}; headers={'Idempotency-Key':'blueprint-once'}
        self.assertEqual((await self.http.post(url+'/simulado',json=payload,headers=headers)).status_code,422)
        async with unit_of_work() as session:
            exam=Exam(user_id=self.uid,program_id=UUID(self.pid),title='Source',kind='simulado',status='ready')
            session.add(exam); await session.flush()
            for index in range(3):
                question=Question(user_id=self.uid,notebook_id=UUID(self.nid),statement=f'Question {index}',question_type='multipla_escolha',
                    source='ai_generated',options=['A','B'],correct_answer='A',provenance={'disciplina':'Português'})
                session.add(question); await session.flush()
                session.add(ExamQuestion(user_id=self.uid,exam_id=exam.id,question_id=question.id,position=index))
        result=self.ok(await self.http.post(url+'/simulado',json=payload,headers=headers))
        self.assertEqual(result['questions_count'],2)
        self.assertTrue(all(q['weight']==3 for q in result['questions']))
        self.assertTrue(all(q['origin']=='ai_generated' for q in result['questions']))
        self.assertTrue(all(q['generated_by_ai'] for q in result['questions']))
        from services.exam_catalog import details
        async with unit_of_work() as session:
            stored=await details(session,self.uid,UUID(result['simulado_id']))
            self.assertTrue(all(q['generated_by_ai'] for q in stored['questions']))
            self.assertEqual(await session.scalar(select(func.count()).select_from(Question).where(Question.user_id==self.uid)),3)
        self.assertTrue(self.ok(await self.http.post(url+'/simulado',json=payload,headers=headers))['replayed'])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(ExamQuestion).where(ExamQuestion.user_id==self.uid,
                ExamQuestion.exam_id==UUID(result['simulado_id']))),2)
