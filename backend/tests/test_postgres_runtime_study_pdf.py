import os
import json
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.models.studies import StudyNote,Flashcard
from db.models.exams import Exam
from db.models.identity import User
from db.session import unit_of_work
import test_postgres_runtime_study_materials as material_tests

DATA={'review_notes':{'title':'Resumo','summary':'Conteúdo de revisão','key_topics':['Direito']},
    'flashcards':[{'front':'Pergunta?','back':'Resposta','deck_name':'Direito'}],
    'quiz':{'title':'Quiz','questions':[{'question_text':'Qual?','options':['A) Sim','B) Não'],'correct_answer':'A'}]}}


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeStudyPDF(unittest.IsolatedAsyncioTestCase):
    ok=material_tests.RuntimeStudyMaterials.ok
    setup_catalog=material_tests.RuntimeStudyMaterials.setup_catalog
    asyncTearDown=material_tests.RuntimeStudyMaterials.asyncTearDown

    async def asyncSetUp(self):
        await material_tests.RuntimeStudyMaterials.asyncSetUp(self)
        async def account(request): return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        extra=[patch('services.study_pdf_materials.account',account),patch('services.study_material_routes._upload',AsyncMock(return_value=SimpleNamespace(uri='test://file'))),
            patch('services.study_material_routes._part',return_value={'file':'test'})]
        for p in extra: p.start()
        self.patches.extend(extra); self.gemini.return_value=SimpleNamespace(text=json.dumps(DATA))

    async def submit(self,headers=None,extra=None):
        return await self.http.post('/api/study/content/analyze-pdf',headers=headers or {},
            data={'notebook_id':self.book['notebook_id'],'num_flashcards':'1','num_quiz_questions':'1',**(extra or {})},
            files={'file':('material.pdf',b'%PDF material','application/pdf')})

    async def test_all_materials_one_transaction_and_replay(self):
        responses=await asyncio.gather(*(self.submit({'Idempotency-Key':'pdf-material-retry'}) for _ in range(4)))
        results=[self.ok(r) for r in responses]
        self.assertEqual(len({r['note']['note_id'] for r in results}),1)
        self.assertEqual(results[0]['xp_earned'],11)
        self.assertTrue(results[0]['note']['ai_generated']); self.assertEqual(results[0]['flashcards'][0]['source_pdf'],'material.pdf')
        self.assertTrue(results[0]['quiz']['ai_generated'])
        async with unit_of_work() as session:
            for model in (StudyNote,Flashcard,Exam):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,11)

    async def test_foreign_before_ai_and_incomplete_generation_no_partial_rows(self):
        self.assertEqual((await self.submit({'Authorization':'Bearer bob'})).status_code,404); self.gemini.assert_not_awaited()
        self.assertEqual((await self.submit(extra={'num_flashcards':'2'})).status_code,502)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyNote).where(StudyNote.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_failure_after_material_writes_rolls_back_everything(self):
        with patch('services.study_pdf_materials.apply_xp',side_effect=RuntimeError('rollback after rows')):
            with self.assertRaises(RuntimeError): await self.submit({'Idempotency-Key':'pdf-rollback-001'})
        async with unit_of_work() as session:
            for model in (StudyNote,Flashcard,Exam):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)
        self.assertEqual(self.ok(await self.submit({'Idempotency-Key':'pdf-rollback-001'}))['xp_earned'],11)
