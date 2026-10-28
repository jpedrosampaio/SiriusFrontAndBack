"""Strict Groq wire contracts with synthetic sources and mock HTTP only."""
import copy
import itertools
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
from jsonschema import Draft202012Validator
from pydantic import ValidationError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.config import MODELS
from ai.providers.groq import GroqProvider
from ai.providers.gemini import GeminiProvider
from ai.router import AIRouter
from ai.schemas import transport_schema, TRANSPORT_VERSION
from ai.types import AIError, AIRequest
from edital_pipeline_contracts import ProposedFact, SectionBinding, InventoryUnit
from edital_transport_contracts import InventoryTransport
from edital_wire_fixtures import inventory_wire
from test_edital_provider_regression import CASES, nodes
from test_edital_scope_contract_regression import SOURCE, FACT, BLOCK


class StrictContracts(unittest.IsolatedAsyncioTestCase):
    async def test_all_four_real_contracts_on_each_documented_strict_model(self):
        current=[(InventoryTransport,inventory_wire(CASES[0][1])),*CASES[1:]]
        for model, (contract, minimal) in itertools.product(('vision', 'reasoning', 'fast'), current):
            canonical = contract.model_json_schema(); original = copy.deepcopy(canonical)
            # Materialize defaults only in this synthetic provider fixture.
            # Runtime code never repairs model responses.
            complete = contract.model_validate(minimal).model_dump(mode='json')
            calls = []
            def respond(request):
                calls.append(request); body = json.loads(request.content)
                self.assertEqual(body['model'], MODELS[model].name)
                self.assertEqual(body['max_completion_tokens'], 3072)
                envelope = body['response_format']['json_schema']
                self.assertIs(envelope['strict'], True)
                schema = envelope['schema']
                self.assertEqual(schema['type'], 'object')
                Draft202012Validator.check_schema(schema)
                for node in nodes(schema):
                    if node.get('type') == 'object' or 'properties' in node:
                        self.assertIs(node['additionalProperties'], False)
                        self.assertEqual(set(node['required']), set(node.get('properties', {})))
                self.assertTrue(Draft202012Validator(schema).is_valid(complete))
                self.assertLess(len(json.dumps(schema).encode()), 60000)
                return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(complete)}}]})
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                router = AIRouter(settings=SimpleNamespace(route=lambda task: [MODELS[model]]), providers={'groq': GroqProvider(client)})
                result = await router.generate(task='edital_extract', keys={'groq': 'synthetic'}, output_type=contract,
                    strict_schema=True, max_tokens=3072)
            self.assertEqual(result.data, contract.model_validate(minimal))
            self.assertEqual(len(calls), 1); self.assertEqual(canonical, original)
        self.assertEqual(TRANSPORT_VERSION, 'structured-transport/9')

    def test_evidence_conditions_are_equivalent_to_the_original_validators(self):
        cases = []
        for state, value, sources in itertools.product((None, 'missing', 'extracted', 'ambiguous'),
                (None, '', 'Analista de Sistemas'), (None, [], [SOURCE])):
            row = {}
            for key, item in (('state', state), ('value', value), ('sources', sources)):
                if item is not None: row[key] = item
            cases.append((ProposedFact, row))
        for decision, sources in itertools.product(('include', 'exclude', 'ambiguous'), (None, [], [SOURCE])):
            row = {'section_key': 'section-a', 'decision': decision, 'reason': 'Fonte sintética'}
            if sources is not None: row['sources'] = sources
            cases.append((SectionBinding, row))
        for contract, row in cases:
            try: contract.model_validate(row); accepted = True
            except ValidationError: accepted = False
            self.assertEqual(Draft202012Validator(contract.model_json_schema()).is_valid(row), accepted)
        invalid = {'roles': [{'name': FACT}], 'classifications': [
            {'block_id': BLOCK['id'], 'kind': 'roles', 'scope': 'all_roles', 'title': FACT}]}
        with self.assertRaises(ValidationError): InventoryUnit.model_validate(invalid)
        # Strict projection cannot accept the observed missing-scope-evidence shape.
        self.assertFalse(Draft202012Validator(transport_schema(InventoryUnit.model_json_schema(),
            'groq_json_v2', strict=True)).is_valid(invalid))

    async def test_strict_wire_is_checked_locally_without_filling_missing_fields(self):
        contract, minimal = CASES[0]
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(minimal)}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            router = AIRouter(settings=SimpleNamespace(route=lambda task: [MODELS['vision']]), providers={'groq': GroqProvider(client)})
            with self.assertRaises(AIError) as failed:
                await router.generate(task='edital_extract', keys={'groq': 'synthetic'}, output_type=contract, strict_schema=True)
        self.assertEqual(failed.exception.kind, 'malformed_output')
        self.assertEqual(failed.exception.response_validation['stage'], 'json_schema')
        self.assertEqual(failed.exception.request_format, 'groq_json_schema_strict')
        self.assertEqual(len(calls), 1)
        self.assertEqual(contract.model_validate(minimal).roles, [])

    async def test_capability_guard_precedes_reservation_and_network(self):
        provider = SimpleNamespace(generate_structured=AsyncMock())
        unsupported = replace(MODELS['vision'], strict_structured=False)
        reserve, attempt = AsyncMock(return_value=True), AsyncMock()
        router = AIRouter(settings=SimpleNamespace(route=lambda task: [unsupported]), providers={'groq': provider}, reserve=reserve)
        with self.assertRaises(AIError) as failed:
            await router.generate(task='edital_extract', keys={'groq': 'synthetic'}, output_type=InventoryUnit,
                strict_schema=True, on_attempt=attempt)
        self.assertEqual(failed.exception.incompatibility, 'model_capability')
        reserve.assert_not_awaited(); attempt.assert_not_awaited(); provider.generate_structured.assert_not_awaited()
        with self.assertRaises(AIError): transport_schema(InventoryUnit.model_json_schema(), 'gemini_json_v2', strict=True)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: self.fail('No network allowed'))) as client:
            with self.assertRaises(AIError):
                await GroqProvider(client).generate(unsupported, 'synthetic', AIRequest('edital_extract', 'synthetic',
                    schema=InventoryUnit.model_json_schema(), strict_schema=True))

    async def test_quota_and_unavailability_preserve_the_single_attempt_fence_and_can_recover(self):
        complete = InventoryUnit.model_validate(CASES[0][1]).model_dump(mode='json')
        for status, kind in ((429, 'quota'), (429, 'rate_limit'), (503, 'unavailable')):
            calls = []
            def respond(request):
                calls.append(request)
                self.assertTrue(json.loads(request.content)['response_format']['json_schema']['strict'])
                if len(calls) == 1: return httpx.Response(status, json={'error': {'message':
                    'Synthetic quota reached' if kind == 'quota' else 'Synthetic provider failure'}})
                return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(complete)}}]})
            attempts = []
            async def one_attempt(model):
                if attempts: raise AIError('pilot_limit')
                attempts.append(model.name)
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                router = AIRouter(settings=SimpleNamespace(route=lambda task: [MODELS['vision'], MODELS['reasoning']]),
                    providers={'groq': GroqProvider(client)})
                with self.assertRaises(AIError) as failed:
                    await router.generate(task='edital_extract', keys={'groq': 'synthetic'}, output_type=InventoryUnit,
                        strict_schema=True, on_attempt=one_attempt)
                self.assertEqual(failed.exception.kind, kind)
                self.assertEqual(len(calls), 1); self.assertEqual(len(attempts), 1)
                # Explicit later pilot after cooldown, without changing its contract.
                router.cooldowns.clear(); attempts.clear()
                result = await router.generate(task='edital_extract', keys={'groq': 'synthetic'}, output_type=InventoryUnit,
                    strict_schema=True, on_attempt=one_attempt)
                self.assertEqual(result.data.roles, []); self.assertEqual(len(calls), 2)
                self.assertEqual(len(attempts), 1)

    async def test_rejected_strict_request_is_not_retried_or_silently_downgraded(self):
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(400, json={'error': {'message': 'Unsupported response_format.json_schema.strict'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            router = AIRouter(settings=SimpleNamespace(route=lambda task: [MODELS['vision'], MODELS['reasoning']]),
                providers={'groq': GroqProvider(client)})
            for unused in range(2):
                with self.assertRaises(AIError) as failed:
                    await router.generate(task='edital_extract', keys={'groq': 'synthetic'}, output_type=InventoryUnit, strict_schema=True)
                self.assertEqual(failed.exception.http_status, 400)
                self.assertEqual(failed.exception.request_format, 'groq_json_schema_strict')
            self.assertEqual(len(calls), 1)
            # Best-effort is a distinct explicit request, not an automatic fallback.
            with self.assertRaises(AIError):
                await router.generate(task='edital_extract', keys={'groq': 'synthetic'}, output_type=InventoryUnit)
            self.assertEqual(len(calls), 2)

    async def test_gemini_envelope_and_best_effort_defaults_remain_unchanged(self):
        for provider_name in ('groq', 'gemini'):
            def respond(request):
                body = json.loads(request.content)
                if provider_name == 'groq':
                    self.assertFalse(body['response_format']['json_schema']['strict'])
                    data = {'choices': [{'message': {'content': json.dumps(CASES[0][1])}}]}
                else:
                    self.assertIn('responseFormat', body['generationConfig'])
                    self.assertNotIn('strict', json.dumps(body['generationConfig']))
                    data = {'candidates': [{'content': {'parts': [{'text': json.dumps(CASES[0][1])}]}}]}
                return httpx.Response(200, json=data)
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                provider = GroqProvider(client) if provider_name == 'groq' else GeminiProvider(client)
                router = AIRouter(settings=SimpleNamespace(route=lambda task: [MODELS['vision' if provider_name == 'groq' else 'flash']]),
                    providers={provider_name: provider})
                await router.generate(task='edital_extract', keys={provider_name: 'synthetic'}, output_type=InventoryUnit,
                    strict_schema=provider_name == 'gemini')
