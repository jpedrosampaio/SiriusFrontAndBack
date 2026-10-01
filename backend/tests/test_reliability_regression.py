"""Isolated tests of real task routes and Gemini helpers; no external services."""
import ast
import asyncio
import copy
import logging
import threading
import unittest
import uuid
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import httpx
import requests
from fastapi import APIRouter, Cookie, FastAPI, HTTPException, Request

SOURCE = Path(__file__).resolve().parents[1] / "server.py"
sys.path.insert(0, str(SOURCE.parent))
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

    def find(self, query, projection=None, **kwargs):
        self.find_count += 1
        rows = [copy.deepcopy(r) for r in self.rows if matches(r, query)]
        async def to_list(limit):
            return rows[:limit]
        return SimpleNamespace(to_list=to_list)

    async def find_one(self, query, projection=None, **kwargs):
        return next((copy.deepcopy(r) for r in self.rows if matches(r, query)), None)

    async def insert_one(self, row, **kwargs):
        self.rows.append(copy.deepcopy(row))

    async def update_one(self, query, update, **kwargs):
        for row in self.rows:
            if matches(row, query):
                row.update(update["$set"])
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    async def update_many(self, query, update, **kwargs):
        for row in self.rows:
            if matches(row, query):
                row.update(update["$set"])




class GeminiRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ns = load_functions({"call_llm", "call_gemini", "upload_to_gemini",
                                  "call_gemini_with_pdf"})
        self.ns["get_user_api_key"] = AsyncMock(return_value="test-key")
        self.ns["track_gemini_usage"] = AsyncMock()
        self.post = AsyncMock(return_value=self.response())
        self.get = AsyncMock()
        from unittest.mock import patch
        import gemini_service
        transport = SimpleNamespace(post=self.post, get=self.get)
        from ai.router import AIRouter
        from ai.providers.gemini import GeminiProvider
        self.ns['agent_runtime'] = SimpleNamespace(credentials=SimpleNamespace(get=AsyncMock(return_value={'gemini': 'test-key'})), router=AIRouter(providers={'gemini': GeminiProvider(transport)}))
        patcher = patch.object(gemini_service, 'http_client', return_value=transport)
        patcher.start()
        self.addCleanup(patcher.stop)

    def response(self, status=200, text="ok", finish="STOP"):
        return httpx.Response(status, json={"candidates": [{
            "content": {"parts": [{"text": text}]}, "finishReason": finish}]})

    async def test_call_llm_tracks_user_and_preserves_timeout(self):
        self.assertEqual(await self.ns["call_llm"]("hello", user_id="alice", timeout_override=7), "ok")
        self.ns["track_gemini_usage"].assert_awaited_once_with("alice", "gemini-3.8-flash", usage={}, feature='assistant_chat')
        self.assertEqual(self.post.call_args.kwargs["timeout"], 7)

    async def test_native_async_transport_yields_to_event_loop(self):
        released = asyncio.Event()
        async def delayed(*args, **kwargs):
            await asyncio.wait_for(released.wait(), 1)
            return self.response()
        self.post.side_effect = delayed
        handle = asyncio.get_running_loop().call_later(0.03, released.set)
        try:
            result = await self.ns["call_gemini"]("hello", "", "test-key")
        finally:
            handle.cancel()
        self.assertEqual(result, ("ok", None))

    async def test_model_fallback_and_schema_retry(self):
        self.post.side_effect = [self.response(429), self.response(text='{"ok":true}')]
        result = await self.ns["call_gemini"]("hello", "", "key", user_id="alice",
                                            response_schema={"type": "OBJECT"})
        self.assertEqual(result, ('{"ok":true}', None))
        calls = self.post.call_args_list
        self.assertIn("generationConfig", calls[0].kwargs["json"])
        self.assertIn("responseJsonSchema", calls[1].kwargs["json"]["generationConfig"])
        self.assertIn("gemini-3.5-flash-lite", calls[1].args[0])
        self.ns["track_gemini_usage"].assert_awaited_once_with("alice", "gemini-3.5-flash-lite", usage={}, feature='edital_extract')

    async def test_quota_and_invalid_key_do_not_record_success(self):
        for status, error in ((429, "quota"), (401, "invalid")):
            self.post.side_effect = None
            self.post.return_value = self.response(status)
            self.assertEqual(await self.ns["call_gemini"]("p", "", "key", user_id="alice"),
                             (None, error))
        self.ns["track_gemini_usage"].assert_not_awaited()

    async def test_pdf_timeout_retains_error_classification(self):
        self.post.side_effect = httpx.ReadTimeout("simulated timeout")
        result = await self.ns["call_gemini_with_pdf"](b"pdf", "p", "", "key")
        self.assertEqual(result, (None, "timeout"))
        self.assertEqual(self.post.call_count, 2)

    async def test_pdf_inline_payload_and_usage(self):
        result = await self.ns["call_gemini_with_pdf"](b"pdf", "p", "", "key", user_id="alice")
        self.assertEqual(result, ("ok", None))
        part = self.post.call_args.kwargs["json"]["contents"][0]["parts"][0]
        self.assertEqual(part["inlineData"]["mimeType"], "application/pdf")
        self.ns["track_gemini_usage"].assert_awaited_once_with("alice", "gemini-3.8-flash", usage={}, feature="edital_extract")

    async def test_upload_preserves_multipart_bytes_through_async_transport(self):
        ids = []
        async def upload(*args, **kwargs):
            ids.append(threading.get_ident())
            return httpx.Response(200, json={"file": {
                "uri": "files/test", "name": "files/test", "state": "ACTIVE"}})
        self.post.side_effect = upload
        self.assertEqual(await self.ns["upload_to_gemini"](b"PDF-DATA", "key"), "files/test")
        self.assertIn(b"PDF-DATA", self.post.call_args.kwargs["content"])
        self.post.assert_awaited_once()

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
