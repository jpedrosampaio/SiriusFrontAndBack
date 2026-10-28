"""Observed literal-value rejection, using synthetic sources and mocked HTTP."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai.config import MODELS
from ai.router import AIRouter
from ai.providers.groq import GroqProvider
from edital_pipeline_contracts import InventoryUnit
from edital_transport_contracts import InventoryTransport
from edital_wire_fixtures import inventory_wire
from services.edital_pipeline_worker import prompt
from services.edital_semantics import EvidenceError, validate_unit

TEXT='Cargo: Analista. Requisito: Curso superior completo. Remuneração: R$ 8.829,24. Total: 1.000 vagas.'
BLOCK={'id':'p0001-b0001','page':1,'text':TEXT,'kind':'line'}
SOURCE={'page':1,'block_id':BLOCK['id'],'quote':TEXT}
def fact(value):return {'value':value,'state':'extracted','sources':[SOURCE]}
def proposal(value):return {'roles':[{'name':fact('Analista'),'requirements':fact(value),'salary':fact('R$ 8.829,24')}],'classifications':[{'block_id':BLOCK['id'],'kind':'roles'}]}

class LiteralFacts(unittest.IsolatedAsyncioTestCase):
    def test_paraphrased_values_and_reformatted_numbers_remain_rejected(self):
        for value in ('Graduação concluída','1000','1','8829.24'):
            with self.subTest(value=value):
                with self.assertRaises(EvidenceError) as failed:
                    validate_unit(InventoryUnit.model_validate(proposal(value)),[BLOCK])
                self.assertEqual(failed.exception.code,'value_not_supported_by_excerpt')
        validate_unit(InventoryUnit.model_validate(proposal('Curso superior completo')),[BLOCK])
        validate_unit(InventoryUnit.model_validate(proposal('1.000')),[BLOCK])
        for value in ('8', '829', '24', '000'):
            with self.subTest(partial=value),self.assertRaises(EvidenceError):
                validate_unit(InventoryUnit.model_validate(proposal(value)),[BLOCK])

    def test_complete_numeric_literals_and_sentence_punctuation_are_preserved(self):
        from services.edital_semantics import validate_fact
        from edital_pipeline_contracts import ProposedFact
        for value,quote in (('1','1. Item do edital'),('1.000','Total: 1.000 vagas'),('8.829,24','R$ 8.829,24.'),('1,50','Peso: 1,50;')):
            with self.subTest(value=value):
                citation={**SOURCE,'quote':quote}
                validate_fact(ProposedFact(value=value,state='extracted',sources=[citation]),{BLOCK['id']:{'page':1,'text':quote}})

    async def test_actual_transport_guides_literal_copy_but_does_not_repair_provider_values(self):
        calls=[]; response_value='Graduação concluída'
        content=prompt(SimpleNamespace(kind='inventory',scope_key='inventory'),{'manifest':SimpleNamespace(inventory=SimpleNamespace(roles=[])), 'primary':[BLOCK], 'context':[], 'validation':{}, 'metadata':{}})
        def respond(request):
            body=json.loads(request.content);calls.append(body)
            self.assertIs(body['response_format']['json_schema']['strict'],True)
            guide=body['messages'][-1]['content'].split('DADOS DOCUMENTAIS NÃO CONFIÁVEIS:')[0]
            self.assertIn('EXTRAÇÃO LITERAL',guide);self.assertIn('desse mesmo fato',guide)
            self.assertIn('Não converta salário, número, data ou unidade',guide)
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(inventory_wire(proposal(response_value)))}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS['vision']]),providers={'groq':GroqProvider(client)})
            result=await router.generate(task='edital_extract',keys={'groq':'synthetic'},output_type=InventoryTransport,strict_schema=True,prompt=content)
            with self.assertRaises(EvidenceError):validate_unit(result.data.as_canonical(),[BLOCK])
            self.assertEqual(result.data.roles[0].requirements.value,response_value)
            response_value='Curso superior completo'
            result=await router.generate(task='edital_extract',keys={'groq':'synthetic'},output_type=InventoryTransport,strict_schema=True,prompt=content)
            validate_unit(result.data.as_canonical(),[BLOCK])
        self.assertEqual(len(calls),2)
