"""Total coverage is explicit; no inferred classification or missing source fill."""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import httpx
from pydantic import ValidationError
from jsonschema import Draft202012Validator
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai.router import AIRouter
from ai.config import MODELS
from ai.providers.groq import GroqProvider
from ai.types import AIError
from edital_partition_contract import partition_contract
from edital_pipeline_contracts import InventoryUnit
from edital_wire_fixtures import partition_wire
from services.edital_source_contract import source_contract
from services.edital_semantics import EvidenceError,validate_unit

IDS=['p0001-b0001','p0001-b0002','p0001-b0003']
BLOCKS=[{'id':identity,'page':1,'text':'Documento sintético.'} for identity in IDS]

def proposal():return {'roles':[],'classifications':[{'block_id':IDS[0],'end_block_id':IDS[-1],'kind':'other'}]}

class TotalCoverage(unittest.IsolatedAsyncioTestCase):
    def test_observed_old_gap_rejected_but_total_map_produces_exact_original_ranges(self):
        with self.assertRaises(EvidenceError) as error:
            validate_unit(InventoryUnit.model_validate({'roles':[],'classifications':[{'block_id':IDS[0],'kind':'other'}]}),BLOCKS)
        self.assertEqual(error.exception.code,'inventory_coverage_mismatch')
        wire=partition_wire(proposal(),IDS);contract=partition_contract(IDS)
        canonical=contract.model_validate(wire).as_canonical();validate_unit(canonical,BLOCKS)
        self.assertEqual(canonical,InventoryUnit.model_validate(proposal()))
        for change in ('missing','foreign','unused','unknown_index'):
            bad=copy.deepcopy(wire)
            if change=='missing':bad['coverage'].pop(IDS[1])
            elif change=='foreign':bad['coverage']['PRIVATE-FOREIGN']=bad['coverage'].pop(IDS[1])
            elif change=='unused':bad['classes'].append(copy.deepcopy(bad['classes'][0]))
            else:bad['coverage'][IDS[1]]=99
            with self.subTest(change=change),self.assertRaises(ValidationError):contract.model_validate(bad)

    def test_nonadjacent_choices_are_preserved_without_merging_across_other_classes(self):
        wire=partition_wire(proposal(),IDS);second=copy.deepcopy(wire['classes'][0]);second['kind']='general'
        wire['classes'].append(second);wire['coverage']={IDS[0]:0,IDS[1]:1,IDS[2]:0}
        # JSON key order is irrelevant; source order comes only from owned input.
        wire['coverage']=dict(reversed(list(wire['coverage'].items())))
        canonical=partition_contract(IDS).model_validate(wire).as_canonical();validate_unit(canonical,BLOCKS)
        self.assertEqual([row.block_id for row in canonical.classifications],IDS)
        self.assertEqual([row.kind for row in canonical.classifications],['other','general','other'])

    async def test_real_strict_transport_requires_every_primary_id_without_context_or_duplicates(self):
        contract=partition_contract(IDS);schema=source_contract(contract,BLOCKS)
        from services.edital_pipeline_worker import prompt
        content=prompt(SimpleNamespace(kind='inventory',scope_key='inventory'),{'manifest':SimpleNamespace(inventory=SimpleNamespace(roles=[])),'primary':BLOCKS,'context':[],'validation':{},'metadata':{}},contract)
        self.assertIn('Campos na raiz: roles, classes, coverage, facts, warnings.',content)
        self.assertIn('PARTIÇÃO TOTAL',content)
        allocation=schema['properties']['coverage'];self.assertEqual(allocation['required'],IDS)
        self.assertFalse(allocation['additionalProperties']);original=InventoryUnit.model_json_schema()
        response=json.dumps(partition_wire(proposal(),IDS));calls=[]
        def answer(request):
            body=json.loads(request.content);calls.append(body)
            actual=body['response_format']['json_schema']['schema']['properties']['coverage']
            self.assertEqual(actual['required'],IDS)
            return httpx.Response(200,json={'choices':[{'message':{'content':response}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
            router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['reasoning']]),providers={'groq':GroqProvider(client)})
            kwargs=dict(task='edital_extract',keys={'groq':'synthetic'},output_type=contract,strict_schema=True,transport_contract=schema)
            result=await router.generate(**kwargs);validate_unit(result.data.as_canonical(),BLOCKS)
            bad=partition_wire(proposal(),IDS);bad['coverage'].pop(IDS[1]);response=json.dumps(bad)
            with self.assertRaises(AIError):await router.generate(**kwargs)
            response=json.dumps(partition_wire(proposal(),IDS)).replace('"coverage": {','"coverage": {"p0001-b0001": 0,',1)
            with self.assertRaises(AIError) as error:await router.generate(**kwargs)
            self.assertEqual(error.exception.response_validation['stage'],'json_decode')
        self.assertEqual(len(calls),3);self.assertEqual(InventoryUnit.model_json_schema(),original)
