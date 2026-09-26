import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from fastapi import APIRouter, Cookie, Request


class HistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_exercise_name_and_literal_regex(self):
        source = Path(__file__).resolve().parents[1] / 'server.py'
        node = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'get_exercise_history')
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[{'exercises_completed': [{'name': 'Supino (barra) inclinado'}, {'name': 'Supino (barra)', 'sets_data': []}]}])
        find = MagicMock(return_value=cursor)
        ns = dict(Request=Request, Optional=Optional, Cookie=Cookie, api_router=APIRouter(),
                  get_current_user=AsyncMock(return_value=SimpleNamespace(user_id='owner')),
                  db=SimpleNamespace(workout_logs=SimpleNamespace(find=find)))
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), ns)
        result = await ns['get_exercise_history'](SimpleNamespace(headers={}), 'Supino (barra)', None)
        self.assertEqual(find.call_args.args[0]['user_id'], 'owner')
        self.assertEqual(find.call_args.args[0]['exercises_completed']['$elemMatch']['name']['$regex'], r'^Supino\ \(barra\)$')
        self.assertEqual(result['history'][0]['exercise_name'], 'Supino (barra)')
