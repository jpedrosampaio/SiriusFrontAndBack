"""Vendor-Discovery envelope checks and actual HTTP serialization, no live inference.

The published Discovery still declares legacy fields. Tests explicitly retain
that fact: a mock rejecting the old envelope cannot prove the historical 400.
"""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai.config import MODELS
from ai.providers.gemini import GeminiProvider
from ai.router import AIRouter
from ai.types import AIError
from test_edital_provider_regression import CASES

DISCOVERY=json.loads((Path(__file__).parent/'fixtures/gemini_generate_content_discovery.json').read_text(encoding='utf-8'))


def published_contract(value,schema='GenerateContentRequest'):
    """Resolve only populated request fields against the selected vendor snapshot."""
    if isinstance(schema,str):schema=DISCOVERY['schemas'][schema]
    if '$ref' in schema:return published_contract(value,schema['$ref'])
    kind=schema.get('type')
    if kind=='any':return
    if kind=='object':
        assert isinstance(value,dict),'object required'
        assert not value.keys()-schema['properties'].keys(),'unknown request field'
        for name,item in value.items():published_contract(item,schema['properties'][name])
    elif kind=='array':
        assert isinstance(value,list),'array required'
        for item in value:published_contract(item,schema['items'])
    elif kind=='string':assert isinstance(value,str),'string required'
    elif kind=='integer':assert type(value) is int,'integer required'
    elif kind=='boolean':assert type(value) is bool,'boolean required'
    else:raise AssertionError('unhandled Discovery shape')
    if 'enum' in schema:assert value in schema['enum'],'unsupported enum value'


class GenerateContentWire(unittest.IsolatedAsyncioTestCase):
    async def test_minimal_and_four_real_contracts_on_both_models_match_published_envelope(self):
        minimal={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
        for model_name in ('flash','lite'):
            for output,payload in [(None,{'ok':True}),*CASES]:
                with self.subTest(model=model_name,contract=output.__name__ if output else 'minimal'):
                    captured=[]
                    def transport(request):
                        body=json.loads(request.content);published_contract(body);captured.append(body)
                        self.assertEqual(str(request.url),f'https://generativelanguage.googleapis.com/v1beta/models/{MODELS[model_name].name}:generateContent')
                        self.assertEqual(request.headers['x-goog-api-key'],'synthetic-only')
                        config=body['generationConfig'];self.assertEqual(set(config),{'responseFormat','maxOutputTokens'})
                        self.assertEqual(config['responseFormat']['text']['mimeType'],'APPLICATION_JSON')
                        self.assertFalse(body['store']);self.assertEqual(config['maxOutputTokens'],12000)
                        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(payload)}]}}]})
                    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                        router=AIRouter(settings=SimpleNamespace(route=lambda task:[MODELS[model_name]]),providers={'gemini':GeminiProvider(client)})
                        result=await router.generate(task='edital_extract',keys={'gemini':'synthetic-only'},prompt='Synthetic documentary source',
                            system='Synthetic extraction instruction',output_type=output,schema=minimal if output is None else None,max_tokens=12000)
                    self.assertEqual(result.data,output.model_validate(payload) if output else payload)
                    # Discovery does not establish that legacy requests fail.
                    legacy=copy.deepcopy(captured[0]);config=legacy['generationConfig']
                    config['responseJsonSchema']=config.pop('responseFormat')['text']['schema'];config['responseMimeType']='application/json'
                    published_contract(legacy)
                    wrong_mime=copy.deepcopy(captured[0]);wrong_mime['generationConfig']['responseFormat']['text']['mimeType']='application/json'
                    with self.assertRaisesRegex(AssertionError,'unsupported enum'):published_contract(wrong_mime)

    async def test_400_diagnostics_preserve_wire_shape_without_private_data_or_second_attempt(self):
        private='PRIVATE-SOURCE-PROMPT-KEY';calls=[]
        def transport(request):
            body=json.loads(request.content);published_contract(body);calls.append(body)
            return httpx.Response(400,json={'error':{'message':'Invalid value at generation_config.response_format.text.mime_type '+private}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            router=AIRouter(providers={'gemini':GeminiProvider(client)})
            with self.assertLogs(level='INFO') as logs:
                with self.assertRaises(AIError) as failed:
                    await router.generate(task='edital_extract',keys={'gemini':private},prompt=private,output_type=CASES[0][0],
                        diagnostic_context={'stage':'inventory','unit_id':'11111111-1111-4111-8111-111111111111'})
            error=failed.exception
            self.assertEqual(error.http_status,400);self.assertEqual(error.incompatibility,'format_mime')
            self.assertEqual(error.request_format,'gemini_response_format');self.assertEqual(len(error.schema_sha256),64)
            self.assertGreater(error.schema_bytes,0);self.assertEqual(len(calls),1)
            self.assertIn(error.schema_sha256,' '.join(logs.output));self.assertIn(error.reference,' '.join(logs.output))
            self.assertNotIn(private,' '.join(logs.output))
            with self.assertRaises(AIError) as cached:
                await router.generate(task='edital_extract',keys={'gemini':private},prompt=private,output_type=CASES[0][0])
            self.assertFalse(cached.exception.attempted);self.assertEqual(cached.exception.schema_sha256,error.schema_sha256)
            self.assertEqual(len(calls),1)

    async def test_structured_format_does_not_leak_into_plain_chat_or_tools(self):
        for kwargs in ({},{'tools':[{'name':'now','description':'Read the time','parameters':{'type':'object'}}]}):
            def transport(request):
                body=json.loads(request.content)
                self.assertEqual(set(body['generationConfig']),{'maxOutputTokens'})
                return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'Synthetic answer'}]}}]})
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                await AIRouter(providers={'gemini':GeminiProvider(client)}).generate(task='assistant_chat',
                    keys={'gemini':'synthetic-only'},prompt='Synthetic question',**kwargs)
