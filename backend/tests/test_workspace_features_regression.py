import asyncio
import sys
import unittest
from collections import defaultdict
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
from fastapi import FastAPI
from pymongo.errors import DuplicateKeyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_planner import build_plan
from edital_sources import source_pages, locate_subject
from study_workspace_routes import workspace_router


class PlannerTests(unittest.TestCase):
    def test_capacity_dates_reviews_and_preserved_completed_history(self):
        completed = [{'entry_id': 'done', 'date': '2026-09-28', 'minutes': 50, 'completed': True}]
        availability = [60, 90, 60, 60, 30, 0, 0]
        result = build_plan('program', [{'notebook_id': 'math', 'name': 'Matemática', 'weight': 3}, {'notebook_id': 'law', 'name': 'Direito', 'weight': 1}], availability, '2026-09-28', '2026-10-30', 50, completed)
        self.assertIn(completed[0], result)
        minutes = defaultdict(int)
        for row in result:
            minutes[row['date']] += row['minutes']
            self.assertLessEqual(row['date'], '2026-10-30')
        for day, total in minutes.items():
            self.assertLessEqual(total, availability[date.fromisoformat(day).weekday()])
        self.assertTrue(any(row.get('kind') == 'Revisão' for row in result))
        self.assertEqual(len({r['entry_id'] for r in result}), len(result))

    def test_zero_availability_never_creates_blocks(self):
        self.assertEqual(build_plan('p', [{'notebook_id': 'n'}], [0] * 7, '2026-01-01', '2026-01-30', 50), [])

    def test_sources_use_real_pages_and_preserve_original_text(self):
        pages = source_pages('[PÁGINA 1]\nRegras gerais\n[PÁGINA 50]\nLÍNGUA PORTUGUESA\nInterpretação de textos')
        evidence = locate_subject('Língua Portuguesa', pages)
        self.assertEqual(evidence[0]['page'], 50)
        self.assertIn('Interpretação', evidence[0]['quote'])
        self.assertEqual(locate_subject('Direito Penal', pages), [])
        self.assertEqual(source_pages('Legacy document without page markers'), [])


class MemoryDrafts:
    def __init__(self): self.rows = {}
    async def find_one(self, query, *args, **kwargs):
        return self.rows.get(query['_id'])
    async def insert_one(self, doc):
        if doc['_id'] in self.rows: raise DuplicateKeyError('duplicate')
        self.rows[doc['_id']] = dict(doc)
    async def find_one_and_update(self, query, update, **kwargs):
        old = self.rows.get(query['_id'])
        if not old or old['revision'] != query['revision']: return None
        old.update(update['$set']); old['revision'] += 1
        return dict(old)


class DraftRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = SimpleNamespace(notebooks=SimpleNamespace(find_one=AsyncMock(return_value={'notebook_id': 'own'})), study_drafts=MemoryDrafts())
        self.app = FastAPI()
        self.app.include_router(workspace_router(self.db, AsyncMock(return_value=SimpleNamespace(user_id='alice')), AsyncMock()))
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')
        self.url = '/study/notebooks/own/draft?topic_key=0_1'

    async def asyncTearDown(self): await self.http.aclose()

    async def test_save_read_retry_and_conflicting_tabs(self):
        first = await self.http.put(self.url, json={'text': 'Minha anotação', 'revision': 0})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual((await self.http.get(self.url)).json()['text'], 'Minha anotação')
        retry = await self.http.put(self.url, json={'text': 'Minha anotação', 'revision': 0})
        self.assertEqual(retry.status_code, 200)
        responses = await asyncio.gather(*(self.http.put(self.url, json={'text': t, 'revision': 1}) for t in ['aba A', 'aba B']))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])

    async def test_owner_and_topic_validation(self):
        self.db.notebooks.find_one.return_value = None
        self.assertEqual((await self.http.get(self.url)).status_code, 404)
        self.assertEqual((await self.http.put(self.url, json={'text': 'x', 'revision': 0})).status_code, 404)
        self.assertEqual((await self.http.get('/study/notebooks/own/draft?topic_key=0.$set')).status_code, 422)

    async def test_dates_are_validated_not_coerced_to_none(self):
        from study_workspace_routes import PlanEntryUpdate
        self.assertEqual(PlanEntryUpdate(date='2026-10-15').date, date(2026, 10, 15))
        with self.assertRaises(ValueError): PlanEntryUpdate(date='2026-02-31')


if __name__ == '__main__': unittest.main()
