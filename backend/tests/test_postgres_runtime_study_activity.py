import asyncio
import os
import unittest
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.studies import StudySession,QuestionAttempt
from db.models.identity import User
from services.planning import apply_xp
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeStudyActivity(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok
    setup_catalog=catalog_tests.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        async def account(request):
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.activity_auth=patch('services.study_activity_routes.account',account); self.activity_auth.start()
        _,self.program,self.notebook=await self.setup_catalog()
        self.nid=self.notebook['notebook_id']

    async def asyncTearDown(self):
        self.activity_auth.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def test_focus_retries_commit_one_session_time_and_xp(self):
        payload={'notebook_id':self.nid,'focus_minutes':25,'break_minutes':5,'notes':'draft'}
        responses=await asyncio.gather(*(self.http.post('/api/study/focus/complete',json=payload,headers={'Idempotency-Key':'focus-same-request'}) for _ in range(20)))
        for response in responses: self.ok(response)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudySession).where(StudySession.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,5)
        notebook=self.ok(await self.http.get('/api/study/notebooks'))[0]
        self.assertEqual(notebook['total_study_time_minutes'],25)
        stats=self.ok(await self.http.get('/api/study/focus/stats'))
        self.assertEqual(stats['today']['total_minutes'],25)
        self.assertEqual(stats['all_time']['sessions'],1)
        self.assertEqual(self.ok(await self.http.get('/api/study/streak'))['current_streak'],1)
        self.assertEqual((await self.http.post('/api/study/focus/complete',json=payload,headers={'Authorization':'Bearer bob'})).status_code,404)

    async def test_focus_failure_rolls_back_minutes_session_and_xp(self):
        def fail(user,delta):
            apply_xp(user,delta)
            raise RuntimeError('injected failure')
        with patch('services.study_activity_routes.apply_xp',fail):
            with self.assertRaises(Exception):
                await self.http.post('/api/study/focus/complete',json={'notebook_id':self.nid,'focus_minutes':25})
        self.assertEqual(self.ok(await self.http.get('/api/study/notebooks'))[0]['total_study_time_minutes'],0)
        self.assertEqual(self.ok(await self.http.get('/api/study/focus/stats'))['all_time']['sessions'],0)
        async with unit_of_work() as session: self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_question_and_session_facts_and_validation(self):
        body={'notebook_id':self.nid,'total':10,'correct':7}
        self.ok(await self.http.post('/api/study/questions/log',json=body))
        self.ok(await self.http.post('/api/study/sessions',json={'notebook_id':self.nid,'duration_minutes':30,'date':'2026-10-01'}))
        stats=self.ok(await self.http.get('/api/study/questions/stats',params={'program_id':self.program['program_id']}))
        self.assertEqual((stats['total_questions'],stats['correct'],stats['accuracy']),(10,7,70))
        self.assertEqual(stats['by_notebook'][self.nid]['incorrect'],3)
        self.assertEqual(self.ok(await self.http.get('/api/study/sessions',params={'date':'2026-10-01'}))[0]['duration_minutes'],30)
        self.assertEqual((await self.http.post('/api/study/questions/log',json={**body,'correct':11})).status_code,422)
        self.assertEqual((await self.http.post('/api/study/questions/log',json=body,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual(self.ok(await self.http.get('/api/study/questions/stats',headers={'Authorization':'Bearer bob'}))['total_questions'],0)

    async def test_progress_rejects_foreign_notebook_paths_and_non_boolean_flags(self):
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={'conteudo_programatico':[{'assunto':'Crase','subtopicos':['Exceções']}]}))
        path=f'/api/study/notebooks/{self.nid}/topic-progress'
        body={'topic_key':'0_0','status':'studied','checked':True}
        self.assertEqual((await self.http.post(path,json=body,headers={'Authorization':'Bearer bob'})).status_code,404)
        for invalid in ({'topic_key':'0.$x'},{'topic_key':'0','status':'studied.other'},{'topic_key':'0','checked':'false'}):
            self.assertEqual((await self.http.post(path,json=invalid)).status_code,422)
        self.assertTrue(self.ok(await self.http.post(path,json=body))['topics']['0_0']['studied'])
        self.assertTrue(self.ok(await self.http.get(path))['topics']['0_0']['studied'])
        self.ok(await self.http.post(path,json={**body,'checked':False}))
        self.assertNotIn('studied',self.ok(await self.http.get(path))['topics']['0_0'])
