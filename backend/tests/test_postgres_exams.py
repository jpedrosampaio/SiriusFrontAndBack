import asyncio
import os
import sys
import unittest
from uuid import uuid4
from sqlalchemy import func,select
from db.engine import dispose_engine
from db.session import unit_of_work
from db.models.exams import Exam,ExamQuestion,Question,ExamAttempt
from db.models.studies import QuestionAttempt
from db.repositories.identity import IdentityRepository
from services.exams import submit_exam

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true','Disposable PostgreSQL required')
class PostgresExams(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await dispose_engine()

    async def test_weighted_grading_blank_facts_and_idempotency(self):
        async with unit_of_work() as session:
            uid = (await IdentityRepository(session).create(email=f'{uuid4()}@example.test',name='Exam',password_hash='test-only')).id
            exam = Exam(user_id=uid,title='Exam',kind='simulado',status='ready')
            session.add(exam)
            await session.flush()
            eid = exam.id
            for i,weight in enumerate([1,3]):
                question = Question(user_id=uid,statement=f'Question {i}',question_type='multiple_choice',correct_answer='A',source='manual')
                session.add(question)
                await session.flush()
                session.add(ExamQuestion(user_id=uid,exam_id=eid,question_id=question.id,position=i,weight=weight))
        responses = await asyncio.gather(*(submit_exam(uid,eid,[{'question_idx':0,'selected_answer':'A','confidence':'guess','changed_answer':True,'seconds':30}],120,'submit_exam') for _ in range(5)))
        self.assertEqual(responses[0]['score'],25)
        self.assertEqual(responses[0]['unanswered'],1)
        self.assertEqual(responses[0]['answers'][0]['confidence'],'guess')
        self.assertTrue(responses[0]['answers'][1]['skipped'])
        self.assertEqual(sum(bool(r.get('replayed')) for r in responses),4)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(ExamAttempt).where(ExamAttempt.user_id == uid)),1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.user_id == uid)),2)
            self.assertEqual((await IdentityRepository(session).by_id(uid)).xp,2)
            saved=(await session.scalars(select(QuestionAttempt).where(QuestionAttempt.user_id==uid))).all()
            answered=next(r for r in saved if r.evidence['answered'])
            self.assertEqual(answered.duration_seconds,30);self.assertTrue(answered.evidence['changed_answer'])
