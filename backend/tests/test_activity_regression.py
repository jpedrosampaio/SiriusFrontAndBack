"""Real route tests on disposable MongoDB: transaction isolation and replay recovery."""
import ast
import asyncio
import hashlib
import json
import logging
import os
import unittest
import uuid
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
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))


def load_routes(client, db):
    ns = dict(globals(), client=client, db=db, api_router=APIRouter(prefix="/api"))
    names = {"setup_activity_collections", "validate_activity_date", "run_activity_mutation", "set_task_completion",
             "update_task", "update_task_status", "get_tasks", "complete_habit",
             "calculate_rank", "award_xp", "calculate_streak", "calculate_best_streak"}
    selected = [node for node in TREE.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
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

    async def test_collection_setup_is_safe_for_concurrent_worker_startup(self):
        await asyncio.gather(*(self.ns["setup_activity_collections"]() for _ in range(4)))
        names = await self.db.list_collection_names()
        self.assertIn("task_instances", names)
        self.assertIn("activity_requests", names)

    async def test_repeated_task_completion_and_undo_each_apply_once(self):
        results = await asyncio.gather(*(self.task() for _ in range(20)))
        self.successes(results)
        self.assertEqual(sum(r.json()["xp_earned"] for r in results), 10)
        await self.balance(10)
        self.assertEqual(await self.db.task_instances.count_documents({}), 1)
        results = await asyncio.gather(*(self.task(False) for _ in range(20)))
        self.successes(results)
        self.assertEqual(sum(r.json()["xp_earned"] for r in results), -10)
        await self.balance(0)

    async def test_checkbox_and_kanban_share_one_completion(self):
        results = await asyncio.gather(
            self.task(),
            self.http.patch("/api/tasks/task_1/status",
                json={"status": "done", "date": "2026-09-14"}))
        self.successes(results)
        await self.balance(10)
        response = await self.http.patch("/api/tasks/task_1/status",
            json={"status": "in_progress", "date": "2026-09-14"})
        self.successes([response])
        await self.balance(0)
        rows = (await self.http.get("/api/tasks", params={"date": "2026-09-14"})).json()
        self.assertEqual((rows[0]["status"], rows[0]["completed"]), ("in_progress", False))

    async def test_repeated_habit_completion_and_undo_each_apply_once(self):
        results = await asyncio.gather(*(self.habit() for _ in range(20)))
        self.successes(results)
        self.assertEqual(sum(r.json()["xp_earned"] for r in results), 8)
        await self.balance(8)
        results = await asyncio.gather(*(self.habit(False) for _ in range(20)))
        self.successes(results)
        await self.balance(0)
        habit = await self.db.habits.find_one({"habit_id": "habit_1"})
        self.assertEqual(habit["completions"], [])

    async def test_concurrent_opposite_states_leave_matching_xp(self):
        results = await asyncio.gather(*(self.task(completed) for completed in [True, False] * 10))
        self.successes(results)
        row = await self.db.task_instances.find_one({})
        await self.balance(10 if row["completed"] else 0)

    async def test_distinct_habit_dates_preserve_all_completions_and_streak(self):
        dates = [f"2026-09-{day:02}" for day in range(1, 11)]
        self.successes(await asyncio.gather(*(self.habit(date=date) for date in dates)))
        habit = await self.db.habits.find_one({"habit_id": "habit_1"})
        self.assertEqual(habit["completions"], dates)
        self.assertEqual(habit["best_streak"], 10)
        await self.balance(80)

    async def test_independent_task_dates_receive_independent_rewards(self):
        self.successes(await asyncio.gather(self.task(date="2026-09-14"),
                                            self.task(date="2026-09-15")))
        await self.balance(20)
        self.assertEqual(await self.db.task_instances.count_documents({}), 2)

    async def test_task_habit_and_other_xp_writers_coexist(self):
        results = await asyncio.gather(self.task(), self.habit(),
            *(self.ns["award_xp"]("alice", 2) for _ in range(10)))
        self.successes(results[:2])
        await self.balance(38)

    async def test_same_key_replays_one_committed_result_after_lost_response(self):
        results = await asyncio.gather(*(self.task(key="same-request-001") for _ in range(12)))
        self.successes(results)
        self.assertEqual(sum(not r.json().get("replayed", False) for r in results), 1)
        await self.balance(10)
        self.assertEqual(await self.db.activity_requests.count_documents({}), 1)

    async def test_old_request_replay_after_undo_does_not_complete_again(self):
        self.successes([await self.task(key="original-request")])
        self.successes([await self.task(False, key="undo-request-001")])
        replay = await self.task(key="original-request")
        self.assertTrue(replay.json()["replayed"])
        await self.balance(0)
        self.assertFalse((await self.db.task_instances.find_one({}))["completed"])

    async def test_key_cannot_be_reused_with_another_payload_or_route(self):
        self.successes([await self.task(key="original-request")])
        for response in (await self.task(False, key="original-request"),
                         await self.habit(key="original-request")):
            self.assertEqual(response.status_code, 409)
        await self.balance(10)

    async def test_user_ownership_and_request_key_scoping(self):
        foreign = await self.task(headers={"Authorization": "Bearer bob"})
        self.assertEqual(foreign.status_code, 404)
        foreign = await self.habit(headers={"Authorization": "Bearer bob"})
        self.assertEqual(foreign.status_code, 404)
        await self.db.tasks.insert_one({
            "user_id": "bob", "task_id": "task_1", "xp_reward": 10})
        self.successes(await asyncio.gather(
            self.task(key="shared-key-001"),
            self.task(key="shared-key-001", headers={"Authorization": "Bearer bob"})))
        await self.balance(10)
        await self.balance(510, "bob")

    async def test_task_failure_rolls_back_state_xp_and_receipt_then_retry_succeeds(self):
        real_award = self.ns["award_xp"]
        async def fail_after_award(*args, **kwargs):
            await real_award(*args, **kwargs)
            raise HTTPException(status_code=503, detail="Injected failure")
        self.ns["award_xp"] = fail_after_award
        response = await self.task(key="rollback-request")
        self.assertEqual(response.status_code, 503)
        await self.balance(0)
        self.assertEqual(await self.db.task_instances.count_documents({}), 0)
        self.assertEqual(await self.db.activity_requests.count_documents({}), 0)
        self.ns["award_xp"] = real_award
        self.successes([await self.task(key="rollback-request")])
        await self.balance(10)

    async def test_habit_failure_rolls_back_state_xp_and_receipt(self):
        real_award = self.ns["award_xp"]
        async def fail_after_award(*args, **kwargs):
            await real_award(*args, **kwargs)
            raise HTTPException(status_code=503, detail="Injected failure")
        self.ns["award_xp"] = fail_after_award
        response = await self.habit(key="rollback-request")
        self.assertEqual(response.status_code, 503)
        await self.balance(0)
        self.assertEqual((await self.db.habits.find_one({}))["completions"], [])
        self.assertEqual(await self.db.activity_requests.count_documents({}), 0)

    async def test_legacy_duplicates_do_not_create_another_reward(self):
        await self.db.users.update_one({"user_id": "alice"}, {"$set": {"xp": 10}})
        await self.db.task_instances.insert_many([
            {"user_id": "alice", "task_id": "task_1", "instance_id": "old-1",
             "date": "2026-09-14", "completed": True},
            {"user_id": "alice", "task_id": "task_1", "instance_id": "old-2",
             "date": "2026-09-14", "completed": False}])
        rows = (await self.http.get("/api/tasks", params={"date": "2026-09-14"})).json()
        self.assertTrue(rows[0]["completed"])
        self.successes([await self.task()])
        await self.balance(10)
        self.successes([await self.task(False)])
        await self.balance(0)
        self.assertEqual(await self.db.task_instances.count_documents({"completed": True}), 0)

    async def test_legacy_toggle_requires_key_and_replay_is_safe(self):
        self.assertEqual((await self.habit(None)).status_code, 428)
        self.successes([await self.habit(None, key="legacy-toggle-001")])
        replay = await self.habit(None, key="legacy-toggle-001")
        self.assertTrue(replay.json()["replayed"])
        await self.balance(8)

    async def test_invalid_inputs_do_not_write(self):
        for response in (await self.task(date="2026-02-30"),
                         await self.habit(date="not-a-date"),
                         await self.task(key="short"),
                         await self.http.patch("/api/tasks/task_1/status", json=[])):
            self.assertIn(response.status_code, (400, 422))
        await self.balance(0)
        self.assertEqual(await self.db.task_instances.count_documents({}), 0)


@unittest.skipUnless(os.environ.get("XP_TEST_MONGO_URI"), "standalone MongoDB not configured")
class StandaloneActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_unsupported_transactions_fail_without_partial_updates(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo = AsyncIOMotorClient(os.environ["XP_TEST_MONGO_URI"])
        db = mongo["sirius_standalone_test_" + uuid.uuid4().hex]
        try:
            await db.users.insert_one({"user_id": "alice", "xp": 0})
            ns, app = load_routes(mongo, db)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                        base_url="https://sirius.test") as http:
                response = await http.patch("/api/tasks/task_1",
                    params={"completed": "true", "date": "2026-09-14"})
                self.assertEqual(response.status_code, 503)
            self.assertEqual((await db.users.find_one({}))["xp"], 0)
            self.assertEqual(await db.task_instances.count_documents({}), 0)
        finally:
            await mongo.drop_database(db.name)
            mongo.close()


if __name__ == "__main__":
    unittest.main()
