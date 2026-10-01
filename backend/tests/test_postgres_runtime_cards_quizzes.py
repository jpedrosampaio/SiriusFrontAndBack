import os
import json
import asyncio
import unittest
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.identity import User
from db.models.studies import Flashcard,FlashcardReview,QuestionAttempt
from db.models.exams import Exam,ExamAttempt
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeCardsQuizzes(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok
    setup_catalog=catalog_tests.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        _,self.program,book=await self.setup_catalog(); self.nid=book['notebook_id']
        self.note=self.ok(await self.http.post('/api/study/notes',json={'notebook_id':self.nid,'title':'Crase','content':'Resumo'}))
        async def account(request):
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.llm=AsyncMock()
        self.patches=[patch(module+'.account',account) for module in ('services.study_cards','services.study_quizzes','services.study_activity_routes','services.studies_v2_routes')]
        self.patches.append(patch('services.study_cards._llm',self.llm))
        for p in self.patches: p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches): p.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def card(self):
        return self.ok(await self.http.post('/api/study/flashcards',json={'notebook_id':self.nid,'deck_name':'Gramática','front':'Pergunta','back':'Resposta','tags':['tag']}))

    async def test_card_review_concurrency_sm2_owner_and_archive(self):
        card=await self.card(); cid=card['flashcard_id']; url='/api/study/flashcards/'+cid
        self.assertEqual(len(self.ok(await self.http.get('/api/study/flashcards',params={'due_only':'true'}))),1)
        responses=await asyncio.gather(*(self.http.post(url+'/review',json={'quality':5},headers={'Idempotency-Key':'card-review-once'}) for _ in range(8)))
        for response in responses: self.assertEqual(self.ok(response)['interval_days'],1)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(FlashcardReview).where(FlashcardReview.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,5)
        result=self.ok(await self.http.post(url+'/review',json={'quality':5},headers={'Idempotency-Key':'card-review-second'}))
        self.assertEqual(result['interval_days'],6)
        self.assertEqual((await self.http.post(url+'/review',json={'quality':6})).status_code,422)
        self.assertEqual((await self.http.post(url+'/review',json={'quality':2},headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual(self.ok(await self.http.get('/api/study/flashcards',params={'due_only':'true'})),[])
        self.assertIsNotNone(self.ok(await self.http.get('/api/study/flashcards'))[0]['last_review'])
        self.ok(await self.http.delete(url))
        self.assertEqual(self.ok(await self.http.get('/api/study/flashcards')),[])
        self.assertNotIn('flashcard',{i['kind'] for i in self.ok(await self.http.get('/api/study/v2/library'))['items']})

    async def test_review_rollback_and_ai_generation_owner_validation(self):
        card=await self.card()
        with patch('services.study_cards.apply_xp',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError): await self.http.post('/api/study/flashcards/'+card['flashcard_id']+'/review',json={'quality':5})
        self.assertEqual(self.ok(await self.http.get('/api/study/flashcards'))[0]['repetitions'],0)
        body={'note_id':self.note['note_id'],'count':2}
        self.assertEqual((await self.http.post('/api/study/flashcards/generate',json=body,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.llm.assert_not_awaited()
        self.llm.return_value=json.dumps([{'front':'A','back':'B'}]*2)
        self.assertEqual(len(self.ok(await self.http.post('/api/study/flashcards/generate',json=body))['flashcards']),2)

    async def test_quiz_attempt_is_atomic_idempotent_and_validates_answers(self):
        body={'notebook_id':self.nid,'title':'Quiz','questions':[{'question':'Pergunta','options':['A','B'],'correct_answer':'A','explanation':'Explicação'}]}
        quiz=self.ok(await self.http.post('/api/study/quizzes',json=body)); url='/api/study/quizzes/'+quiz['quiz_id']
        self.assertEqual(self.ok(await self.http.get('/api/study/quizzes'))[0]['questions'][0]['question'],'Pergunta')
        answers={'answers':[{'question_idx':0,'selected_answer':'A'}]}
        results=await asyncio.gather(*(self.http.post(url+'/attempt',json=answers,headers={'Idempotency-Key':'quiz-attempt-once'}) for _ in range(6)))
        for r in results: self.assertEqual(self.ok(r)['score'],100)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(ExamAttempt).where(ExamAttempt.user_id==self.uid)),1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,30)
        self.assertEqual((await self.http.post(url+'/attempt',json={'answers':answers['answers']*2})).status_code,422)
        self.assertEqual((await self.http.post(url+'/attempt',json=answers,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.ok(await self.http.delete(url)); self.assertEqual(self.ok(await self.http.get('/api/study/quizzes')),[])

    async def test_quiz_generation_uses_owned_notes_and_rejects_partial_response(self):
        body={'notebook_id':self.nid,'count':2}
        self.assertEqual((await self.http.post('/api/study/quizzes/generate',json=body,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.llm.assert_not_awaited()
        self.llm.return_value=json.dumps([{'question':'Pergunta','options':['A','B'],'correct_answer':'A'}])
        self.assertEqual((await self.http.post('/api/study/quizzes/generate',json=body)).status_code,502)
        self.assertEqual(self.ok(await self.http.get('/api/study/quizzes')),[])
        body['count']=1
        result=self.ok(await self.http.post('/api/study/quizzes/generate',json=body))
        self.assertTrue(result['ai_generated'])
