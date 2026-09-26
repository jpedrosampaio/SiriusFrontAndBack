import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gemini_service


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_parts_and_structured_config_use_same_async_transport(self):
        post = AsyncMock(return_value=httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': '{"ok":true}'}]}}]}))
        with patch.object(gemini_service, 'http_client', return_value=SimpleNamespace(post=post)):
            result = await gemini_service.call_gemini('', 'system', 'fake', parts=[{'inlineData': {'mimeType': 'image/png', 'data': 'AA=='}}], config_options={'responseMimeType': 'application/json'})
        self.assertEqual(result[0], '{"ok":true}')
        self.assertEqual(post.call_args.kwargs['json']['contents'][0]['parts'][0]['inlineData']['mimeType'], 'image/png')
        self.assertEqual(post.call_args.kwargs['json']['generationConfig']['responseMimeType'], 'application/json')

    async def test_non_active_upload_is_never_sent_for_generation(self):
        client = SimpleNamespace(post=AsyncMock(return_value=httpx.Response(200, json={'file': {'uri': 'file', 'name': 'files/test', 'state': 'PROCESSING'}})), get=AsyncMock(return_value=httpx.Response(200, json={'state': 'FAILED'})))
        with patch.object(gemini_service, 'http_client', return_value=client), patch.object(gemini_service.asyncio, 'sleep', new=AsyncMock()):
            self.assertIsNone(await gemini_service.upload_to_gemini(b'pdf', 'fake'))

    def test_no_dead_sdk_client_or_blocking_provider_http_remains(self):
        source = Path(__file__).resolve().parents[1].joinpath('server.py').read_text(encoding='utf-8')
        self.assertNotIn('gemini_client', source)
        self.assertNotIn('google.genai', source)
        transport = Path(gemini_service.__file__).read_text(encoding='utf-8')
        self.assertNotIn('requests.post', transport)
