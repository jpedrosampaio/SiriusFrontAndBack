import ast
import json
import logging
import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock
from fastapi import APIRouter, Cookie, HTTPException, Request
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TopicExamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = ROOT / 'server.py'
        names = {'SimuladoCreate', 'generate_simulado'}
        nodes = [n for n in ast.parse(source.read_text(encoding='utf-8')).body if getattr(n, 'name', '') in names]
        self.db = SimpleNamespace(study_programs=SimpleNamespace(find_one=AsyncMock(return_value={'program_id': 'p'})), notebooks=SimpleNamespace(find_one=AsyncMock(return_value={'program_id': 'p', 'name': 'Português', 'conteudo_programatico': [{'assunto': 'Crase'}]})), simulados=SimpleNamespace(insert_one=AsyncMock()))
        self.generate = AsyncMock(return_value=SimpleNamespace(text=json.dumps({'questions': [{'question_text': 'Questão', 'correct_answer': 'A'}]})))
        self.ns = dict(globals(), api_router=APIRouter(), db=self.db, get_current_user=AsyncMock(return_value=SimpleNamespace(user_id='alice')), get_user_api_key=AsyncMock(return_value='fake'), request_gemini=self.generate, award_xp=AsyncMock())
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), self.ns)

    async def test_topic_is_resolved_from_owned_syllabus_and_linked(self):
        data = self.ns['SimuladoCreate'](title='Teste', program_id='p', notebook_id='nb', topic_key='0', num_questions=1, topic='untrusted topic')
        result = await self.ns['generate_simulado'](SimpleNamespace(headers={}), data, None)
        question = result['simulado']['questions'][0]
        self.assertEqual(question['subdisciplina'], 'Crase')
        self.assertEqual(question['topic_key'], '0')
        self.assertEqual(question['notebook_id'], 'nb')
        self.assertIn('Crase', self.generate.call_args.kwargs['config']['system_instruction'])
        self.assertEqual(question['provenance'], 'inferred')

    async def test_foreign_preparation_never_calls_ai(self):
        self.db.study_programs.find_one.return_value = None
        with self.assertRaises(HTTPException) as error:
            await self.ns['generate_simulado'](SimpleNamespace(headers={}), self.ns['SimuladoCreate'](title='Teste', program_id='foreign'), None)
        self.assertEqual(error.exception.status_code, 404)
        self.generate.assert_not_awaited()

    async def test_wrong_question_count_is_not_saved(self):
        with self.assertRaises(HTTPException) as error:
            await self.ns['generate_simulado'](SimpleNamespace(headers={}), self.ns['SimuladoCreate'](title='Teste', num_questions=4), None)
        self.assertEqual(error.exception.status_code, 502)
        self.db.simulados.insert_one.assert_not_awaited()
