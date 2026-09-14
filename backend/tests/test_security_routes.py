"""Regression tests for security-sensitive routes, without live MongoDB/Telegram.

Load the real selected definitions from server.py via AST: importing the monolithic
module would initialize production integrations. Requests still pass through FastAPI
and Pydantic, while database and outbound HTTP operations are explicit test doubles.
"""
import ast
import json
import logging
import os
import secrets
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Literal, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import APIRouter, Cookie, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

SOURCE = Path(__file__).resolve().parents[1] / "server.py"


def load_routes():
    names = {
        "Task", "Habit", "Transaction", "Goal", "SyncPayload", "get_sync_config",
        "sync_table", "get_sync_data", "setup_telegram_webhook", "telegram_webhook",
        "trigger_daily_summaries", "startup_setup",
    }
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    selected = [
        node for node in tree.body
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name in names)
        or (isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "SYNC_TABLES" for t in node.targets))
    ]
    namespace = dict(globals())
    namespace.update(app=FastAPI(), api_router=APIRouter(prefix="/api"),
                     TELEGRAM_BOT_TOKEN="test-bot-token",
                     TELEGRAM_BOT_WEBHOOK_SECRET="a" * 32,
                     telegram_bot=object())
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), namespace)
    namespace["app"].include_router(namespace["api_router"])
    return namespace


class SecurityRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ns = load_routes()
        self.collection = MagicMock()
        self.collection.find_one = AsyncMock(return_value=None)
        self.collection.update_one = AsyncMock()
        self.collection.delete_one = AsyncMock()
        self.collection.find.return_value.to_list = AsyncMock(return_value=[])
        self.db = MagicMock()
        self.db.__getitem__.return_value = self.collection
        self.db.telegram_links = self.collection
        self.ns["db"] = self.db
        self.ns["send_telegram_daily_summary"] = AsyncMock()

        async def auth(authorization=None, session_token=None):
            if authorization != "Bearer alice":
                raise HTTPException(status_code=401, detail="Not authenticated")
            return SimpleNamespace(user_id="alice")

        self.ns["get_current_user"] = auth
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.ns["app"]),
            base_url="https://sirius.test",
            headers={"Authorization": "Bearer alice"},
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    def payload(self, operation="INSERT", data=None, record_id="task_1"):
        return {"record_id": record_id, "operation": operation,
                "data": data if data is not None else {
                    "task_id": record_id, "title": "Study", "date": "2026-09-14",
                    "user_id": "alice",
                }, "timestamp": "2026-09-14T10:00:00+00:00"}

    async def test_sync_requires_authentication(self):
        self.client.headers.pop("Authorization")
        response = await self.client.post("/api/sync/tasks", json=self.payload())
        self.assertEqual(response.status_code, 401)
        self.db.__getitem__.assert_not_called()

    async def test_internal_collections_are_not_readable_or_writable(self):
        for table in ("users", "user_sessions", "telegram_links", "unknown"):
            for method, url, kwargs in (
                ("get", f"/api/sync/{table}/alice", {}),
                ("post", f"/api/sync/{table}", {"json": self.payload()}),
            ):
                with self.subTest(table=table, method=method):
                    response = await self.client.request(method, url, **kwargs)
                    self.assertEqual(response.status_code, 403)
        self.db.__getitem__.assert_not_called()

    async def test_cannot_read_another_user(self):
        response = await self.client.get("/api/sync/tasks/bob")
        self.assertEqual(response.status_code, 403)
        self.db.__getitem__.assert_not_called()

    async def test_read_is_scoped_and_projects_only_public_fields(self):
        response = await self.client.get("/api/sync/tasks/alice")
        self.assertEqual(response.status_code, 200)
        selector, projection = self.collection.find.call_args.args
        self.assertEqual(selector, {"user_id": "alice"})
        self.assertEqual(projection["task_id"], 1)
        self.assertNotIn("password", projection)
        self.assertNotIn("gemini_api_key", projection)

    async def test_cannot_forge_owner_or_record_id(self):
        for data in ({"user_id": "bob"}, {"task_id": "task_other"}):
            response = await self.client.post("/api/sync/tasks", json=self.payload(data=data))
            self.assertIn(response.status_code, (403, 422))
        self.collection.update_one.assert_not_awaited()

    async def test_invalid_operations_identifiers_and_fields_are_rejected(self):
        samples = [
            self.payload(operation="UPSERT"),
            self.payload(record_id=""),
            self.payload(record_id="$where"),
            self.payload(data={"password": "injected"}),
            self.payload(data={"$set": {"user_id": "bob"}}),
            self.payload(data={"title": {"$ne": None}}),
        ]
        for payload in samples:
            with self.subTest(payload=payload):
                response = await self.client.post("/api/sync/tasks", json=payload)
                self.assertEqual(response.status_code, 422)
        self.collection.update_one.assert_not_awaited()

    async def test_insert_forces_owner_identifier_and_reward(self):
        payload = self.payload()
        payload["data"].pop("user_id")
        payload["data"]["xp_reward"] = 999999
        response = await self.client.post("/api/sync/tasks", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        selector, update = self.collection.update_one.call_args.args
        self.assertEqual(selector, {"task_id": "task_1", "user_id": "alice"})
        self.assertEqual(update["$set"]["user_id"], "alice")
        self.assertEqual(update["$set"]["task_id"], "task_1")
        self.assertEqual(update["$set"]["xp_reward"], 10)

    async def test_existing_other_owner_id_is_not_overwritten(self):
        self.collection.find_one.side_effect = [None, {"task_id": "task_1"}]
        response = await self.client.post("/api/sync/tasks", json=self.payload())
        self.assertEqual(response.status_code, 409)
        self.collection.update_one.assert_not_awaited()

    async def test_update_missing_or_other_owner_record_does_not_upsert(self):
        response = await self.client.post(
            "/api/sync/tasks", json=self.payload(operation="UPDATE", data={"completed": 1}))
        self.assertEqual(response.status_code, 404)
        self.collection.find_one.assert_awaited_once_with(
            {"task_id": "task_1", "user_id": "alice"}, {"_id": 0})
        self.collection.update_one.assert_not_awaited()

    async def test_partial_update_preserves_existing_data_and_reward(self):
        self.collection.find_one.return_value = {
            "task_id": "task_1", "user_id": "alice", "title": "Existing",
            "date": "2026-09-14", "created_at": "2026-09-01T00:00:00Z",
            "xp_reward": 12,
        }
        response = await self.client.post("/api/sync/tasks", json=self.payload(
            operation="UPDATE", data={"completed": 1, "xp_reward": 9000}))
        self.assertEqual(response.status_code, 200, response.text)
        args, kwargs = self.collection.update_one.call_args
        self.assertEqual(args[0], {"task_id": "task_1", "user_id": "alice"})
        self.assertEqual(args[1]["$set"]["title"], "Existing")
        self.assertEqual(args[1]["$set"]["xp_reward"], 12)
        self.assertIs(args[1]["$set"]["completed"], True)
        self.assertFalse(kwargs["upsert"])

    async def test_delete_is_scoped_and_idempotent(self):
        for _ in range(2):
            response = await self.client.post("/api/sync/tasks",
                json=self.payload(operation="DELETE", data={}))
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.collection.delete_one.await_count, 2)
        self.collection.delete_one.assert_awaited_with(
            {"task_id": "task_1", "user_id": "alice"})

    async def test_mobile_json_arrays_are_normalized(self):
        payload = self.payload(record_id="habit_1", data={
            "name": "Read", "color": "#ffffff", "completions": '["2026-09-14"]'})
        response = await self.client.post("/api/sync/habits", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.collection.update_one.call_args.args[1]["$set"]["completions"],
                         ["2026-09-14"])
        self.collection.update_one.reset_mock()
        payload["data"]["completions"] = "invalid JSON"
        response = await self.client.post("/api/sync/habits", json=payload)
        self.assertEqual(response.status_code, 422)
        self.collection.update_one.assert_not_awaited()

    async def test_profile_cannot_reconfigure_global_webhook(self):
        with patch.object(httpx, "AsyncClient") as outbound:
            response = await self.client.post("/api/telegram/setup-webhook",
                json={"backend_url": "https://attacker.invalid"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("test-bot-token", response.text)
        outbound.assert_not_called()

    async def test_webhook_requires_dedicated_secret(self):
        for secret in ("", "wrong", "test-bot-token"):
            response = await self.client.post("/api/telegram/webhook", json={},
                headers={"X-Telegram-Bot-Api-Secret-Token": secret})
            self.assertEqual(response.status_code, 403)
        response = await self.client.post("/api/telegram/webhook", json={},
            headers={"X-Telegram-Bot-Api-Secret-Token": "a" * 32})
        self.assertEqual(response.status_code, 200)
        legacy = await self.client.post("/api/telegram/webhook/test-bot-token", json={})
        self.assertEqual(legacy.status_code, 404)

    async def test_disabled_webhook_fails_closed(self):
        self.ns["TELEGRAM_BOT_WEBHOOK_SECRET"] = ""
        response = await self.client.post("/api/telegram/webhook", json={})
        self.assertEqual(response.status_code, 503)

    async def test_summaries_only_target_authenticated_user(self):
        self.collection.find.return_value.to_list.return_value = [
            {"user_id": "alice", "chat_id": 123}]
        response = await self.client.post("/api/telegram/send-daily-summaries")
        self.assertEqual(response.status_code, 200)
        self.collection.find.assert_called_once_with({"status": "active", "user_id": "alice"})
        self.ns["send_telegram_daily_summary"].assert_awaited_once_with("alice", 123)

    async def test_startup_rejects_untrusted_or_missing_configuration(self):
        for url in ("", "http://insecure.invalid", "https://user:pass@example.com",
                    "https://example.com?redirect=evil", "https://example.com#evil"):
            with self.subTest(url=url), patch.dict(os.environ, {
                "BACKEND_PUBLIC_URL": url, "CORS_ORIGINS": "https://attacker.invalid"
            }), patch.object(httpx, "AsyncClient") as outbound:
                await self.ns["startup_setup"]()
                outbound.assert_not_called()
        self.ns["TELEGRAM_BOT_WEBHOOK_SECRET"] = ""
        with patch.dict(os.environ, {"BACKEND_PUBLIC_URL": "https://backend.test"}), \
             patch.object(httpx, "AsyncClient") as outbound:
            await self.ns["startup_setup"]()
            outbound.assert_not_called()

    async def test_startup_uses_fixed_path_and_secret_without_logging_token(self):
        outbound = AsyncMock()
        outbound.post.return_value = httpx.Response(200, json={"ok": True})
        factory = MagicMock()
        factory.return_value.__aenter__.return_value = outbound
        with patch.dict(os.environ, {"BACKEND_PUBLIC_URL": "https://backend.test/"}), \
             patch.object(httpx, "AsyncClient", factory), self.assertLogs(level="INFO") as logs:
            await self.ns["startup_setup"]()
        payload = outbound.post.call_args.kwargs["json"]
        self.assertEqual(payload["url"], "https://backend.test/api/telegram/webhook")
        self.assertEqual(payload["secret_token"], "a" * 32)
        self.assertNotIn("test-bot-token", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
