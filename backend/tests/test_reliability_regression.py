"""Isolated tests of real task routes and Gemini helpers; no external services."""
import ast
import asyncio
import copy
import logging
import threading
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import httpx
import requests
from fastapi import APIRouter, Cookie, FastAPI, HTTPException, Request

SOURCE = Path(__file__).resolve().parents[1] / "server.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))


def load_functions(names):
    ns = dict(globals())
    ns.update(app=FastAPI(), api_router=APIRouter(prefix="/api"), GEMINI_MODEL="gemini-2.5-flash")
    selected = [n for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name in names]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), ns)
    ns["app"].include_router(ns["api_router"])
    return ns


def matches(row, query):
    return all(row.get(k) in v["$in"] if isinstance(v, dict) and "$in" in v
               else row.get(k) == v for k, v in query.items())


class Collection:
    def __init__(self, rows=()):
        self.rows = copy.deepcopy(list(rows))
        self.find_count = 0

    def find(self, query, projection=None):
        self.find_count += 1
        rows = [copy.deepcopy(r) for r in self.rows if matches(r, query)]
        async def to_list(limit):
            return rows[:limit]
        return SimpleNamespace(to_list=to_list)

    async def find_one(self, query, projection=None):
        return next((copy.deepcopy(r) for r in self.rows if matches(r, query)), None)

    async def insert_one(self, row):
        self.rows.append(copy.deepcopy(row))

    async def update_one(self, query, update):
        for row in self.rows:
            if matches(row, query):
                row.update(update["$set"])
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)


class TaskRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ns = load_functions({"get_tasks", "update_task", "update_task_status"})
        self.db = SimpleNamespace(
            tasks=Collection([{"task_id": "task_1", "user_id": "alice", "title": "Study",
                               "is_template": True, "recurrence": "daily", "xp_reward": 10,
                               "created_at": "2026-09-01T00:00:00+00:00"}]),
            task_instances=Collection(), users=Collection([{"user_id": "alice", "xp": 0}]),
        )
        async def auth(**kwargs):
            return SimpleNamespace(user_id="alice", xp=0, rank="Recruta")
        self.ns.update(db=self.db, get_current_user=auth, calculate_rank=lambda xp: "Recruta")
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.ns["app"]), base_url="https://sirius.test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def listing(self, date="2026-09-14"):
        response = await self.client.get("/api/tasks", params={"date": date})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_in_progress_survives_reload_and_is_per_day(self):
        response = await self.client.patch("/api/tasks/task_1/status",
            json={"status": "in_progress", "date": "2026-09-14"})
        self.assertEqual(response.status_code, 200)
        rows = await self.listing()
        self.assertEqual(rows[0]["status"], "in_progress")
        self.assertFalse(rows[0]["completed"])
        self.assertEqual((await self.listing("2026-09-15"))[0]["status"], "todo")

    async def test_checkbox_and_kanban_remain_consistent(self):
        await self.client.patch("/api/tasks/task_1/status",
            json={"status": "in_progress", "date": "2026-09-14"})
        for completed, expected in ((True, "done"), (False, "todo")):
            response = await self.client.patch("/api/tasks/task_1", params={
                "completed": str(completed).lower(), "date": "2026-09-14"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual((await self.listing())[0]["status"], expected)
            self.assertEqual(self.db.task_instances.rows[0]["status"], expected)

    async def test_legacy_completion_and_stale_status_are_normalized(self):
        for completed, status, expected in (
            (True, None, "done"), (False, None, "todo"), (False, "done", "todo"),
        ):
            self.db.task_instances.rows = [{
                "instance_id": "i", "user_id": "alice", "task_id": "task_1",
                "date": "2026-09-14", "completed": completed, "status": status}]
            self.assertEqual((await self.listing())[0]["status"], expected)

    async def test_foreign_instances_are_not_read_or_updated(self):
        foreign = {"instance_id": "foreign", "user_id": "bob", "task_id": "task_1",
                   "date": "2026-09-14", "completed": True, "status": "done"}
        self.db.task_instances.rows = [copy.deepcopy(foreign)]
        self.assertEqual((await self.listing())[0]["status"], "todo")
        response = await self.client.patch("/api/tasks/task_1/status",
            json={"status": "in_progress", "date": "2026-09-14"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.task_instances.rows[0], foreign)

    async def test_instances_are_loaded_in_one_query(self):
        task = self.db.tasks.rows[0]
        self.db.tasks.rows += [{**task, "task_id": f"task_{i}"} for i in range(2, 101)]
        rows = await self.listing()
        self.assertEqual(len(rows), 100)
        self.assertEqual(self.db.task_instances.find_count, 1)

    async def test_empty_and_recurrence_filtered_results(self):
        response = await self.client.get("/api/tasks", params={
            "date": "2026-09-14", "recurrence": "weekly"})
        self.assertEqual(response.json(), [])
        self.assertEqual(self.db.task_instances.find_count, 0)


class GeminiRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ns = load_functions({"call_llm", "call_gemini", "upload_to_gemini",
                                  "call_gemini_with_pdf"})
        self.ns["get_user_api_key"] = AsyncMock(return_value="test-key")
        self.ns["track_gemini_usage"] = AsyncMock()
        self.post = MagicMock(return_value=self.response())
        self.get = MagicMock()
        self.ns["requests"] = SimpleNamespace(
            post=self.post, get=self.get, exceptions=requests.exceptions)

    def response(self, status=200, text="ok", finish="STOP"):
        return httpx.Response(status, json={"candidates": [{
            "content": {"parts": [{"text": text}]}, "finishReason": finish}]})

    async def test_call_llm_tracks_user_and_preserves_timeout(self):
        self.assertEqual(await self.ns["call_llm"]("hello", user_id="alice", timeout_override=7), "ok")
        self.ns["track_gemini_usage"].assert_awaited_once_with("alice", "gemini-2.5-flash")
        self.assertEqual(self.post.call_args.kwargs["timeout"], 7)

    async def test_blocking_request_does_not_block_event_loop(self):
        released = threading.Event()
        main_thread = threading.get_ident()
        thread_ids = []
        def delayed(*args, **kwargs):
            thread_ids.append(threading.get_ident())
            if not released.wait(1):
                raise RuntimeError("Event loop did not run scheduled callback")
            return self.response()
        self.post.side_effect = delayed
        handle = asyncio.get_running_loop().call_later(0.03, released.set)
        try:
            result = await self.ns["call_gemini"]("hello", "", "test-key")
        finally:
            released.set()
            handle.cancel()
        self.assertEqual(result, ("ok", None))
        self.assertTrue(all(t != main_thread for t in thread_ids))

    async def test_model_fallback_and_schema_retry(self):
        self.post.side_effect = [self.response(400), self.response(429), self.response()]
        result = await self.ns["call_gemini"]("hello", "", "key", user_id="alice",
                                            response_schema={"type": "OBJECT"})
        self.assertEqual(result, ("ok", None))
        calls = self.post.call_args_list
        self.assertIn("generationConfig", calls[0].kwargs["json"])
        self.assertNotIn("generationConfig", calls[1].kwargs["json"])
        self.assertIn("gemini-flash-latest", calls[2].args[0])
        self.ns["track_gemini_usage"].assert_awaited_once_with("alice", "gemini-flash-latest")

    async def test_quota_and_invalid_key_do_not_record_success(self):
        for status, error in ((429, "quota"), (401, "invalid")):
            self.post.side_effect = None
            self.post.return_value = self.response(status)
            self.assertEqual(await self.ns["call_gemini"]("p", "", "key", user_id="alice"),
                             (None, error))
        self.ns["track_gemini_usage"].assert_not_awaited()

    async def test_pdf_timeout_retains_error_classification(self):
        self.post.side_effect = requests.exceptions.Timeout()
        result = await self.ns["call_gemini_with_pdf"](b"pdf", "p", "", "key")
        self.assertEqual(result, (None, "timeout"))
        self.assertEqual(self.post.call_count, 3)

    async def test_pdf_inline_payload_and_usage(self):
        result = await self.ns["call_gemini_with_pdf"](b"pdf", "p", "", "key", user_id="alice")
        self.assertEqual(result, ("ok", None))
        part = self.post.call_args.kwargs["json"]["contents"][0]["parts"][1]
        self.assertEqual(part["inlineData"]["mimeType"], "application/pdf")
        self.ns["track_gemini_usage"].assert_awaited_once_with("alice", "gemini-2.5-flash")

    async def test_upload_preserves_multipart_bytes_and_runs_off_thread(self):
        ids = []
        def upload(*args, **kwargs):
            ids.append(threading.get_ident())
            return httpx.Response(200, json={"file": {
                "uri": "files/test", "name": "files/test", "state": "ACTIVE"}})
        self.post.side_effect = upload
        self.assertEqual(await self.ns["upload_to_gemini"](b"PDF-DATA", "key"), "files/test")
        self.assertIn(b"PDF-DATA", self.post.call_args.kwargs["data"])
        self.assertNotEqual(ids[0], threading.get_ident())

    async def test_gemini_paths_have_no_direct_blocking_http_calls(self):
        names = {"call_gemini", "upload_to_gemini", "call_gemini_with_pdf",
                 "test_gemini_key", "edital_chat"}
        # Include the edital endpoint by its decorator, independent of its function name.
        for node in TREE.body:
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            is_edital = any("edital-chat" in ast.unparse(d) for d in node.decorator_list)
            if node.name not in names and not is_edital:
                continue
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
                    self.assertFalse(
                        isinstance(call.func.value, ast.Name) and call.func.value.id == "requests"
                        and call.func.attr in ("get", "post"),
                        f"Blocking request left in {node.name}")


if __name__ == "__main__":
    unittest.main()
