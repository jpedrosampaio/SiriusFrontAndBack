"""Real route tests on disposable MongoDB: transaction isolation and replay recovery."""
import ast
import asyncio
import hashlib
import json
import logging
import os
import unittest
import uuid
import sys
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import AsyncMock

import httpx
from fastapi import APIRouter, Cookie, FastAPI, HTTPException, Request
from pymongo import ReturnDocument
from pymongo.errors import OperationFailure, CollectionInvalid
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

SOURCE = Path(__file__).resolve().parents[1] / "server.py"
sys.path.insert(0, str(SOURCE.parent))
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))


def load_routes(client, db):
    ns = dict(globals(), client=client, db=db, api_router=APIRouter(prefix="/api"))
    names = {"setup_activity_collections", "validate_activity_date", "run_activity_mutation", "set_task_completion",
             "update_task", "update_task_status", "get_tasks", "complete_habit",
             "FocusSessionCreate", "complete_focus_session", "update_study_streak", "start_workout_session", "update_session_exercise", "complete_workout_session", "abandon_workout_session", "calculate_rank", "award_xp", "calculate_streak", "calculate_best_streak"}
    selected = [node for node in TREE.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), ns)
    async def auth(authorization=None, **kwargs):
        # Deliberately stale XP in auth: the transaction must use the database.
        return SimpleNamespace(user_id="bob" if authorization == "Bearer bob" else "alice",
                               xp=0, rank="Recruta")
    ns["get_current_user"] = auth
    app = FastAPI()
    app.include_router(ns["api_router"])
    return ns, app


class ActivityValidationTests(unittest.TestCase):
    def test_only_calendar_dates_are_accepted(self):
        ns, _ = load_routes(None, None)
        self.assertEqual(ns["validate_activity_date"]("2024-02-29"), "2024-02-29")
        for value in ("2026-02-29", "2026-9-14", "2026-09-14T00:00:00", None, 123):
            with self.subTest(value=value), self.assertRaises(HTTPException):
                ns["validate_activity_date"](value)


@unittest.skipUnless(os.environ.get("ACTIVITY_TEST_MONGO_URI"), "replica set not configured")
class ActivityTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        self.mongo = AsyncIOMotorClient(os.environ["ACTIVITY_TEST_MONGO_URI"],
                                       serverSelectionTimeoutMS=5000)
        self.db = self.mongo["sirius_activity_test_" + uuid.uuid4().hex]
        await self.db.users.insert_many([
            {"user_id": "alice", "xp": 0, "rank": "Recruta"},
            {"user_id": "bob", "xp": 500, "rank": "Cabo"}])
        await self.db.tasks.insert_one({
            "user_id": "alice", "task_id": "task_1", "xp_reward": 10,
            "is_template": True, "recurrence": "daily",
            "created_at": "2026-09-01T00:00:00+00:00"})
        await self.db.habits.insert_one({
            "user_id": "alice", "habit_id": "habit_1", "completions": [],
            "streak": 0, "best_streak": 0})
        self.ns, app = load_routes(self.mongo, self.db)
        await self.ns["setup_activity_collections"]()
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="https://sirius.test")

    async def asyncTearDown(self):
        await self.http.aclose()
        await self.mongo.drop_database(self.db.name)
        self.mongo.close()

    async def task(self, completed=True, key=None, date="2026-09-14", headers=None):
        headers = dict(headers or {})
        if key:
            headers["Idempotency-Key"] = key
        return await self.http.patch("/api/tasks/task_1",
            params={"completed": str(completed).lower(), "date": date}, headers=headers)

    async def habit(self, completed=True, key=None, date="2026-09-14", headers=None):
        headers = dict(headers or {})
        if key:
            headers["Idempotency-Key"] = key
        params = {"date": date}
        if completed is not None:
            params["completed"] = str(completed).lower()
        return await self.http.post("/api/habits/habit_1/complete", params=params, headers=headers)

    async def balance(self, expected, user_id="alice"):
        row = await self.db.users.find_one({"user_id": user_id})
        self.assertEqual(row["xp"], expected)
        self.assertEqual(row["rank"], self.ns["calculate_rank"](expected))

    def successes(self, responses):
        for response in responses:
            self.assertEqual(response.status_code, 200, response.text)



    async def test_workout_start_and_completion_serialize_and_replay(self):
        await self.db.workout_plans.insert_one({'plan_id': 'plan', 'user_id': 'alice', 'name': 'Plan', 'exercises': [{'name': 'Exercise', 'sets': 3, 'reps': 12}]})
        starts = await asyncio.gather(*(self.http.post('/api/workout-sessions/start', json={'plan_id': 'plan'}) for _ in range(8)))
        self.assertEqual(sum(r.status_code == 200 for r in starts), 1)
        self.assertTrue(all(r.status_code in (200, 409) for r in starts))
        session_id = next(r.json()['session_id'] for r in starts if r.status_code == 200)
        path = f'/api/workout-sessions/{session_id}'
        changes = await asyncio.gather(*(self.http.patch(path + '/exercise/0', json={'sets_data': [{'weight': str(weight), 'completed': True}], 'revision': 0}) for weight in (10, 12)))
        self.assertEqual(sorted(r.status_code for r in changes), [200, 409])
        completed = await asyncio.gather(*(self.http.post(path + '/complete', json={'difficulty': 3}) for _ in range(10)))
        self.successes(completed)
        self.assertEqual(await self.db.workout_logs.count_documents({}), 1)
        await self.balance(completed[0].json()['xp_earned'])

    async def test_collection_setup_is_safe_for_concurrent_worker_startup(self):
        await asyncio.gather(*(self.ns["setup_activity_collections"]() for _ in range(4)))
        names = await self.db.list_collection_names()
        self.assertIn("task_instances", names)
        self.assertIn("activity_requests", names)

    async def test_dashboard_counts_full_history_and_keeps_owners_separate(self):
        from dashboard_service import dashboard_snapshot
        await self.db.transactions.insert_many([{'user_id': 'alice', 'date': '2026-09-14', 'type': 'income', 'amount': 1} for _ in range(1005)])
        await self.db.transactions.insert_one({'user_id': 'bob', 'date': '2026-09-14', 'type': 'income', 'amount': 9999})
        await self.db.focus_sessions.insert_one({'user_id': 'alice', 'date': '2026-09-14', 'focus_minutes': 25, 'completed': True})
        result = await dashboard_snapshot(self.db, SimpleNamespace(user_id='alice', name='Alice', xp=0, rank='Recruta', picture=None), '2026-09-14')
        self.assertEqual(result['income'], 1005)
        self.assertEqual(result['study_stats']['study_time_today_minutes'], 25)






















if __name__ == "__main__":
    unittest.main()
