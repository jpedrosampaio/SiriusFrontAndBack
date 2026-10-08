import asyncio
import os
import unittest
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, func
from db.session import unit_of_work
from db.models.studies import StudyTopic, StudySession, QuestionAttempt, ReviewEvent
from db.models.agent import Message
from db.models.identity import User
from services.retrieval import Retrieval
import test_postgres_runtime_catalog as fixtures


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class Tutor(unittest.IsolatedAsyncioTestCase):
    ok = fixtures.RuntimeCatalog.ok
    setup_catalog = fixtures.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await fixtures.RuntimeCatalog.asyncSetUp(self)
        _, program, book = await self.setup_catalog()
        self.pid, self.nid = program['program_id'], book['notebook_id']
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid, json={'conteudo_programatico': [{'assunto': 'Crase'}]}))
        async with unit_of_work() as session:
            self.topic = await session.scalar(select(StudyTopic.id).where(StudyTopic.user_id == self.uid, StudyTopic.notebook_id == UUID(self.nid)))
        async def account(request):
            return {'user_id': str(self.bob if request.headers.get('Authorization') == 'Bearer bob' else self.uid), 'timezone': 'America/Sao_Paulo'}
        self.provider = AsyncMock(return_value='Pergunta estimada: explique a crase. [S1]')
        self.patches = [patch('services.study_tutor.account', account), patch('services.study_activity_routes.account', account), patch('services.study_tutor._llm', self.provider)]
        for p in self.patches: p.start()
        self.scope = {'preparation_id': self.pid, 'notebook_id': self.nid, 'topic_key': '0'}
        self.turn = {**self.scope, 'mode': 'socratic', 'conversation_id': str(uuid4()), 'request_id': 'tutor-request-01', 'message': 'Explique crase'}

    async def asyncTearDown(self):
        for p in reversed(self.patches): p.stop()
        await fixtures.RuntimeCatalog.asyncTearDown(self)

    async def attach(self, title='Material', text='Crase: fusão de duas vogais. Conhecimento do usuário.'):
        import hashlib
        return await Retrieval().attach(str(self.uid), hashlib.sha256((title+text).encode()).hexdigest(), title+'.pdf',
            'application/pdf', 100, [{'page': 2, 'text': text}], 'extracted')

    async def test_turn_replay_scope_history_and_no_estimated_mastery(self):
        result = self.ok(await self.http.post('/api/study/tutor/turn', json=self.turn))
        replay = self.ok(await self.http.post('/api/study/tutor/turn', json=self.turn))
        self.assertEqual(result, replay); self.assertEqual(self.provider.await_count, 1)
        self.assertEqual(result['ai_message']['tutor']['knowledge_basis'], 'general_model_knowledge_and_sirius_facts')
        self.assertEqual(result['ai_message']['citations'], [])
        history = self.ok(await self.http.get('/api/study/tutor/history', params={k:v for k,v in self.turn.items() if k not in ('message','request_id')}))
        self.assertEqual(len(history['messages']), 2)
        changed = {**self.turn, 'message': 'Different question'}
        self.assertEqual((await self.http.post('/api/study/tutor/turn', json=changed)).status_code, 409)
        foreign = {'Authorization': 'Bearer bob'}
        self.assertEqual((await self.http.post('/api/study/tutor/turn', json=self.turn, headers=foreign)).status_code, 404)
        self.assertEqual((await self.http.get('/api/study/tutor/materials', params=self.scope, headers=foreign)).status_code, 404)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.user_id == self.uid)), 0)
            self.assertEqual((await session.get(User, self.uid)).xp, 0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(Message).where(Message.user_id == self.uid)), 2)

    async def test_material_binding_grounding_ownership_and_archive(self):
        first = await self.attach(); unrelated = await self.attach('Other', 'Crase: outro material não vinculado.')
        url = '/api/study/tutor/materials/'+first['attachment_id']+'/link'
        headers = {'Idempotency-Key': 'bind-material-01'}
        self.ok(await self.http.post(url, json=self.scope, headers=headers))
        self.assertTrue(self.ok(await self.http.post(url, json=self.scope, headers=headers))['replayed'])
        self.assertEqual((await self.http.post(url, json=self.scope, headers={'Authorization':'Bearer bob','Idempotency-Key':'foreign-bind'})).status_code, 404)
        listed = self.ok(await self.http.get('/api/study/tutor/materials', params=self.scope))
        self.assertEqual([f['attachment_id'] for f in listed['materials']], [first['attachment_id']])
        result = self.ok(await self.http.post('/api/study/tutor/turn', json=self.turn))
        citations = result['ai_message']['citations']
        self.assertTrue(citations); self.assertEqual({c['source_id'] for c in citations}, {first['attachment_id']})
        self.assertTrue(all(c['category'] == 'user_material' for c in citations))
        self.assertNotIn(unrelated['attachment_id'], str(citations))
        self.assertIn('uma pergunta', self.provider.call_args.kwargs['system_message'])
        self.ok(await self.http.delete('/api/study/notebooks/'+self.nid))
        self.assertEqual((await self.http.get('/api/study/tutor/materials', params=self.scope)).status_code, 404)
        self.assertEqual((await self.http.post('/api/study/tutor/turn', json={**self.turn,'request_id':'archived-turn'})).status_code, 404)

    async def test_concurrent_retries_use_one_provider_and_one_exchange(self):
        original = self.provider.side_effect
        async def delayed(*args, **kwargs):
            await asyncio.sleep(.1); return 'Uma pergunta de recall.'
        self.provider.side_effect = delayed
        responses = await asyncio.gather(*(self.http.post('/api/study/tutor/turn', json=self.turn) for _ in range(4)))
        self.assertIn(200, [r.status_code for r in responses]); self.assertTrue(all(r.status_code in (200,409) for r in responses))
        self.assertEqual(self.provider.await_count, 1)
        self.ok(await self.http.post('/api/study/tutor/turn', json=self.turn)); self.assertEqual(self.provider.await_count, 1)
        self.provider.side_effect = original

    async def test_copilot_counts_only_recorded_window_and_excludes_blanks(self):
        now = datetime.now(timezone.utc); since = now-timedelta(minutes=10)
        async with unit_of_work() as session:
            session.add(StudySession(user_id=self.uid, notebook_id=UUID(self.nid), date=now.date(), duration_minutes=25,
                completed=True, source='focus', created_at=now, notes='Recorded focus'))
            session.add(QuestionAttempt(user_id=self.uid, notebook_id=UUID(self.nid), topic_id=self.topic,
                total=4, correct=3, source='manual', answered_at=now, evidence={}))
            session.add(QuestionAttempt(user_id=self.uid, notebook_id=UUID(self.nid), topic_id=self.topic,
                total=1, correct=0, source='simulado', answered_at=now, evidence={'answered':False}))
            session.add(ReviewEvent(user_id=self.uid, topic_id=self.topic, reviewed_at=now, result='manual'))
            session.add(ReviewEvent(user_id=self.uid, topic_id=self.topic, reviewed_at=now, result='manual'))
        r = self.ok(await self.http.get('/api/study/tutor/copilot', params={**self.scope,'since':since.isoformat()}))
        self.assertEqual((r['recorded_minutes'],r['answered'],r['accuracy'],r['reviewed_topics']), (25,4,75,1))
        self.assertTrue(r['proposal_only']); self.assertEqual(self.provider.await_count,0)
        self.assertEqual((await self.http.get('/api/study/tutor/copilot', params={**self.scope,'since':(now-timedelta(days=2)).isoformat()})).status_code,422)
