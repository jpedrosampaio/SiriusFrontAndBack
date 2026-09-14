import ast
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock
from fastapi import APIRouter, Cookie, HTTPException, Request


class WorkspaceTests(unittest.IsolatedAsyncioTestCase):
    def route(self, name, db):
        source = Path(__file__).resolve().parents[1] / 'server.py'
        node = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body if getattr(n, 'name', '') == name)
        ns = dict(globals(), api_router=APIRouter(), db=db,
                  get_current_user=AsyncMock(return_value=SimpleNamespace(user_id='owner')),
                  mark_discipline_quality=lambda cargos: None)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), ns)
        return ns[name]

    async def test_saved_analysis_requires_owner_and_excludes_raw_pdf(self):
        lookup = AsyncMock(return_value=None)
        route = self.route('get_edital_analysis', SimpleNamespace(edital_analyses=SimpleNamespace(find_one=lookup)))
        with self.assertRaises(HTTPException) as error:
            await route(SimpleNamespace(headers={}), 'foreign', None)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(lookup.call_args.args, ({'analysis_id': 'foreign', 'user_id': 'owner'}, {'_id': 0, 'pdf_text': 0}))
        lookup.return_value = {'analysis_id': 'own', 'cargos': []}
        self.assertEqual((await route(SimpleNamespace(headers={}), 'own', None))['analysis_id'], 'own')

    async def test_progress_cannot_modify_foreign_notebook(self):
        lookup = AsyncMock(return_value=None)
        route = self.route('update_topic_progress', SimpleNamespace(notebooks=SimpleNamespace(find_one=lookup)))
        with self.assertRaises(HTTPException) as error:
            await route(SimpleNamespace(headers={}), 'foreign', {'topic_key': '0_1', 'status': 'studied', 'checked': True}, None)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(lookup.call_args.args[0], {'notebook_id': 'foreign', 'user_id': 'owner'})

    async def test_progress_rejects_injected_paths_and_non_boolean_flags(self):
        route = self.route('update_topic_progress', SimpleNamespace())
        for body in [{'topic_key': '0.$x'}, {'topic_key': '0', 'status': 'studied.other'}, {'topic_key': '0', 'checked': 'false'}]:
            with self.subTest(body=body), self.assertRaises(HTTPException) as error:
                await route(SimpleNamespace(headers={}), 'own', body, None)
            self.assertEqual(error.exception.status_code, 422)


if __name__ == '__main__':
    unittest.main()
