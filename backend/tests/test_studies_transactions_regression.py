import os
import sys
import uuid
import unittest
import asyncio
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
import httpx
from test_activity_regression import load_routes
from studies_v2 import studies_v2_router
from simulado_scoring import submit_exam, grade
from study_blueprint import blueprint, assemble


class ExamTests(unittest.TestCase):
    def test_duplicate_answers_rejected_and_blank_not_full_score(self):
        questions = [{'correct_answer': 'A', 'weight': 2}, {'correct_answer': 'B', 'weight': 1}]
        from fastapi import HTTPException
        with self.assertRaises(HTTPException): grade(questions, [{'question_idx': 0, 'selected_answer': 'A'}] * 2)
        result = grade(questions, [{'question_idx': 0, 'selected_answer': 'A'}])
        self.assertEqual(result['score'], 66.7)
        self.assertEqual(result['accuracy'], 50)
        self.assertEqual(result['unanswered'], 1)
        self.assertEqual(result['correct_count'], 1)

    def test_blueprint_exact_counts_and_missing_questions_explained(self):
        from fastapi import HTTPException
        plan = blueprint([{'notebook_id': 'n', 'name': 'Português', 'num_questoes_edital': 2, 'weight': 3}])
        exams = [{'simulado_id': 's', 'questions': [{'question_text': str(i), 'disciplina': 'Português', 'correct_answer': 'A'} for i in range(3)]}]
        result = assemble(plan['distribution'], exams, 'stable')
        self.assertEqual(len(result), 2)
        self.assertTrue(all(q['weight'] == 3 for q in result))
        self.assertEqual(result, assemble(plan['distribution'], exams, 'stable'))
        with self.assertRaises(HTTPException): assemble(plan['distribution'], [], 's')
        self.assertFalse(blueprint([{'notebook_id': 'n', 'name': 'Português'}])['complete'])


@unittest.skipUnless(os.environ.get('ACTIVITY_TEST_MONGO_URI'), 'replica set not configured')
class StudyTransactions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        self.mongo = AsyncIOMotorClient(os.environ['ACTIVITY_TEST_MONGO_URI'], serverSelectionTimeoutMS=5000)
        self.db = self.mongo['sirius_studies2_test_' + uuid.uuid4().hex]
        await self.db.users.insert_many([{'user_id': 'alice', 'xp': 0, 'rank': 'Recruta'}, {'user_id': 'bob', 'xp': 0, 'rank': 'Recruta'}])
        self.ns, _ = load_routes(self.mongo, self.db)
        await self.ns['setup_activity_collections']()
        await self.db.notebooks.insert_one({'user_id': 'alice', 'notebook_id': 'nb', 'program_id': 'p', 'conteudo_programatico': [{'assunto': 'Crase', 'subtopicos': []}]})
        await self.db.study_programs.insert_one({'user_id': 'alice', 'program_id': 'p', 'name': 'Preparação'})
        app = FastAPI()
        app.include_router(studies_v2_router(self.db, self.ns['get_current_user'], self.ns['run_activity_mutation']), prefix='/api')
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://sirius.test')

    async def asyncTearDown(self):
        await self.http.aclose()
        await self.mongo.drop_database(self.db.name)
        self.mongo.close()

    async def test_attempt_concurrent_replay_counts_once_and_owner_isolation(self):
        body = {'notebook_id': 'nb', 'topic_key': '0', 'question': 'Questão', 'correct': False, 'error_reason': 'forgot'}
        responses = await asyncio.gather(*(self.http.post('/api/study/v2/attempts', json=body, headers={'Idempotency-Key': 'attempt-once'}) for _ in range(8)))
        for response in responses: self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(await self.db.study_attempts.count_documents({}), 1)
        self.assertEqual(await self.db.question_logs.count_documents({}), 1)
        self.assertEqual((await self.db.notebooks.find_one({'notebook_id': 'nb'}))['total_questions'], 1)
        foreign = await self.http.post('/api/study/v2/attempts', json=body, headers={'Authorization': 'Bearer bob', 'Idempotency-Key': 'foreign-owner-attempt'})
        self.assertEqual(foreign.status_code, 404, foreign.text)
        self.assertEqual(await self.db.study_attempts.count_documents({}), 1)
        self.assertEqual((await self.http.get('/api/study/v2/performance', headers={'Authorization': 'Bearer bob'})).json()['summary']['samples'], 0)

    async def test_target_creation_replay_does_not_duplicate_program(self):
        body = {'name': 'Certificação X', 'kind': 'certification'}
        for _ in range(2):
            result = await self.http.post('/api/study/v2/targets', json=body, headers={'Idempotency-Key': 'target-once'})
            self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(await self.db.study_targets.count_documents({}), 1)
        self.assertEqual(await self.db.study_programs.count_documents({}), 2)

    async def test_simulado_replay_commits_one_grade_xp_and_evidence(self):
        await self.db.simulados.insert_one({'user_id': 'alice', 'simulado_id': 'sim', 'program_id': 'p', 'questions': [{'question_text': 'Crase?', 'correct_answer': 'A', 'notebook_id': 'nb', 'topic_key': '0', 'disciplina': 'Português'}]})
        payload = {'answers': [{'question_idx': 0, 'selected_answer': 'A'}], 'time_spent_seconds': 30}
        submission = SimpleNamespace(**payload, model_dump=lambda: payload)
        request = SimpleNamespace(headers={'Idempotency-Key': 'sim-once'})
        async def submit():
            return await submit_exam(self.db, 'alice', 'sim', submission, request, self.ns['run_activity_mutation'], self.ns['award_xp'], self.ns['update_study_streak'])
        results = await asyncio.gather(*(submit() for _ in range(6)))
        self.assertTrue(all(r['score'] == 100 for r in results))
        self.assertEqual(await self.db.simulado_attempts.count_documents({}), 1)
        self.assertEqual(await self.db.study_attempts.count_documents({}), 1)
        self.assertEqual(await self.db.question_logs.count_documents({}), 1)
        self.assertEqual((await self.db.users.find_one({'user_id': 'alice'}))['xp'], 2)


if __name__ == '__main__': unittest.main()
