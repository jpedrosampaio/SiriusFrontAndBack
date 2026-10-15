"""Real HTTP adapters and shared facade; only httpx.MockTransport is used."""
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from types import SimpleNamespace
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.config import MODELS
from ai.types import AIError, AIRequest
from ai.providers.gemini import GeminiProvider
from ai.router import AIRouter
from ai.errors import public_ai_error, safe_ai_message
import gemini_service


class FailureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        gemini_service.configure(None)

    async def test_http_classification_survives_router_facade_without_private_body(self):
        private = 'PRIVATE_PROMPT_KEY_DOCUMENT_SENTINEL'
        for status, body, kind in [(401, {}, 'invalid_key'), (403, {}, 'permission_denied'),
            (400, {'error': {'details': [{'reason':'API_KEY_INVALID'}]}}, 'invalid_key'),
            (400, {}, 'invalid_request'), (404, {}, 'model_unavailable'),
            (429, {'error':{'message':'rate limited'}}, 'rate_limit'),
            (429, {'error':{'message':'quota exceeded'}}, 'quota'), (503, {}, 'unavailable')]:
            with self.subTest(status=status,kind=kind):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status,json={**body,'private':private}))) as client:
                    gemini_service.configure(AIRouter(providers={'gemini':GeminiProvider(client)}))
                    with self.assertLogs(level='INFO') as logs:
                        text, failure = await gemini_service.call_gemini(private,'system',private,task='edital_extract')
                    self.assertIsNone(text); self.assertEqual(failure,kind)
                    self.assertNotIn(private,' '.join(logs.output))
                    error=public_ai_error(kind)
                    self.assertNotIn(private,repr(error.detail)); self.assertEqual(error.detail['code'],'ai_'+kind)
                    self.assertEqual(safe_ai_message(error.detail),error.detail['message'])

    async def test_network_timeout_and_invalid_http_json_are_distinct(self):
        for failure,kind in [(httpx.ConnectError('PRIVATE URL'), 'network_error'),(httpx.ReadTimeout('PRIVATE URL'), 'timeout')]:
            def transport(request): raise failure
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                with self.assertRaises(AIError) as error:
                    await GeminiProvider(client).generate(MODELS['flash'],'synthetic',AIRequest('edital_extract','private'))
                self.assertEqual(error.exception.kind,kind); self.assertNotIn('PRIVATE',str(error.exception))
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,text='not JSON'))) as client:
            with self.assertRaises(AIError) as error:
                await GeminiProvider(client).generate(MODELS['flash'],'synthetic',AIRequest('edital_extract','private'))
            self.assertEqual(error.exception.kind,'malformed_output')

    async def test_finish_reasons_empty_and_malformed_candidates_never_become_results(self):
        for data,kind in [({'candidates':[{'finishReason':'MAX_TOKENS'}]},'output_truncated'),
            ({'promptFeedback':{'blockReason':'SAFETY'}},'blocked_output'), ({},'empty_output'),
            ({'candidates':['private malformed candidate']},'malformed_output')]:
            provider=GeminiProvider(SimpleNamespace(post=AsyncMock(return_value=httpx.Response(200,json=data))))
            with self.assertRaises(AIError) as error:
                await provider.generate(MODELS['flash'],'synthetic',AIRequest('edital_extract','private'))
            self.assertEqual(error.exception.kind,kind)

    async def test_cooldown_retains_cause_and_is_scoped_to_user(self):
        from ai.providers.fake import FakeAIProvider
        provider=FakeAIProvider(AIError('rate_limit'),AIError('rate_limit'),'ok')
        router=AIRouter(providers={'gemini':provider})
        for _ in range(2):
            with self.assertRaises(AIError) as error:
                await router.generate(task='edital_extract',keys={'gemini':'synthetic'},user_id='alice')
            self.assertEqual(error.exception.kind,'rate_limit')
        self.assertEqual(len(provider.calls),2)
        result=await router.generate(task='edital_extract',keys={'gemini':'synthetic'},user_id='bob')
        self.assertEqual(result.text,'ok')

    def test_async_failure_message_rebuilt_from_allowlist(self):
        self.assertIsNone(safe_ai_message({'code':'invented','message':'PRIVATE'}))
        message=safe_ai_message({'code':'ai_timeout','message':'PRIVATE'})
        self.assertIn('tempo',message.lower()); self.assertNotIn('PRIVATE',message)
