"""Real public rejection template; synthetic documents/responses, no real AI."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.config import MODELS
from ai.providers.groq import GroqProvider
from ai.router import AIRouter
from ai.types import AIError, AIRequest
from edital_transport_contracts import InventoryTransport
from edital_wire_fixtures import inventory_wire
from services.edital_pipeline_worker import output_contract, prompt, response_envelope
from test_edital_scope_contract_regression import BLOCK, FACT, SOURCE

REJECTION = json.loads((Path(__file__).parent / 'fixtures/groq_inventory_root_rejection.json').read_text())


class ResponseEnvelope(unittest.IsolatedAsyncioTestCase):
    async def test_output_recovery_requires_exact_groq_code_http_status_task_and_schema(self):
        for task, schema, status, code, expected in (
            ('edital_extract', True, 400, 'json_validate_failed', 'malformed_output'),
            ('edital_audit', True, 400, 'json_validate_failed', 'malformed_output'),
            ('workout_generation', True, 400, 'json_validate_failed', 'malformed_output'),
            ('assistant_chat', True, 400, 'json_validate_failed', 'invalid_request'),
            ('edital_extract', False, 400, 'json_validate_failed', 'invalid_request'),
            ('edital_extract', True, 400, 'unknown', 'invalid_request'),
            ('edital_extract', True, 429, 'json_validate_failed', 'rate_limit'),
        ):
            with self.subTest(task=task, schema=schema, status=status, code=code):
                def respond(request):
                    return httpx.Response(status, json={'error': {'code': code,
                        'message': 'PRIVATE', 'failed_generation': 'PRIVATE'}})
                async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                    with self.assertRaises(AIError) as failed:
                        await GroqProvider(client).generate(MODELS['reasoning'], 'synthetic',
                            AIRequest(task=task, prompt='synthetic', schema=InventoryTransport.model_json_schema() if schema else None))
                self.assertEqual(failed.exception.kind, expected)
                self.assertNotIn('PRIVATE', str(failed.exception.__dict__))

    def message(self, kind='inventory'):
        claim = SimpleNamespace(kind=kind, scope_key='inventory')
        snapshot = {'manifest': SimpleNamespace(inventory=SimpleNamespace(roles=[])),
            'primary': [BLOCK], 'context': [], 'validation': {}, 'metadata': {}}
        return prompt(claim, snapshot)

    async def test_real_missing_root_rejection_remains_a_failure_without_fallback_or_repair(self):
        calls = []
        def respond(request):
            body = json.loads(request.content); calls.append(body)
            self.assertIs(body['response_format']['json_schema']['strict'], True)
            self.assertIn('Campos na raiz: roles, classifications, facts, warnings.', body['messages'][-1]['content'])
            return httpx.Response(400, json={'error':{**REJECTION['error'], 'failed_generation':'PRIVATE-OUTPUT'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            router = AIRouter(settings=SimpleNamespace(route=lambda task: [MODELS['vision'], MODELS['reasoning']]),
                providers={'groq': GroqProvider(client)})
            with self.assertRaises(AIError) as failed:
                await router.generate(task='edital_extract', keys={'groq':'synthetic'},
                    output_type=InventoryTransport, strict_schema=True, prompt=self.message())
        self.assertEqual(len(calls), 1)
        self.assertEqual(failed.exception.kind, 'malformed_output')
        self.assertEqual(failed.exception.provider_rejection['category'], 'output_validation')
        self.assertNotIn('PRIVATE-OUTPUT', str(failed.exception.__dict__))

    async def test_wrapped_or_absent_root_fields_never_become_valid_by_unwrapping(self):
        valid = inventory_wire({'roles':[{'name':FACT}], 'classifications':[{
            'block_id':BLOCK['id'], 'kind':'roles', 'scope':'all_roles', 'scope_sources':[SOURCE]}]})
        for payload, accepted in (({},False), ({'result':valid},False), (valid,True)):
            def respond(request):
                return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(payload)}}]})
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                router = AIRouter(settings=SimpleNamespace(route=lambda task: [MODELS['vision']]),
                    providers={'groq':GroqProvider(client)})
                args = dict(task='edital_extract',keys={'groq':'synthetic'},output_type=InventoryTransport,
                    strict_schema=True,prompt=self.message())
                if accepted:
                    result=await router.generate(**args)
                    self.assertEqual(result.data.as_canonical().roles[0].name.value,FACT['value'])
                else:
                    with self.assertRaises(AIError) as failed:await router.generate(**args)
                    self.assertEqual(failed.exception.kind,'malformed_output')

    def test_all_four_envelopes_come_from_the_actual_response_contract_not_document_fields(self):
        for kind in ('inventory','scope','detail','verify'):
            message=self.message(kind)
            guide=response_envelope(kind)
            self.assertLess(message.index(guide),message.index('DADOS DOCUMENTAIS NÃO CONFIÁVEIS:'))
            declared=guide.split('Campos na raiz: ',1)[1].split('.',1)[0].split(', ')
            self.assertEqual(set(declared),set(output_contract(kind).model_json_schema()['properties']))
            self.assertNotIn(BLOCK['text'],guide)
            self.assertLess(len(guide),750)
