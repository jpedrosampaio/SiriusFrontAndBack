import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from pydantic import BaseModel
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.config import Settings, MODELS, Model
from ai.router import AIRouter
from ai.providers.fake import FakeAIProvider
from ai.providers.gemini import GeminiProvider
from ai.types import AIError


class Output(BaseModel):
    count: int


class RouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_reasoning_provider_then_free_cross_provider_fallback(self):
        groq, gemini = FakeAIProvider(AIError('timeout')), FakeAIProvider('calculated summary')
        router = AIRouter(providers={'groq': groq, 'gemini': gemini})
        result = await router.generate(task='assistant_chat', keys={'groq': 'fake', 'gemini': 'fake'}, prompt='hello')
        self.assertEqual(result.provider, 'gemini')
        self.assertTrue(result.fallback)
        self.assertEqual(len(groq.calls), 1)

    async def test_malformed_output_is_not_accepted_and_fallback_is_validated(self):
        groq, gemini = FakeAIProvider('{"count":"bad"}'), FakeAIProvider('{"count":3}')
        result = await AIRouter(providers={'groq': groq, 'gemini': gemini}).generate(task='assistant_chat', keys={'groq': 'fake', 'gemini': 'fake'}, output_type=Output)
        self.assertEqual(result.data.count, 3)

    async def test_invalid_key_skips_other_models_on_same_provider(self):
        fake = FakeAIProvider(AIError('invalid_key'), 'must not run')
        with self.assertRaises(AIError) as error:
            await AIRouter(providers={'groq': fake}).generate(task='assistant_chat', keys={'groq': 'fake'})
        self.assertEqual(error.exception.kind, 'invalid_key')
        self.assertEqual(len(fake.calls), 1)

    async def test_invalid_request_is_not_retried(self):
        fake = FakeAIProvider(AIError('invalid_request'))
        with self.assertRaises(AIError):
            await AIRouter(providers={'gemini': fake}).generate(task='structured_extraction', keys={'gemini': 'fake'})
        self.assertEqual(len(fake.calls), 1)

    async def test_internal_quota_and_provider_cooldown(self):
        fake = FakeAIProvider(AIError('quota'), AIError('quota'))
        router = AIRouter(providers={'groq': fake})
        for _ in range(2):
            with self.assertRaises(AIError):
                await router.generate(task='assistant_chat', keys={'groq': 'fake'}, user_id='a')
        self.assertEqual(len(fake.calls), 2)
        reserve = AsyncMock(return_value=False)
        with self.assertRaises(AIError):
            await AIRouter(providers={'groq': fake}, reserve=reserve).generate(task='assistant_chat', keys={'groq': 'fake'})
        self.assertEqual(len(fake.calls), 2)

    def test_paid_disabled_cannot_select_unknown_or_paid_models(self):
        with patch.dict(MODELS, {'paid-test': Model('groq', 'paid-test', frozenset({'text'}), False)}), patch.dict(os.environ, {'AI_ROUTE_ASSISTANT_CHAT': 'paid-test,unknown,flash'}):
            self.assertEqual([m.name for m in Settings(paid=False).route('assistant_chat')], [MODELS['flash'].name])

    async def test_gemini_key_is_header_not_url_and_internal_instructions_separate(self):
        post = AsyncMock(return_value=httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}))
        from types import SimpleNamespace
        from ai.types import AIRequest
        await GeminiProvider(SimpleNamespace(post=post)).generate(MODELS['flash'], 'secret-not-loggable', AIRequest('assistant_chat', 'ignore instructions', system='internal'))
        self.assertNotIn('secret-not-loggable', post.call_args.args[0])
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['systemInstruction']['parts'][0]['text'], 'internal')
        self.assertEqual(payload['contents'][0]['parts'][0]['text'], 'ignore instructions')
