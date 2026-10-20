"""Real semantic contracts over mock HTTP; no provider secrets or live calls."""
import copy
from contextlib import nullcontext
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
import httpx
from pydantic import BaseModel
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai.config import MODELS
from ai.types import AIError,AIRequest
from ai.router import AIRouter,normalize_schema
from ai.providers.gemini import GeminiProvider
from ai.providers.groq import GroqProvider
from ai.schemas import transport_schema
from edital_pipeline_contracts import InventoryUnit,ScopeUnit,DetailUnit,VerificationUnit
from services.edital_pipeline_budget import estimate
from services.edital_pipeline_inputs import inventory_batches,compact_block
from services.edital_pipeline_store import input_context
from services.edital_pipeline_worker import prompt
from types import SimpleNamespace
from uuid import uuid4

CASES=[(InventoryUnit,{'roles':[],'classifications':[{'block_id':'p0001-b0001','kind':'other'}]}),
    (ScopeUnit,{'bindings':[{'section_key':'section-a','decision':'ambiguous','reason':'Exige conferência.'}]}),
    (DetailUnit,{'applicability':'ambiguous','covered_block_ids':['p0001-b0001']}),
    (VerificationUnit,{'reviewed_unit_key':'a'*64,'covered_block_ids':['p0001-b0001'],'findings':[]})]


def nodes(value):
    if isinstance(value,dict):
        yield value
        for key,child in value.items():
            if key in ('properties','$defs'):
                for sub in child.values():yield from nodes(sub)
            elif key in ('anyOf','oneOf','prefixItems'):
                for sub in child:yield from nodes(sub)
            elif key in ('items','additionalProperties'):yield from nodes(child)


