"""Source-bound schemas over mock HTTP; no live provider or document data."""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai.config import MODELS
from ai.providers.groq import GroqProvider
from ai.router import AIRouter
from ai.types import AIError
from ai.validation_diagnostics import documentary_failure
from edital_pipeline_contracts import ScopeUnit,DetailUnit,VerificationUnit,InventoryUnit
from edital_transport_contracts import InventoryTransport
from edital_wire_fixtures import inventory_wire
from services.edital_source_contract import source_contract
from services.edital_semantics import validate_unit,EvidenceError

PRIMARY=[{'id':'p0001-b0001','page':1,'text':'Cargo: Analista.'},{'id':'p0002-b0001','page':2,'text':'Cronograma.'}]
CONTEXT=[{'id':'p0003-b0001','page':3,'text':'Contexto da seção.'}]
def payload(page=1,block_id='p0001-b0001'):
    return inventory_wire({'roles':[{'name':{'value':'Analista','state':'extracted','sources':[{'page':page,'block_id':block_id,'quote':'Cargo: Analista.'}]}}],
        'classifications':[{'block_id':'p0001-b0001','end_block_id':'p0002-b0001','kind':'roles'}]})

class SourceContracts(unittest.IsolatedAsyncioTestCase):
    def test_all_real_stage_contracts_bind_citations_without_mutating_canonical_schema(self):
        for contract in (InventoryTransport,ScopeUnit,DetailUnit,VerificationUnit):
            with self.subTest(contract=contract.__name__):
                original=copy.deepcopy(contract.model_json_schema())
                bound=source_contract(contract,PRIMARY,CONTEXT)
                citation=bound['$defs']['Citation']['properties']
                self.assertEqual(citation['block_id']['enum'],[b['id'] for b in PRIMARY+CONTEXT])
                self.assertEqual(citation['page']['enum'],[1,2,3])
                self.assertEqual(contract.model_json_schema(),original)
                if contract is InventoryTransport:
                    fields=bound['$defs']['ClassificationTransport']['properties']
                    self.assertEqual(fields['block_id']['enum'],[b['id'] for b in PRIMARY])
                if contract in (DetailUnit,VerificationUnit):
                    self.assertEqual(bound['properties']['covered_block_ids']['items']['enum'],[b['id'] for b in PRIMARY])

    async def test_real_wire_restricts_references_and_canonical_gate_remains_mandatory(self):
        response=payload();calls=[]
        def answer(request):
            body=json.loads(request.content);calls.append(body)
            fields=body['response_format']['json_schema']['schema']['$defs']['Citation']['properties']
            self.assertEqual(fields['block_id']['enum'],[b['id'] for b in PRIMARY]);self.assertEqual(fields['page']['enum'],[1,2])
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(response)}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
            router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['reasoning']]),providers={'groq':GroqProvider(client)})
            kwargs=dict(task='edital_extract',keys={'groq':'synthetic'},output_type=InventoryTransport,strict_schema=True,transport_contract=source_contract(InventoryTransport,PRIMARY))
            result=await router.generate(**kwargs);validate_unit(result.data.as_canonical(),PRIMARY)
            response=payload(block_id='p0999-b0001')
            with self.assertRaises(AIError) as rejected:await router.generate(**kwargs)
            self.assertEqual(rejected.exception.kind,'malformed_output')
            self.assertEqual(rejected.exception.response_validation['stage'],'json_schema')
            self.assertTrue(rejected.exception.response_validation['path'].startswith('$.roles[].name'))
            # Both values individually belong to the source enum, but this pair
            # is false. The original document comparison must still reject it.
            response=payload(page=2);result=await router.generate(**kwargs)
            with self.assertRaises(EvidenceError) as rejected:validate_unit(result.data.as_canonical(),PRIMARY)
            self.assertEqual(documentary_failure(rejected.exception),{'stage':'documentary','code':'source_reference_mismatch','path':'$.roles[].name.sources[].page'})
        self.assertEqual(len(calls),3)

    async def test_all_four_bound_stage_schemas_reach_mock_transport_and_original_validation(self):
        from test_edital_provider_regression import CASES
        response={};calls=[]
        def answer(request):
            body=json.loads(request.content);calls.append(body)
            citation=body['response_format']['json_schema']['schema']['$defs']['Citation']['properties']
            self.assertEqual(citation['block_id']['enum'],['p0001-b0001']);self.assertEqual(citation['page']['enum'],[1])
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(response)}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
            router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['reasoning']]),providers={'groq':GroqProvider(client)})
            for contract,minimum in CASES:
                output=InventoryTransport if contract is InventoryUnit else contract
                response=inventory_wire(minimum) if contract is InventoryUnit else contract.model_validate(minimum).model_dump(mode='json')
                result=await router.generate(task='edital_extract',keys={'groq':'synthetic'},output_type=output,strict_schema=True,
                    transport_contract=source_contract(output,PRIMARY[:1]))
                canonical=result.data.as_canonical() if contract is InventoryUnit else result.data
                validate_unit(canonical,PRIMARY[:1],expected_section_keys=('section-a',),expected_reviewed_unit_key='a'*64)
        self.assertEqual(len(calls),4)

    async def test_invalid_transport_contract_is_stopped_before_provider_or_reservation(self):
        from unittest.mock import AsyncMock
        reserved=AsyncMock();provider=SimpleNamespace(generate_structured=AsyncMock())
        router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['reasoning']]),providers={'groq':provider},reserve=reserved)
        for bound in (False,{},'PRIVATE-INVALID'):
            with self.subTest(bound=type(bound).__name__),self.assertRaises(AIError):
                await router.generate(task='edital_extract',keys={'groq':'synthetic'},output_type=InventoryTransport,transport_contract=bound)
        reserved.assert_not_awaited();provider.generate_structured.assert_not_awaited()

    async def test_broader_transport_can_never_bypass_the_original_output_model(self):
        def answer(request):return httpx.Response(200,json={'choices':[{'message':{'content':'{}'}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
            router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['reasoning']]),providers={'groq':GroqProvider(client)})
            with self.assertRaises(AIError) as rejected:
                await router.generate(task='edital_extract',keys={'groq':'synthetic'},output_type=InventoryTransport,strict_schema=True,
                    transport_contract={'type':'object','properties':{},'additionalProperties':False})
            self.assertEqual(rejected.exception.kind,'malformed_output')

    def test_documentary_locations_cannot_publish_private_dynamic_keys_or_values(self):
        error=EvidenceError('source_reference_mismatch',('roles',0,'PRIVATE-PDF-KEY',123))
        public=documentary_failure(error)
        self.assertEqual(public['path'],'$.roles[].*');self.assertNotIn('PRIVATE',json.dumps(public))
