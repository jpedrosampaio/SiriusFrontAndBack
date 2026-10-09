import asyncio
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from cryptography.fernet import Fernet
from fastapi import HTTPException
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.credentials import Credentials, credential_fields, public_profile
from ai.registry import validate_call, TOOLS
from ai.actions import autonomy, Preferences
from ai.planning import plan_day
from ai.memory import MemoryInput, fingerprint
from ai.rag import chunks
from ai.automations import quiet


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def test_credentials_are_encrypted_and_never_serialized(self):
        with patch.dict(os.environ, {'AI_KEY_ENCRYPTION_KEY': Fernet.generate_key().decode()}):
            fields = credential_fields('groq', 'secret-1234')
            self.assertIsNone(fields['groq_api_key'])
            self.assertNotIn('secret-1234', fields['groq_api_key_encrypted'])
            public = public_profile(fields | {'password': 'password', 'gemini_api_key': 'legacy-5678'})
            self.assertTrue(public['has_groq_key'])
            self.assertEqual(public['gemini_key_last4'], '5678')
            self.assertFalse(any('api_key' in k for k in public))

    def test_key_encryption_roundtrip_requires_same_key(self):
        # Mongo plaintext migration is intentionally retired: this release resets data.
        # Persistent owner isolation is covered by test_postgres_runtime_auth.
        from ai.credentials import cipher
        with patch.dict(os.environ, {'AI_KEY_ENCRYPTION_KEY': Fernet.generate_key().decode()}):
            fields = credential_fields('gemini', 'new-secret')
            self.assertIsNone(fields['gemini_api_key'])
            self.assertEqual(cipher().decrypt(fields['gemini_api_key_encrypted'].encode()), b'new-secret')

    def test_new_secrets_require_encryption_but_deletion_does_not(self):
        with patch.dict(os.environ, {'AI_KEY_ENCRYPTION_KEY': ''}):
            with self.assertRaises(HTTPException): credential_fields('gemini', 'secret')
            self.assertIsNone(credential_fields('gemini', '')['gemini_api_key'])

    def test_tool_arguments_cannot_supply_user_or_negative_money(self):
        valid = {'amount': 48, 'category': 'Alimentação', 'date': '2026-09-26'}
        self.assertEqual(validate_call('record_expense', valid)['amount'], '48')
        for args in (valid | {'user_id': 'bob'}, valid | {'amount': -48}, valid | {'amount': float('nan')}, valid | {'date': '2026-99-99'}):
            with self.assertRaises(ValueError): validate_call('record_expense', args)
        with self.assertRaises(ValueError): validate_call('delete_all', {})

    def test_all_profiles_require_confirmation_for_money(self):
        for profile in ('conservative', 'balanced', 'proactive'):
            self.assertIn(autonomy(TOOLS['record_expense'], Preferences(profile=profile)), ('PROPOSE_ONLY', 'CONFIRM_REQUIRED'))
        self.assertEqual(autonomy(TOOLS['record_expense'], Preferences(blocked_tools=['record_expense'])), 'BLOCKED')

    def test_literal_multi_intent_produces_two_previews_without_a_model(self):
        from ai.agent import simple_proposals
        message = 'Registre um gasto de R$ 48 com alimentação e 50 minutos de estudo de Direito Constitucional'
        notebooks = [{'notebook_id': 'mine', 'name': 'Direito Constitucional'}]
        calls = simple_proposals(message, notebooks)
        self.assertEqual([c.name for c in calls], ['record_expense', 'record_study_session'])
        self.assertEqual(calls[0].arguments['amount'], '48')
        self.assertEqual(calls[1].arguments['notebook_id'], 'mine')
        self.assertEqual(simple_proposals('Exemplo: ' + message, notebooks), [])
        self.assertEqual(len(simple_proposals(message, [])), 1)

    def test_planner_respects_capacity_fixed_intervals_and_completed_tasks(self):
        tasks = [{'task_id': 'a', 'title': 'A', 'priority': 'high', 'duration_minutes': 60}, {'task_id': 'b', 'title': 'B', 'duration_minutes': 90}, {'task_id': 'c', 'completed': True}]
        result = plan_day(tasks, [{'date': '2026-09-26', 'start_minute': 510, 'end_minute': 600}], '2026-09-26', 480, 720, 90, now=datetime.fromisoformat('2026-09-26T08:00:00-03:00'))
        self.assertEqual([(b['start_minute'], b['end_minute']) for b in result['blocks']], [(600, 660)])
        self.assertEqual(len(result['unscheduled']), 1)
        self.assertEqual(result['remaining_minutes'], 30)

    def test_planner_derives_available_time_without_hidden_budget(self):
        result = plan_day([{'task_id':'a','title':'Estimate'}, {'task_id':'b','completed':True},
            {'task_id':'c','duration_minutes':200}], [{'date':'2026-09-26','start_minute':510,'end_minute':600}],
            '2026-09-26',480,720, now=datetime.fromisoformat('2026-09-26T08:00:00-03:00'))
        self.assertEqual(result['available_minutes'],150)
        self.assertEqual(result['budget_minutes'],150)
        self.assertEqual(result['blocks'][0]['duration_minutes'],30)
        self.assertTrue(result['blocks'][0]['duration_estimated'])
        self.assertEqual(len(result['unscheduled']),1)

    async def test_memory_fingerprint_normalizes_case_and_spacing(self):
        self.assertEqual(fingerprint(' No reminders '), fingerprint('no REMINDERS'))


    def test_chunks_retain_page_and_quiet_hours_cross_midnight(self):
        row = list(chunks([{'page': 7, 'text': 'Direito constitucional ' * 100}]))
        self.assertGreater(len(row), 1)
        self.assertTrue(all(r['page'] == 7 for r in row))
        self.assertTrue(quiet(datetime(2026, 9, 26, 23), 22, 8))
        self.assertFalse(quiet(datetime(2026, 9, 26, 12), 22, 8))

    async def test_independent_verifier_keeps_valid_bounded_json_and_rejects_false_quote(self):
        import json
        from ai.edital_verifier import verify, Verification
        payload = {'findings': [{'cargo': 'Analista', 'field': 'vagas', 'status': 'explicit', 'page': 1, 'quote': 'trecho inventado', 'explanation': 'fake'}]}
        router = SimpleNamespace(generate=AsyncMock(return_value=SimpleNamespace(data=Verification.model_validate(payload), provider='groq', model='fake')))
        result = await verify(router, {'groq': 'fake'}, 'alice', [{'nome': 'Analista', 'disciplinas': [{'nome': 'Direito', 'topicos': ['x'*50000]}]}]*50, [{'page': 1, 'text': 'Conteúdo programático '+ 'Direito '*10000}])
        prompt = router.generate.call_args.kwargs['prompt']
        self.assertLess(len(prompt), 15000)
        self.assertIn('pages', json.loads(prompt))
        self.assertEqual(result['findings'], [])
        self.assertEqual(router.generate.call_args.kwargs['keys'], {'groq': 'fake'})
