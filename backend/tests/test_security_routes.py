"""Regression tests for security-sensitive routes, without live Telegram.

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
        "setup_telegram_webhook", "telegram_webhook",
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
