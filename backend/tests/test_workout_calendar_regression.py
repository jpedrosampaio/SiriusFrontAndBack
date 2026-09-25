import ast
import json
import logging
import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

from fastapi import APIRouter, Cookie, HTTPException, Request
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workout_calendar import calendar_shape, validate_ai_calendar

TREE = ast.parse((ROOT / 'server.py').read_text(encoding='utf-8'))
NODES = [n for n in TREE.body if getattr(n, 'name', '') in ('WorkoutPlanGenerate', 'generate_workout_plan', 'improve_workout_plan', 'start_workout_session', '_strip_json_fences')]


def route_context():
    ns = dict(globals(), api_router=APIRouter())
    exec(compile(ast.Module(body=NODES, type_ignores=[]), str(ROOT / 'server.py'), 'exec'), ns)
    ns['get_current_user'] = AsyncMock(return_value=SimpleNamespace(user_id='user1'))
    ns['db'] = SimpleNamespace(workout_plans=SimpleNamespace(insert_one=AsyncMock()))
    async def mutate(user, key, fingerprint, apply):
        return await apply(None, {})
    ns['run_activity_mutation'] = mutate
    ns['award_xp'] = AsyncMock(return_value=(5, 'E'))
    return ns


def period(count=20):
    return {'days': [{'exercises': [{'name': 'Exercise'}]} for _ in range(count)]}


class CalendarTests(unittest.IsolatedAsyncioTestCase):
    async def generate(self, responses, **kwargs):
        self.ns = route_context()
        self.ns['call_llm'] = AsyncMock(side_effect=[json.dumps(r) for r in responses])
        request = self.ns['WorkoutPlanGenerate'](objective='hipertrofia', level='intermediario', duration='mes', **kwargs)
        return await self.ns['generate_workout_plan'](SimpleNamespace(headers={}), request, None)

    async def test_four_weeks_month(self):
        result = await self.generate([period()])
        plan = result['plan']
        self.assertEqual(len(plan['days']), 20)
        self.assertEqual(plan['cycle_weeks'], 4)
        self.assertEqual(plan['days'][5]['week'], 2)
        self.assertEqual(plan['days'][5]['day_name'], 'sem2_dia1')

    async def test_partial_response_retried_before_save(self):
        result = await self.generate([period(10), period()])
        self.assertEqual(len(result['plan']['days']), 20)
        self.assertEqual(self.ns['call_llm'].await_count, 2)
        self.ns['db'].workout_plans.insert_one.assert_awaited_once()

    async def test_repeated_partial_response_never_saved_or_rewarded(self):
        with self.assertRaises(HTTPException) as error:
            await self.generate([period(10), period(10)])
        self.assertEqual(error.exception.status_code, 502)
        self.ns['db'].workout_plans.insert_one.assert_not_awaited()
        self.ns['award_xp'].assert_not_awaited()

    async def test_splits_expanded_exactly(self):
        data = {'splits': [{'split_label': 'A', 'exercises': [{'name': 'Exercise'}]}]}
        result = await self.generate([data], generation_mode='tipo_treino', split_config=[{'label': 'A'}], cycle_weeks=4, training_days_per_week=3)
        self.assertEqual(len(result['plan']['days']), 12)
        self.assertEqual(result['plan']['days'][-1]['week'], 4)
        self.assertIsNot(result['plan']['days'][0]['exercises'], result['plan']['days'][1]['exercises'])

    async def test_missing_splits_not_silently_replaced_by_partial_days(self):
        with self.assertRaises(HTTPException):
            await self.generate([period(10), period(10)], generation_mode='tipo_treino', split_config=[{'label': 'A'}])
        self.ns['db'].workout_plans.insert_one.assert_not_awaited()

    async def test_conflicting_week_rejected(self):
        data = period()
        data['days'][5]['day_label'] = 'Semana 3 - Dia 1'
        with self.assertRaises(HTTPException):
            await self.generate([data, data])
        self.ns['db'].workout_plans.insert_one.assert_not_awaited()

    async def test_running_frequency_and_stale_split_mode(self):
        result = await self.generate([period(12)], workout_type='corrida', weekly_frequency=3, generation_mode='tipo_treino')
        self.assertEqual(result['plan']['training_days_per_week'], 3)
        self.assertEqual(result['plan']['generation_mode'], 'periodo')

    def test_request_bounds(self):
        model = route_context()['WorkoutPlanGenerate']
        for args in ({'cycle_weeks': 0}, {'cycle_weeks': 13}, {'training_days_per_week': 8}, {'weekly_frequency': 1}):
            with self.assertRaises(ValueError):
                model(objective='hipertrofia', level='iniciante', **args)

    async def test_improve_uses_user_llm_and_preserves_four_weeks(self):
        ns = route_context()
        plan = {'name': 'Plan', 'plan_duration': 'mes', 'generation_mode': 'periodo', 'days': period()['days']}
        ns['db'].workout_plans.find_one = AsyncMock(return_value=plan)
        ns['db'].workout_sessions = SimpleNamespace(find=lambda *args: SimpleNamespace(to_list=AsyncMock(return_value=[])))
        ns['db'].daily_workout_status = ns['db'].workout_sessions
        ns['call_llm'] = AsyncMock(side_effect=[json.dumps(period(10)), json.dumps(period())])
        result = await ns['improve_workout_plan'](SimpleNamespace(headers={}), 'original', None)
        self.assertEqual(len(result['plan']['days']), 20)
        self.assertEqual(result['plan']['cycle_weeks'], 4)
        self.assertEqual(ns['call_llm'].call_args.kwargs['user_id'], 'user1')
        self.assertEqual(ns['call_llm'].await_count, 2)

    async def test_invalid_start_day_never_falls_back_to_whole_plan(self):
        for index in (-1, 20, '2', True):
            ns = route_context()
            ns['db'].workout_sessions = SimpleNamespace(find_one=AsyncMock(return_value=None), insert_one=AsyncMock())
            ns['db'].workout_plans.find_one = AsyncMock(return_value=period())
            request = SimpleNamespace(headers={}, json=AsyncMock(return_value={'plan_id': 'plan', 'day_index': index}))
            with self.assertRaises(HTTPException) as error:
                await ns['start_workout_session'](request, None)
            self.assertEqual(error.exception.status_code, 422)
            ns['db'].workout_sessions.insert_one.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
