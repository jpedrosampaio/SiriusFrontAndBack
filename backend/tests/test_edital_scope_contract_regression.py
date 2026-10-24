"""The observed scope-without-evidence failure, without real provider calls."""
import copy
import itertools
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import httpx
from jsonschema import Draft202012Validator
from pydantic import ValidationError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.config import MODELS
from ai.providers.groq import GroqProvider
from ai.providers.gemini import GeminiProvider
from ai.router import AIRouter
from ai.schemas import transport_schema
from ai.types import AIError
from edital_pipeline_contracts import BlockClassification, InventoryUnit
from services.edital_pipeline_worker import prompt, FACT_CONTRACT
from services.edital_semantics import validate_unit, EvidenceError

TEXT = 'Perfil A: Analista de Sistemas. Estas regras aplicam-se a todos os cargos.'
SOURCE = {'page': 1, 'block_id': 'p0001-b0001', 'quote': TEXT}
BLOCK = {'id': SOURCE['block_id'], 'page': 1, 'text': TEXT, 'kind': 'line', 'column': 0}
FACT = {'value': 'Analista de Sistemas', 'state': 'extracted', 'sources': [SOURCE]}


class ScopeContract(unittest.IsolatedAsyncioTestCase):
    def test_wire_scope_conditions_match_the_unchanged_pydantic_invariant(self):
        canonical = BlockClassification.model_json_schema()
        original = copy.deepcopy(canonical)
        variants = [canonical, transport_schema(canonical, 'groq_json_v2'), transport_schema(canonical, 'gemini_json_v2')]
        for schema in variants: Draft202012Validator.check_schema(schema)
        for scope, sources, references in itertools.product(
            (None, 'unspecified', 'all_roles', 'named_roles', 'except_roles'), (None, [], [SOURCE]), (None, [], [FACT])):
            row = {'block_id': BLOCK['id'], 'kind': 'roles'}
            if scope is not None: row['scope'] = scope
            if sources is not None: row['scope_sources'] = sources
            if references is not None: row['role_references'] = references
            try: BlockClassification.model_validate(row); accepted = True
            except ValidationError: accepted = False
            for schema in variants:
                with self.subTest(scope=scope, sources=sources, references=references):
                    self.assertEqual(Draft202012Validator(schema).is_valid(row), accepted)
        self.assertEqual(BlockClassification.model_json_schema(), original)
        self.assertEqual(BlockClassification.model_config['extra'], 'forbid')
        self.assertFalse(BlockClassification.model_config['allow_inf_nan'])

    async def test_real_failure_shape_is_rejected_and_documented_scope_can_pass_both_transports(self):
        invalid = {'roles': [], 'classifications': [{'block_id': BLOCK['id'], 'kind': 'roles', 'scope': 'all_roles'}]}
        with self.assertRaises(ValidationError) as old_gate:
            InventoryUnit.model_validate(invalid)
        self.assertIn('Semantic applicability requires source evidence', str(old_gate.exception))
        valid = copy.deepcopy(invalid)
        valid['classifications'][0]['scope_sources'] = [SOURCE]
        valid['roles'] = [{'name': FACT}]
        claim = SimpleNamespace(kind='inventory', scope_key='inventory')
        snapshot = {'manifest': SimpleNamespace(inventory=SimpleNamespace(roles=[])),
            'primary': [BLOCK], 'context': [], 'validation': {}, 'metadata': {}}
        message = prompt(claim, snapshot)
        self.assertIn(FACT_CONTRACT, message)
        self.assertIn('title.sources não substituem\nscope_sources', message)
        self.assertIn('scope=unspecified', message)
        self.assertLess(message.index('REGRAS DO CONTRATO'), message.index('DADOS DOCUMENTAIS NÃO CONFIÁVEIS'))
        for provider_name in ('gemini', 'groq'):
            for payload, accepted in ((invalid, False), (valid, True)):
                calls = []
                def response(request):
                    calls.append(request)
                    body = json.loads(request.content)
                    wire = body['response_format']['json_schema']['schema'] if provider_name == 'groq' else body['generationConfig']['responseFormat']['text']['schema']
                    self.assertFalse(Draft202012Validator(wire).is_valid(invalid))
                    self.assertTrue(Draft202012Validator(wire).is_valid(valid))
                    text = json.dumps(payload)
                    data = {'choices': [{'message': {'content': text}}]} if provider_name == 'groq' else {'candidates': [{'content': {'parts': [{'text': text}]}}]}
                    return httpx.Response(200, json=data)
                async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
                    provider = GroqProvider(client) if provider_name == 'groq' else GeminiProvider(client)
                    settings = SimpleNamespace(route=lambda task: [MODELS['vision' if provider_name == 'groq' else 'flash']])
                    router = AIRouter(settings=settings, providers={provider_name: provider})
                    if accepted:
                        result = await router.generate(task='edital_extract', keys={provider_name: 'synthetic'}, prompt=message, output_type=InventoryUnit)
                        self.assertEqual(validate_unit(result.data, [BLOCK]).roles[0].name.value, FACT['value'])
                    else:
                        with self.assertRaises(AIError) as rejected:
                            await router.generate(task='edital_extract', keys={provider_name: 'synthetic'}, prompt=message, output_type=InventoryUnit)
                        self.assertEqual(rejected.exception.kind, 'malformed_output')
                        self.assertEqual(rejected.exception.response_validation['stage'], 'json_schema')
                    self.assertEqual(len(calls), 1)

    def test_title_evidence_cannot_substitute_scope_evidence_and_fake_quotes_remain_rejected(self):
        missing = {'roles': [], 'classifications': [{'block_id': BLOCK['id'], 'kind': 'roles', 'scope': 'all_roles', 'title': FACT}]}
        for profile in ('groq_json_v2', 'gemini_json_v2'):
            self.assertFalse(Draft202012Validator(transport_schema(InventoryUnit.model_json_schema(), profile)).is_valid(missing))
        row = copy.deepcopy(missing)
        row['classifications'][0]['scope_sources'] = [{**SOURCE, 'quote': 'INVENTED DOCUMENTARY CLAIM'}]
        proposal = InventoryUnit.model_validate(row)
        with self.assertRaises(EvidenceError) as rejected:
            validate_unit(proposal, [BLOCK])
        self.assertEqual(str(rejected.exception), 'source_excerpt_mismatch')