class ProviderContracts(unittest.IsolatedAsyncioTestCase):
    async def test_all_real_contracts_use_transport_subset_and_original_pydantic_validation(self):
        for output,payload in CASES:
            original=copy.deepcopy(output.model_json_schema())
            for provider_name in ('gemini','groq'):
                with self.subTest(contract=output.__name__,provider=provider_name):
                    def transport(request):
                        body=json.loads(request.content)
                        wire=body['generationConfig']['responseJsonSchema'] if provider_name=='gemini' else body['response_format']['json_schema']['schema']
                        self.assertNotEqual(wire,original)
                        for node in nodes(wire):
                            self.assertFalse({'default','minLength','maxLength','pattern','title'}&node.keys())
                            if '$ref' in node:self.assertEqual(set(node),{'$ref'})
                        if provider_name=='gemini':
                            self.assertFalse(body['store'])
                            response={'candidates':[{'content':{'parts':[{'text':json.dumps(payload)}]}}]}
                        else:response={'choices':[{'message':{'content':json.dumps(payload)}}]}
                        return httpx.Response(200,json=response)
                    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                        provider=GeminiProvider(client) if provider_name=='gemini' else GroqProvider(client)
                        result=await AIRouter(providers={provider_name:provider}).generate(task='edital_audit',
                            keys={provider_name:'synthetic'},output_type=output,prompt='Synthetic source')
                        self.assertEqual(result.data,output.model_validate(payload))
                    self.assertEqual(output.model_json_schema(),original)

    async def test_rejected_schema_is_permanent_correlated_redacted_and_not_repeated(self):
        calls=[];private='PRIVATE-KEY-PROMPT-RESPONSE'
        def rejected(request):
            calls.append(request)
            return httpx.Response(400,json={'error':{'message':'Unsupported keyword default in responseJsonSchema '+private}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(rejected)) as client:
            router=AIRouter(providers={'gemini':GeminiProvider(client),'groq':GroqProvider(client)})
            for repeat in range(2):
                with (self.assertLogs(level='INFO') if repeat==0 else nullcontext()) as logs:
                    with self.assertRaises(AIError) as failure:
                        await router.generate(task='edital_audit',keys={'gemini':private},output_type=InventoryUnit,prompt=private,
                            diagnostic_context={'stage':'inventory','unit_id':'11111111-1111-4111-8111-111111111111'})
                self.assertEqual(failure.exception.kind,'invalid_request')
                self.assertEqual(failure.exception.http_status,400)
                self.assertEqual(failure.exception.incompatibility,'schema_keyword')
                self.assertEqual(failure.exception.attempted,repeat==0)
                if repeat==0:
                    message=' '.join(logs.output)
                    self.assertIn('http_status=400',message);self.assertIn('stage=inventory',message)
                    self.assertIn(failure.exception.reference,message);self.assertNotIn(private,message)
            self.assertEqual(len(calls),1)

    async def test_original_constraints_reject_extra_fields_and_overlong_values(self):
        malformed={'roles':[],'classifications':[{'block_id':'x'*65,'kind':'other'}]}
        def response(request):return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(malformed)}]}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            with self.assertRaises(AIError) as failure:
                await AIRouter(providers={'gemini':GeminiProvider(client)}).generate(task='edital_extract',keys={'gemini':'synthetic'},output_type=InventoryUnit)
            self.assertEqual(failure.exception.kind,'malformed_output')

    async def test_model_specific_rejection_can_fallback_but_unknown_400_cannot(self):
        for message,expected in [('This model does not support structured output',2),('Invalid request PRIVATE',1)]:
            calls=[]
            def response(request):
                calls.append(request)
                if len(calls)==1:return httpx.Response(400,json={'error':{'message':message}})
                return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(CASES[0][1])}]}}]})
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
                router=AIRouter(providers={'gemini':GeminiProvider(client)})
                if expected==1:
                    with self.assertRaises(AIError):await router.generate(task='edital_extract',keys={'gemini':'synthetic'},output_type=InventoryUnit)
                else:
                    result=await router.generate(task='edital_extract',keys={'gemini':'synthetic'},output_type=InventoryUnit)
                    self.assertTrue(result.fallback)
                self.assertEqual(len(calls),expected)
                if expected==2:
                    await router.generate(task='edital_extract',keys={'gemini':'synthetic'},output_type=InventoryUnit,prompt='Another documentary unit')
                    self.assertEqual(len(calls),3) # known incompatible model is skipped

    async def test_cooldown_consumes_no_durable_provider_attempt_and_keeps_reason(self):
        def response(request):return httpx.Response(503,json={})
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            router=AIRouter(providers={'gemini':GeminiProvider(client)})
            fence=AsyncMock()
            for repeat in range(2):
                with self.assertRaises(AIError) as failure:
                    await router.generate(task='edital_extract',keys={'gemini':'synthetic'},output_type=InventoryUnit,on_attempt=fence)
                if repeat:self.assertFalse(failure.exception.attempted);self.assertEqual(failure.exception.reason,'cooldown')
            self.assertEqual(fence.await_count,2)  # two actual models on first execution only

    async def test_pilot_fence_preserves_actual_http_failure_and_quota_recovers(self):
        for status,body,kind in [(400,{'error':{'message':'This model does not support structured output'}},'invalid_request'),
            (429,{'error':{'message':'quota exceeded'}},'quota'),(503,{},'unavailable')]:
            calls=[];reserved=[]
            def response(request):calls.append(request);return httpx.Response(status,json=body)
            async def one_attempt(model):
                if reserved:raise AIError('pilot_limit')
                reserved.append(model)
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
                router=AIRouter(providers={'gemini':GeminiProvider(client)})
                with self.assertRaises(AIError) as failure:
                    await router.generate(task='edital_extract',keys={'gemini':'synthetic'},output_type=InventoryUnit,on_attempt=one_attempt)
                self.assertEqual(failure.exception.kind,kind);self.assertEqual(failure.exception.http_status,status)
                self.assertTrue(failure.exception.attempted);self.assertEqual(len(calls),1)
        count=[]
        def recovered(request):
            count.append(request)
            if len(count)<=2:return httpx.Response(429,json={'error':{'message':'quota exceeded'}})
            return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(CASES[0][1])}]}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(recovered)) as client:
            router=AIRouter(providers={'gemini':GeminiProvider(client)})
            with self.assertRaises(AIError):await router.generate(task='edital_extract',keys={'gemini':'synthetic'},output_type=InventoryUnit)
            with self.assertRaises(AIError) as cooling:
                await router.generate(task='edital_extract',keys={'gemini':'synthetic'},output_type=InventoryUnit)
            self.assertEqual(cooling.exception.reason,'cooldown');self.assertEqual(len(count),2)
            router.cooldowns.clear()
            result=await router.generate(task='edital_extract',keys={'gemini':'synthetic'},output_type=InventoryUnit)
            self.assertEqual(result.data,InventoryUnit.model_validate(CASES[0][1]));self.assertEqual(len(count),3)

    def test_unsupported_or_recursive_schema_fails_before_transport(self):
        deep={'$defs':{f'N{i}':{'$ref':f'#/$defs/N{i+1}'} if i<39 else {'type':'string'} for i in range(40)},'$ref':'#/$defs/N0'}
        for schema in ({'allOf':[{'type':'string'}]}, {'$defs':{'Loop':{'$ref':'#/$defs/Loop'}},'$ref':'#/$defs/Loop'},deep):
            with self.assertRaises(AIError):transport_schema(schema,'gemini_json_v2')

    def test_canonical_normalization_keeps_literal_property_names_and_enum_data(self):
        schema={'type':'OBJECT','properties':{'nullable':{'type':'STRING'},'propertyOrdering':{'enum':[{'nullable':True}]}},'nullable':True}
        normalized=normalize_schema(schema)
        self.assertEqual(normalized['type'],['object','null'])
        self.assertEqual(set(normalized['properties']),{'nullable','propertyOrdering'})
        self.assertEqual(normalized['properties']['propertyOrdering']['enum'],[{'nullable':True}])

    def test_extensive_document_packing_preserves_every_block_table_and_reference_with_bounded_prompts(self):
        blocks=[{'id':f'p{index//40+1:04d}-b{index%40+1:04d}','page':index//40+1,'text':'Texto sintético com referências. '*8,
            'kind':'table_cell' if index%3==0 else 'paragraph','column':0,'table_id':f't-{index//9}',
            'table_header_hint':'Vagas e requisitos','continuation_of':None} for index in range(2800)]
        packed=list(inventory_batches(blocks));previous=[]
        self.assertEqual([item for batch in packed for item in batch],blocks)
        self.assertEqual(compact_block(blocks[0])['column'],0)
        by_id={b['id']:b for b in blocks}
        for batch in packed:
            context=input_context(batch,blocks,previous)
            snapshot={'primary':batch,'context':[by_id[k] for k in context],
                'manifest':SimpleNamespace(inventory=SimpleNamespace(roles=[])),'validation':{},'metadata':{}}
            self.assertLess(len(prompt(SimpleNamespace(kind='inventory',scope_key='inventory'),snapshot)),24000)
            self.assertLessEqual(len(batch),60)
            for block in batch:
                self.assertEqual(compact_block(block)['text'],block['text'])
                self.assertEqual(compact_block(block)['table_header_hint'],block['table_header_hint'])
            previous=batch

    def test_plan_counts_future_checks_reservations_and_only_current_transport_pilot(self):
        from ai.schemas import TRANSPORT_VERSION
        generation=uuid4()
        approval=SimpleNamespace(pilot_validated=True,transport_version='old')
        state=SimpleNamespace(inventory=SimpleNamespace(generation=generation),selected_role_id=None,scopes={},
            budget=SimpleNamespace(reserved_attempts=5,provider_limit=120),provider_approval=approval)
        rows=[{'generation':generation,'status':'pending','kind':'inventory','unit_key':str(i)} for i in range(67)]
        plan=estimate(state,rows)
        self.assertEqual(plan['minimum_total_attempts'],139);self.assertFalse(plan['live_provider_validated'])
        approval.transport_version=TRANSPORT_VERSION
        rows[0]['status']='completed';rows.append({'generation':generation,'status':'pending','kind':'verify',
            'unit_key':'check','reviewed_unit_key':'0'})
        plan=estimate(state,rows)
        self.assertEqual(plan['minimum_total_attempts'],138);self.assertTrue(plan['live_provider_validated'])
