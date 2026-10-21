"""Bounded public diagnostics for rejected HTTP requests, never live inference."""
import json
import sys
import unittest
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.provider_diagnostics import rejection_metadata, safe_rejection
from ai.providers.gemini import GeminiProvider
from ai.router import AIRouter
from ai.types import AIError
from edital_pipeline_contracts import InventoryUnit


class RejectionMetadata(unittest.TestCase):
    def test_public_field_templates_and_schema_paths_are_allowlisted(self):
        cases = [
            ('Invalid JSON payload received. Unknown name "store": Cannot find field.', 'store', 'unknown_field'),
            ('Unknown name "response_format" at "generation_config": Cannot find field.', 'generationConfig.responseFormat', 'unknown_field'),
            ('Invalid value at generation_config.max_output_tokens', 'generationConfig.maxOutputTokens', 'invalid_value'),
        ]
        for message, field, category in cases:
            with self.subTest(field=field):
                self.assertEqual(rejection_metadata({'code': 400, 'status': 'INVALID_ARGUMENT', 'message': message}),
                    {'code': 400, 'status': 'INVALID_ARGUMENT', 'category': category, 'fields': [field]})
        result = rejection_metadata({'message': 'Request contains an invalid argument.', 'details': [
            {'fieldViolations': [{'field': 'generation_config.response_format.text.schema.properties.PRIVATE',
                                 'description': 'PRIVATE secret body'}]}]})
        self.assertEqual(result, {'category': 'unspecified', 'fields': ['generationConfig.responseFormat.text.schema']})

    def test_private_and_malformed_provider_values_never_escape(self):
        private = 'PRIVATE-PDF-PROMPT-KEY'
        payload = {'code': True, 'status': private, 'message': private + ' Unknown name "PRIVATE_KEY"',
            'details': [None, {'fieldViolations': [None, {'field': private, 'description': private}]}]}
        self.assertEqual(rejection_metadata(payload), {'category': 'unknown_field', 'fields': []})
        for error in (None, [], private, {'message': {}, 'details': {}}, {'message': None, 'details': [None]}):
            self.assertNotIn(private, json.dumps(rejection_metadata(error)))
        self.assertEqual(safe_rejection({'code': 400, 'status': 'INVALID_ARGUMENT', 'category': 'unknown_field',
            'fields': ['store', private, {}, 'generationConfig'], 'message': private, 'key': private}),
            {'code': 400, 'status': 'INVALID_ARGUMENT', 'category': 'unknown_field', 'fields': ['generationConfig', 'store']})
        self.assertEqual(safe_rejection({'fields': ['store'] * 10000})['fields'], ['store'])
        self.assertEqual(rejection_metadata({'message': 'a' * 4096 + ' Unknown name "store"'})['fields'], [])

    def test_generic400_stays_unknown_instead_of_fabricating_rejected_parameter(self):
        metadata = rejection_metadata({'code': 400, 'status': 'INVALID_ARGUMENT',
            'message': 'Request contains an invalid argument.'})
        self.assertEqual(metadata['category'], 'unspecified')
        self.assertEqual(metadata['fields'], [])


class RejectionTransport(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_reaches_logs_and_rejection_cache_without_retries_or_private_text(self):
        calls = []
        private = 'PRIVATE-PDF-PROMPT-KEY'
        def transport(request):
            calls.append(request)
            return httpx.Response(400, json={'error': {'code': 400, 'status': 'INVALID_ARGUMENT',
                'message': 'Invalid JSON payload received. Unknown name "store": Cannot find field. ' + private,
                'details': [{'fieldViolations': [{'field': 'store', 'description': private}]}]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            router = AIRouter(providers={'gemini': GeminiProvider(client)})
            with self.assertLogs(level='INFO') as captured:
                with self.assertRaises(AIError) as failed:
                    await router.generate(task='edital_extract', keys={'gemini': private}, prompt=private, output_type=InventoryUnit)
            error = failed.exception
            self.assertEqual(error.provider_rejection, {'code': 400, 'status': 'INVALID_ARGUMENT',
                'category': 'unknown_field', 'fields': ['store']})
            self.assertEqual(error.incompatibility, 'request_rejected') # routing is unchanged
            self.assertEqual(error.request_format, 'gemini_response_format')
            self.assertIn('provider_rejection=', ' '.join(captured.output))
            self.assertNotIn(private, ' '.join(captured.output))
            self.assertNotIn(private, str(error))
            with self.assertRaises(AIError) as cached:
                await router.generate(task='edital_extract', keys={'gemini': private}, prompt=private, output_type=InventoryUnit)
            self.assertEqual(cached.exception.provider_rejection, error.provider_rejection)
            self.assertIsNot(cached.exception.provider_rejection, error.provider_rejection)
            self.assertFalse(cached.exception.attempted)
            self.assertEqual(len(calls), 1)

