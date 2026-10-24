"""Observed Groq compiler rejection, lossless wire shape and original gates."""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import httpx
from jsonschema import Draft202012Validator
from pydantic import ValidationError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai.config import MODELS
from ai.providers.groq import GroqProvider
from ai.providers.gemini import GeminiProvider
from ai.router import AIRouter
from ai.schemas import transport_schema
from ai.types import AIError
from edital_pipeline_contracts import InventoryUnit,ScopeUnit,DetailUnit,VerificationUnit
from edital_transport_contracts import InventoryTransport
from edital_wire_fixtures import inventory_wire
from test_edital_provider_regression import CASES,nodes
from test_edital_scope_contract_regression import BLOCK,SOURCE,FACT
from services.edital_semantics import validate_unit,EvidenceError

REJECTION=json.loads((Path(__file__).parent/'fixtures/groq_scope_discriminator_rejection.json').read_text())


def ambiguous_unions(schema):
    """Only the restriction evidenced by the real error, not a vendor emulator."""
    found=[]
    for node in nodes(schema):
        choices=node.get('anyOf',[])
        if len(choices)<2 or any(choice.get('type')!='object' for choice in choices):continue
        candidates=set.intersection(*(set(key for key,prop in choice.get('properties',{}).items()
            if 'enum' in prop or 'const' in prop) for choice in choices))
        if len(candidates)>1:found.append(sorted(candidates))
    return found


class WireInventory(unittest.IsolatedAsyncioTestCase):
    def canonical(self,scope='all_roles'):
        return {'roles':[{'name':FACT}], 'classifications':[{'block_id':BLOCK['id'],'kind':'roles',
            'scope':scope,'scope_sources':[SOURCE],
            'role_references':[FACT] if scope in ('named_roles','except_roles') else []}]}

    async def test_observed_compiler_rejection_is_reproduced_and_new_shape_passes_both_providers(self):
        old=transport_schema(InventoryUnit.model_json_schema(),'groq_json_v2',strict=True)
        self.assertIn(['kind','level','scope'],ambiguous_unions(old))
        for provider_name in ('groq','gemini'):
            calls=[];payload=inventory_wire(self.canonical())
            def respond(request):
                calls.append(request);body=json.loads(request.content)
                schema=body['response_format']['json_schema']['schema'] if provider_name=='groq' else body['generationConfig']['responseFormat']['text']['schema']
                if ambiguous_unions(schema):return httpx.Response(400,json=REJECTION)
                self.assertEqual(ambiguous_unions(schema),[])
                self.assertTrue(Draft202012Validator(schema).is_valid(payload))
                text=json.dumps(payload)
                return httpx.Response(200,json={'choices':[{'message':{'content':text}}]} if provider_name=='groq'
                    else {'candidates':[{'content':{'parts':[{'text':text}]}}]})
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                model=MODELS['vision' if provider_name=='groq' else 'flash']
                provider=GroqProvider(client) if provider_name=='groq' else GeminiProvider(client)
                router=AIRouter(settings=SimpleNamespace(route=lambda task:[model]),providers={provider_name:provider})
                if provider_name=='groq':
                    with self.assertRaises(AIError) as legacy:
                        await router.generate(task='edital_extract',keys={provider_name:'synthetic'},output_type=InventoryUnit,strict_schema=True)
                    self.assertEqual(legacy.exception.incompatibility,'schema_discriminator')
                    self.assertEqual(legacy.exception.provider_rejection['category'],'schema_discriminator')
                result=await router.generate(task='edital_extract',keys={provider_name:'synthetic'},output_type=InventoryTransport,strict_schema=True)
                canonical=result.data.as_canonical()
                self.assertEqual(validate_unit(canonical,[BLOCK]).roles[0].name.value,FACT['value'])
                self.assertEqual(canonical,InventoryUnit.model_validate(self.canonical()))
                self.assertEqual(len(calls),2 if provider_name=='groq' else 1)

    def test_all_current_contracts_avoid_the_observed_union_ambiguity(self):
        for contract in (InventoryTransport,ScopeUnit,DetailUnit,VerificationUnit):
            for profile in ('groq_json_v2','gemini_json_v2'):
                schema=transport_schema(contract.model_json_schema(),profile,strict=profile=='groq_json_v2')
                self.assertEqual(ambiguous_unions(schema),[])
                self.assertLess(len(json.dumps(schema).encode()),60000)

    def test_roundtrip_is_lossless_for_each_scope_and_does_not_mutate_wire_results(self):
        for scope in ('all_roles','named_roles','except_roles','unspecified'):
            expected=InventoryUnit.model_validate(self.canonical(scope))
            data=inventory_wire(self.canonical(scope));before=copy.deepcopy(data)
            result=InventoryTransport.model_validate(data)
            for unused in range(2):
                self.assertEqual(result.as_canonical().model_dump(mode='json'),expected.model_dump(mode='json'))
            self.assertEqual(data,before);self.assertEqual(result.model_dump(mode='json'),before)
            self.assertNotIn('applicability',result.as_canonical().model_dump()['classifications'][0])

    def test_sources_bounds_extra_keys_and_original_heading_validator_are_not_weakened(self):
        valid=inventory_wire(self.canonical())
        invalids=[]
        row=copy.deepcopy(valid);row['classifications'][0]['applicability']['scope_sources']=[];invalids.append(row)
        row=copy.deepcopy(valid);row['classifications'][0]['scope']='all_roles';invalids.append(row)
        row=copy.deepcopy(valid);row['classifications'][0]['block_id']='x'*65;invalids.append(row)
        row=copy.deepcopy(valid);row['classifications'][0]['level']='section';invalids.append(row)
        for row in invalids:
            with self.assertRaises(ValidationError):InventoryTransport.model_validate(row)
        legacy=InventoryUnit.model_validate(self.canonical()).model_dump(mode='json')
        with self.assertRaises(ValidationError):InventoryTransport.model_validate(legacy)
        fake=copy.deepcopy(valid);fake['classifications'][0]['applicability']['scope_sources'][0]['quote']='INVENTED CLAIM'
        canonical=InventoryTransport.model_validate(fake).as_canonical()
        with self.assertRaises(EvidenceError) as rejected:validate_unit(canonical,[BLOCK])
        self.assertEqual(str(rejected.exception),'source_excerpt_mismatch')

    async def test_canonical_pydantic_error_is_still_reported_before_router_success(self):
        data=inventory_wire(self.canonical());data['classifications'][0]['level']='section'
        def respond(request):return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(data)}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['vision']]),providers={'groq':GroqProvider(client)})
            with self.assertRaises(AIError) as failed:
                await router.generate(task='edital_extract',keys={'groq':'synthetic'},output_type=InventoryTransport,strict_schema=True)
        self.assertEqual(failed.exception.kind,'malformed_output')
        self.assertEqual(failed.exception.response_validation['stage'],'pydantic')
        self.assertEqual(failed.exception.response_validation['rule'],'heading_title_missing')
