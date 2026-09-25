import ast
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, patch

from fastapi import APIRouter, Cookie, HTTPException, Query, Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import study_resources as resources


class PriorityTests(unittest.TestCase):
    def test_normalized_syllabus_keeps_original_progress_keys(self):
        result = resources.normalize_content([None, {'assunto': 'Direito', 'subtopicos': [None, 'Garantias']}], preserve_keys=True)
        self.assertEqual(result, [{'assunto': 'Direito', 'subtopicos': ['Garantias'], 'topic_key': '1', 'subtopic_keys': ['1_1']}])

    def test_deadlines_require_both_a_real_excerpt_and_the_literal_date(self):
        valid = {'label': 'Inscrições', 'data': '20/10/2026', 'fonte': 'Inscrições até 20/10/2026'}
        self.assertEqual(resources.sourced_deadlines([valid, dict(valid, data='21/10/2026'), dict(valid, fonte='invented'), None], 'Inscrições até 20/10/2026'), [valid])
        self.assertEqual(resources.sourced_deadlines(None, ''), [])

    def test_equal_question_counts_are_preserved_and_decimal_weights_rank(self):
        data = resources.prioritize([{'peso': 1, 'num_questoes': 10}, {'peso': 1.5, 'num_questoes': 10}])
        self.assertEqual(data[0]['peso'], 1.5)
        self.assertEqual(data[0]['participacao_estimada'], 60)
        self.assertTrue(all(d['num_questoes'] == 10 for d in data))
        self.assertTrue(data[0]['prioridade_provisoria'])

    def test_missing_questions_use_comparable_weight_only_scores(self):
        data = resources.prioritize([{'peso': 1, 'num_questoes': 30}, {'peso': 3, 'num_questoes': 0}])
        self.assertEqual(data[0]['peso'], 3)
        self.assertEqual(data[0]['participacao_estimada'], 75)

    def test_legacy_content_strings_do_not_crash(self):
        self.assertEqual(resources.normalize_content(['Topic', {'assunto': 'Other', 'subtopicos': 'Subtopic'}]), [
            {'assunto': 'Topic', 'subtopicos': []}, {'assunto': 'Other', 'subtopicos': ['Subtopic']}])

    def test_evidence_requires_matching_pdf_excerpt(self):
        evidence = resources.scoring_evidence({'peso': 1.5, 'peso_fonte': 'Português   1,5', 'num_questoes': 10, 'num_questoes_fonte': 'invented'}, 'Português 1,5')
        self.assertEqual(evidence['peso_status'], 'extraido_com_fonte')
        self.assertEqual(evidence['num_questoes_status'], 'a_conferir')
        self.assertEqual(evidence['num_questoes_fonte'], '')

    def test_non_finite_weights_do_not_break_ranking(self):
        data = resources.prioritize([{'peso': 'nan'}, {'peso': None}, {'peso': -2}])
        self.assertTrue(all(d['prioridade_score'] == 1 for d in data))


class LessonTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        resources._lesson_cache.clear()

    async def test_missing_key_keeps_contextual_search_available(self):
        result = await resources.youtube_lessons('Português interpretação & texto', '')
        self.assertEqual(result['status'], 'not_configured')
        self.assertIn('%26', result['search_url'])
        self.assertEqual(result['videos'], [])

    async def test_youtube_results_are_real_links_and_cached(self):
        get = AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {'items': [
            {'id': {'videoId': 'abcdefghijk'}, 'snippet': {'title': 'A &amp; B', 'channelTitle': 'Canal'}},
            {'id': {'videoId': 'https://evil.example'}, 'snippet': {}},
        ]}))
        with patch.object(resources.httpx, 'AsyncClient') as factory:
            factory.return_value.__aenter__.return_value.get = get
            first = await resources.youtube_lessons('Topic', 'test-secret')
            second = await resources.youtube_lessons('Topic', 'test-secret')
        get.assert_awaited_once()
        self.assertEqual(first, second)
        self.assertEqual(first['videos'][0]['title'], 'A & B')
        self.assertEqual(len(first['videos']), 1)
        self.assertNotIn('test-secret', str(first))

    async def test_provider_failure_does_not_leak_key(self):
        with patch.object(resources.httpx, 'AsyncClient') as factory:
            factory.return_value.__aenter__.return_value.get = AsyncMock(return_value=SimpleNamespace(status_code=403))
            result = await resources.youtube_lessons('Topic', 'test-secret')
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('test-secret', str(result))

    async def test_lessons_require_owned_notebook(self):
        source = ROOT / 'server.py'
        nodes = [n for n in ast.parse(source.read_text(encoding='utf-8')).body if getattr(n, 'name', '') == 'get_study_lessons']
        lookup = AsyncMock(return_value=None)
        ns = dict(globals(), api_router=APIRouter(), db=SimpleNamespace(notebooks=SimpleNamespace(find_one=lookup)), get_current_user=AsyncMock(return_value=SimpleNamespace(user_id='owner')))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), ns)
        with self.assertRaises(HTTPException) as error:
            await ns['get_study_lessons'](SimpleNamespace(headers={}), 'foreign', 'Topic', None)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(lookup.call_args.args[0], {'notebook_id': 'foreign', 'user_id': 'owner'})


if __name__ == '__main__':
    unittest.main()
