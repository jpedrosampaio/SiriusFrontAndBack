"""Real workout schema and transport, synthetic responses only."""
import ast
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock
from unittest.mock import patch
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ai.config import MODELS, Settings
from jsonschema import Draft202012Validator
from ai.providers.gemini import GeminiProvider
from ai.providers.groq import GroqProvider
from ai.router import AIRouter
from ai.types import AIError, AIResult
from workout_generation_contract import BasePlan
from workout_generation_fixtures import bases


class StructuredWorkout(unittest.IsolatedAsyncioTestCase):
    async def test_shared_bridge_passes_contract_only_when_requested(self):
        tree = ast.parse((ROOT / 'server.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if getattr(n, 'name', '') == 'call_llm')
        generate = AsyncMock(return_value=AIResult(text='{}', model='synthetic'))
        namespace = {'Optional': Optional, 'agent_runtime': SimpleNamespace(
            credentials=SimpleNamespace(get=AsyncMock(return_value={'groq':'synthetic'})),
            router=SimpleNamespace(generate=generate)), 'track_gemini_usage': AsyncMock()}
        exec(compile(ast.Module(body=[node],type_ignores=[]), 'call_llm', 'exec'), namespace)
        await namespace['call_llm']('synthetic', user_id='test', task='workout_generation', output_type=BasePlan, strict_schema=True)
        self.assertIs(generate.call_args.kwargs['output_type'], BasePlan)
        self.assertTrue(generate.call_args.kwargs['strict_schema'])
        await namespace['call_llm']('synthetic', user_id='test')
        self.assertNotIn('output_type', generate.call_args.kwargs)
        self.assertNotIn('strict_schema', generate.call_args.kwargs)

    async def test_real_workout_schema_reaches_both_providers_and_rejects_missing_exercise_data(self):
        for provider, model in (('gemini', MODELS['flash']), ('groq', MODELS['reasoning'])):
            for valid in (True, False):
                with self.subTest(provider=provider, valid=valid):
                    payload = BasePlan.model_validate(bases()).model_dump(mode='json')
                    if not valid: del payload['base_sessions'][0]['exercises'][0]['required_equipment']
                    sent=[]
                    def respond(request):
                        sent.append(json.loads(request.content))
                        content=json.dumps(payload)
                        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':content}]}}]} if provider=='gemini' else {'choices':[{'message':{'content':content}}]})
                    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                        router=AIRouter(settings=SimpleNamespace(route=lambda task:[model]),
                            providers={provider: GeminiProvider(client) if provider=='gemini' else GroqProvider(client)})
                        args=dict(task='workout_generation',keys={provider:'synthetic'},prompt='synthetic',output_type=BasePlan,strict_schema=True)
                        if valid:
                            result=await router.generate(**args)
                            self.assertEqual(len(result.data.base_sessions),3)
                        else:
                            with self.assertRaises(AIError) as failure: await router.generate(**args)
                            self.assertEqual(failure.exception.kind,'malformed_output')
                    self.assertEqual(len(sent),1)
                    wire = sent[0]['generationConfig']['responseFormat']['text']['schema'] if provider=='gemini' else sent[0]['response_format']['json_schema']['schema']
                    self.assertIn('base_sessions',wire['properties'])
                    if provider == 'groq':
                        self.assertTrue(sent[0]['response_format']['json_schema']['strict'])
                        for obj in [wire, *wire['$defs'].values()]:
                            if obj.get('type') == 'object':
                                self.assertFalse(obj['additionalProperties'])
                                self.assertEqual(set(obj['required']), set(obj['properties']))

    async def test_default_route_prefers_free_groq_but_preserves_gemini_only_accounts(self):
        with patch.dict('os.environ', {}, clear=True):
            settings = Settings()
            self.assertFalse(settings.paid)
            self.assertEqual([m.name for m in settings.route('workout_generation')][:2],
                ['openai/gpt-oss-120b', 'openai/gpt-oss-20b'])
            providers = {name: SimpleNamespace(generate_structured=AsyncMock(return_value=AIResult(
                text=BasePlan.model_validate(bases()).model_dump_json()))) for name in ('groq','gemini')}
            router = AIRouter(settings=settings, providers=providers)
            await router.generate(task='workout_generation', keys={'gemini':'synthetic'},
                output_type=BasePlan, strict_schema=True)
            providers['groq'].generate_structured.assert_not_awaited()
            providers['gemini'].generate_structured.assert_awaited_once()

    async def test_groq_output_failure_returns_to_bounded_caller_without_hidden_fallback(self):
        sent=[]
        def respond(request):
            sent.append(json.loads(request.content))
            return httpx.Response(400,json={'error':{'code':'json_validate_failed',
                'message':'private generated text must not be logged', 'failed_generation':'PRIVATE'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['reasoning'],MODELS['fast']]),
                providers={'groq':GroqProvider(client)})
            for _ in range(2):
                with self.assertRaises(AIError) as failure:
                    await router.generate(task='workout_generation',keys={'groq':'synthetic'},
                        output_type=BasePlan,strict_schema=True)
                self.assertEqual(failure.exception.kind,'malformed_output')
            self.assertEqual(len(sent),2)
            self.assertFalse(router.rejections)

    async def test_strict_transport_keeps_original_limits_and_rejects_extra_fields(self):
        from ai.schemas import transport_schema
        wire=transport_schema(BasePlan.model_json_schema(),'groq_json_v2',strict=True)
        valid=BasePlan.model_validate(bases()).model_dump(mode='json')
        Draft202012Validator(wire).validate(valid)
        for field, value in [('sets',9),('required_equipment',['invented']),('untrusted_field','x')]:
            invalid=json.loads(json.dumps(valid))
            invalid['base_sessions'][0]['exercises'][0][field]=value
            self.assertFalse(Draft202012Validator(wire).is_valid(invalid))
            with self.assertRaises(ValueError): BasePlan.model_validate(invalid)
