"""Real workout schema and transport, synthetic responses only."""
import ast
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ai.config import MODELS
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
        await namespace['call_llm']('synthetic', user_id='test', task='workout_generation', output_type=BasePlan)
        self.assertIs(generate.call_args.kwargs['output_type'], BasePlan)
        await namespace['call_llm']('synthetic', user_id='test')
        self.assertNotIn('output_type', generate.call_args.kwargs)

    async def test_real_workout_schema_reaches_both_providers_and_rejects_missing_exercise_data(self):
        for provider, model in (('gemini', MODELS['flash']), ('groq', MODELS['reasoning'])):
            for valid in (True, False):
                with self.subTest(provider=provider, valid=valid):
                    payload = bases()
                    if not valid: del payload['base_sessions'][0]['exercises'][0]['required_equipment']
                    sent=[]
                    def respond(request):
                        sent.append(json.loads(request.content))
                        content=json.dumps(payload)
                        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':content}]}}]} if provider=='gemini' else {'choices':[{'message':{'content':content}}]})
                    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                        router=AIRouter(settings=SimpleNamespace(route=lambda task:[model]),
                            providers={provider: GeminiProvider(client) if provider=='gemini' else GroqProvider(client)})
                        args=dict(task='workout_generation',keys={provider:'synthetic'},prompt='synthetic',output_type=BasePlan)
                        if valid:
                            result=await router.generate(**args)
                            self.assertEqual(len(result.data.base_sessions),3)
                        else:
                            with self.assertRaises(AIError) as failure: await router.generate(**args)
                            self.assertEqual(failure.exception.kind,'malformed_output')
                    self.assertEqual(len(sent),1)
                    wire = sent[0]['generationConfig']['responseFormat']['text']['schema'] if provider=='gemini' else sent[0]['response_format']['json_schema']['schema']
                    self.assertIn('base_sessions',wire['properties'])
