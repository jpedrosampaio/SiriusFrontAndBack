"""Local response rejection diagnostics over real contracts and mocked HTTP only."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
from pydantic import BaseModel, model_validator, ValidationError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.router import AIRouter
from ai.config import MODELS
from ai.providers.gemini import GeminiProvider
from ai.providers.groq import GroqProvider
from ai.types import AIError
from ai.validation_diagnostics import safe_validation, location_path, pydantic_failure
from edital_pipeline_contracts import InventoryUnit, ScopeUnit, DetailUnit, VerificationUnit

PRIVATE = 'PRIVATE-PDF-PROMPT-KEY-RESPONSE'
SOURCE = {'page': 1, 'block_id': 'p0001-b0001', 'quote': PRIVATE}


class ValidationDiagnostics(unittest.IsolatedAsyncioTestCase):
    async def reject(self, contract, payload, expected, provider_name='groq'):
        calls = []
        text = payload if isinstance(payload, str) else json.dumps(payload)
        def respond(request):
            calls.append(request)
            response = ({'candidates': [{'content': {'parts': [{'text': text}]}}]} if provider_name == 'gemini'
                else {'choices': [{'message': {'content': text}}]})
            return httpx.Response(200, json=response)
        fence = AsyncMock()
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            provider = GeminiProvider(client) if provider_name == 'gemini' else GroqProvider(client)
            with self.assertLogs(level='INFO') as logs:
                with self.assertRaises(AIError) as rejected:
                    route=SimpleNamespace(route=lambda task: [MODELS['flash' if provider_name=='gemini' else 'vision']])
                    await AIRouter(settings=route,providers={provider_name: provider}).generate(task='edital_extract',
                        keys={provider_name: PRIVATE}, prompt=PRIVATE, output_type=contract, on_attempt=fence,
                        diagnostic_context={'stage': 'inventory', 'unit_id': '11111111-1111-4111-8111-111111111111'})
        error = rejected.exception
        self.assertEqual(error.kind, 'malformed_output')
        self.assertEqual(error.response_validation, expected)
        self.assertTrue(error.attempted)
        self.assertIsNone(error.http_status)  # Do not invent a retained HTTP status.
        self.assertEqual(error.request_format, 'groq_json_schema' if provider_name == 'groq' else 'gemini_response_format')
        self.assertEqual(len(error.schema_sha256), 64)
        self.assertGreater(error.schema_bytes, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(fence.await_count, 1)
        self.assertNotIn(PRIVATE, str(error) + json.dumps(error.response_validation) + ' '.join(logs.output))
        self.assertIn('response_validation=', ' '.join(logs.output))
        self.assertIn(error.reference, ' '.join(logs.output))

    async def test_json_schema_and_pydantic_are_distinct_without_output_repair(self):
        cases = [
            ('```json\n{}\n```', {'stage': 'json_decode', 'code': 'markdown_fence', 'path': '$'}),
            ('{"private":' + PRIVATE, {'stage': 'json_decode', 'code': 'invalid_json', 'path': '$'}),
            ({'roles': []}, {'stage': 'json_schema', 'code': 'required', 'path': '$.classifications'}),
            ({'roles': [], 'classifications': [{'block_id':'p0001-b0001','kind':'other'}], PRIVATE: PRIVATE},
                {'stage': 'json_schema', 'code': 'additionalProperties', 'path': '$'}),
            ({'roles': [{'name': {'value': PRIVATE, 'sources': [SOURCE]}}], 'classifications': [{'block_id':'p0001-b0001','kind':'other'}]},
                {'stage': 'json_schema', 'code': 'anyOf', 'path': '$.roles[].name'}),
            ({'roles': [], 'classifications': [{'block_id':'p0001-b0001','kind':'other','level':'section'}]},
                {'stage': 'pydantic', 'code': 'value_error', 'path': '$.classifications[]', 'rule': 'heading_title_missing'}),
        ]
        for provider in ('groq', 'gemini'):
            for payload, expected in cases:
                with self.subTest(provider=provider, expected=expected):
                    await self.reject(InventoryUnit, payload, expected, provider)

    async def test_all_four_real_contracts_keep_evidence_and_structural_gates(self):
        for contract, payload, expected in [
            (InventoryUnit, {'roles': [], 'classifications': [{'block_id': 'p0001-b0001', 'kind': 'other',
                'title': {'value': PRIVATE, 'sources': [SOURCE]}}]},
                {'stage': 'json_schema', 'code': 'anyOf', 'path': '$.classifications[]'}),
            (ScopeUnit, {'bindings': [{'section_key': 'section-a', 'decision': 'include', 'reason': PRIVATE}]},
                {'stage': 'json_schema', 'code': 'anyOf', 'path': '$.bindings[]'}),
            (DetailUnit, {'applicability': 'selected_role', 'covered_block_ids': ['p0001-b0001']},
                {'stage': 'pydantic', 'code': 'value_error', 'path': '$', 'rule': 'applicability_evidence_missing'}),
            (VerificationUnit, {'covered_block_ids': ['p0001-b0001'], 'findings': []},
                {'stage': 'json_schema', 'code': 'required', 'path': '$.reviewed_unit_key'}),
        ]:
            with self.subTest(contract=contract.__name__):
                await self.reject(contract, payload, expected)

    def test_unknown_dynamic_locations_messages_inputs_and_metadata_cannot_escape(self):
        self.assertEqual(location_path(('roles', 128, PRIVATE, 'name')), '$.roles[].*')
        self.assertEqual(location_path(('roles', True, PRIVATE)), '$.roles.*')
        self.assertEqual(safe_validation({'stage': 'pydantic', 'code': 'value_error',
            'path': '$.' + PRIVATE, 'rule': PRIVATE, 'input': PRIVATE, 'message': PRIVATE}),
            {'stage': 'pydantic', 'code': 'value_error', 'path': '$'})
        for bad in (None, [], {'stage': PRIVATE, 'code': PRIVATE}, {'stage': {}, 'code': []},
            {'stage': 'json_schema', 'code': 'value_error'}):
            self.assertIsNone(safe_validation(bad))
        class PrivateError(BaseModel):
            value: str
            @model_validator(mode='after')
            def reject(self):
                raise ValueError(self.value)
        with self.assertRaises(ValidationError) as rejected:
            PrivateError.model_validate({'value': PRIVATE})
        metadata = pydantic_failure(rejected.exception)
        self.assertEqual(metadata, {'stage': 'pydantic', 'code': 'value_error', 'path': '$'})
        self.assertNotIn(PRIVATE, json.dumps(AIError(response_validation={**metadata, 'ctx': PRIVATE}).response_validation))
        self.assertIsNone(AIError().response_validation)  # Legacy calls remain compatible.
