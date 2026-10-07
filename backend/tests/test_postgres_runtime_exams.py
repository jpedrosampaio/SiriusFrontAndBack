import os
import json
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.exams import Exam,ExamAttempt
from db.models.studies import QuestionAttempt,ReviewEvent
from db.models.identity import User
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeExams(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok
    setup_catalog=catalog_tests.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        area,program,notebook=await self.setup_catalog(); self.aid=area['area_id']; self.pid=program['program_id']; self.nid=notebook['notebook_id']
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={'conteudo_programatico':[{'assunto':'Crase'}]}))
        self.questions=[{'question_text':'Questão 1','correct_answer':'A','weight':2,'options':['A','B']},
            {'question_text':'Questão 2','correct_answer':'B','weight':1,'options':['A','B']}]
        self.generate=AsyncMock(return_value=SimpleNamespace(text=json.dumps({'questions':self.questions})))
        async def authenticate(authorization=None,session_token=None): return SimpleNamespace(user_id=str(self.bob if authorization=='Bearer bob' else self.uid))
        async def account(request): return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.patches=[patch('services.exam_generation_routes.get_current_user',authenticate),patch('services.exam_generation_routes.get_user_api_key',AsyncMock(return_value='fake')),
            patch('services.exam_generation_routes.request_gemini',self.generate),patch('services.exam_routes.account',account),
            patch('services.study_activity_routes.account',account),patch('services.studies_v2_routes.account',account)]
        for p in self.patches: p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches): p.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def create(self,headers=None,count=2):
        return await self.http.post('/api/study/simulados/generate',json={'title':'Teste','program_id':self.pid,'notebook_id':self.nid,
            'topic_key':'0','num_questions':count,'topic':'untrusted topic','banca':'FGV'},headers={'Idempotency-Key':'generate-exam-once',**(headers or {})})

    async def test_topic_generation_submit_replay_reviews_and_archive(self):
        created=self.ok(await self.create()); exam=created['simulado']; eid=exam['simulado_id']
        self.assertEqual(exam['questions'][0]['subdisciplina'],'Crase'); self.assertEqual(exam['questions'][0]['topic_key'],'0')
        self.assertEqual(exam['questions'][0]['notebook_id'],self.nid); self.assertEqual(exam['questions'][0]['provenance'],'inferred')
        self.assertIn('Crase',self.generate.call_args.kwargs['config']['system_instruction'])
        base='/api/study/simulados/'+eid
        body={'answers':[{'question_idx':0,'selected_answer':'A'}],'time_spent_seconds':30}
        responses=await asyncio.gather(*(self.http.post(base+'/submit',json=body,headers={'Idempotency-Key':'submit-exam-once'}) for _ in range(6)))
        for response in responses: self.assertEqual(self.ok(response)['score'],66.7)
        async with unit_of_work() as session:
            for model,n in ((ExamAttempt,1),(QuestionAttempt,2),(ReviewEvent,1)):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),n)
            self.assertEqual((await session.get(User,self.uid)).xp,7)
        self.assertEqual(self.ok(await self.http.get('/api/study/v2/performance'))['summary']['samples'],1)
        stats=self.ok(await self.http.get('/api/study/simulados/stats'))
        self.assertEqual(stats['total_attempts'],1); self.assertEqual(stats['total_correct'],1)
        self.assertEqual(stats['by_banca']['FGV']['attempts'],1)
        listing=self.ok(await self.http.get('/api/study/simulados',params={'area_id':self.aid}))
        self.assertEqual(listing[0]['questions_count'],2); self.assertEqual(listing[0]['attempts_count'],1)
        self.assertNotIn('questions',listing[0])
        self.assertEqual(len(self.ok(await self.http.get(base+'/results'))),1)
        self.assertEqual(len(self.ok(await self.http.get(base))['questions']),2)
        foreign={'Authorization':'Bearer bob','Idempotency-Key':'foreign-submit'}
        for suffix in ('','/results'): self.assertEqual((await self.http.get(base+suffix,headers=foreign)).status_code,404)
        self.assertEqual((await self.http.post(base+'/submit',json=body,headers=foreign)).status_code,404)
        self.ok(await self.http.delete(base))
        self.assertEqual((await self.http.get(base)).status_code,404)
        self.assertEqual(self.ok(await self.http.get('/api/study/simulados/stats'))['total_attempts'],0)

    async def test_foreign_scope_and_wrong_question_count_never_save(self):
        self.assertEqual((await self.create(headers={'Authorization':'Bearer bob'})).status_code,404)
        self.generate.assert_not_awaited()
        self.assertEqual((await self.create(count=4)).status_code,502)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Exam).where(Exam.user_id==self.uid)),0)

    async def test_submission_rollback_keeps_generation_xp_only(self):
        eid=self.ok(await self.create())['simulado']['simulado_id']
        body={'answers':[{'question_idx':0,'selected_answer':'A'}],'time_spent_seconds':30}
        with patch('services.exams.apply_xp',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError): await self.http.post('/api/study/simulados/'+eid+'/submit',json=body,headers={'Idempotency-Key':'exam-rollback'})
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(ExamAttempt).where(ExamAttempt.user_id==self.uid)),0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,5)

    async def test_pdf_import_normalizes_questions_and_cleans_temporary_file(self):
        paths=[]
        async def upload(path,uid):
            paths.append(path); self.assertTrue(Path(path).is_file()); return SimpleNamespace(uri='test://pdf')
        with patch('services.exam_generation_routes.upload_gemini_path',upload),patch('services.exam_generation_routes.gemini_file_part',return_value={}):
            result=self.ok(await self.http.post('/api/study/simulados/import-pdf',data={'title':'PDF','area_id':self.aid,'program_id':self.pid},
                files={'file':('prova.pdf',b'%PDF-test','application/pdf')}))
        self.assertEqual(result['simulado']['questions_count'],2)
        self.assertEqual(result['simulado']['source_type'],'pdf_import')
        self.assertTrue(all(not Path(p).exists() for p in paths))
