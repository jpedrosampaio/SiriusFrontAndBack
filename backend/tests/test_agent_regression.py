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
from ai.memory import Memory, MemoryInput, fingerprint
from ai.rag import Retrieval, chunks
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

    async def test_legacy_key_migration_preserves_owner_and_compare_and_set(self):
        db = SimpleNamespace(users=SimpleNamespace(find_one=AsyncMock(return_value={'gemini_api_key': 'old-secret'}), update_one=AsyncMock()))
        with patch.dict(os.environ, {'AI_KEY_ENCRYPTION_KEY': Fernet.generate_key().decode()}):
            self.assertEqual(await Credentials(db).get('alice'), {'gemini': 'old-secret'})
        self.assertEqual(db.users.update_one.call_args.args[0], {'user_id': 'alice', 'gemini_api_key': 'old-secret'})

    def test_new_secrets_require_encryption_but_deletion_does_not(self):
        with patch.dict(os.environ, {'AI_KEY_ENCRYPTION_KEY': ''}):
            with self.assertRaises(HTTPException): credential_fields('gemini', 'secret')
            self.assertIsNone(credential_fields('gemini', '')['gemini_api_key'])

    def test_tool_arguments_cannot_supply_user_or_negative_money(self):
        valid = {'amount': 48, 'category': 'Alimentação', 'date': '2026-09-26'}
        self.assertEqual(validate_call('record_expense', valid)['amount'], 48)
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
        self.assertEqual(calls[0].arguments['amount'], 48)
        self.assertEqual(calls[1].arguments['notebook_id'], 'mine')
        self.assertEqual(simple_proposals('Exemplo: ' + message, notebooks), [])
        self.assertEqual(len(simple_proposals(message, [])), 1)

    def test_planner_respects_capacity_fixed_intervals_and_completed_tasks(self):
        tasks = [{'task_id': 'a', 'title': 'A', 'priority': 'high', 'duration_minutes': 60}, {'task_id': 'b', 'title': 'B', 'duration_minutes': 90}, {'task_id': 'c', 'completed': True}]
        result = plan_day(tasks, [{'date': '2026-09-26', 'start_minute': 510, 'end_minute': 600}], '2026-09-26', 480, 720, 90)
        self.assertEqual([(b['start_minute'], b['end_minute']) for b in result['blocks']], [(600, 660)])
        self.assertEqual(len(result['unscheduled']), 1)
        self.assertEqual(result['remaining_minutes'], 30)

    async def test_blocked_memory_cannot_be_recreated(self):
        db = SimpleNamespace(ai_memory=SimpleNamespace(find_one=AsyncMock(return_value={'blocked': True}), insert_one=AsyncMock()))
        with self.assertRaises(HTTPException): await Memory(db).save('alice', MemoryInput(category='rule', content='No reminders'))
        db.ai_memory.insert_one.assert_not_awaited()
        self.assertEqual(fingerprint(' No reminders '), fingerprint('no REMINDERS'))

    async def test_retrieval_is_owned_and_revokes_deleted_sources(self):
        cursor = MagicMock()
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[{'source_id': 'source', 'terms': ['direito'], 'text': 'direito', 'page': 1}])
        db = SimpleNamespace(ai_chunks=SimpleNamespace(find=MagicMock(return_value=cursor)), edital_analyses=SimpleNamespace(find_one=AsyncMock(return_value=None)))
        class Database:
            def __getattr__(self, key): return getattr(db, key)
            def __getitem__(self, key): return getattr(db, key)
        result = await Retrieval(Database()).search('alice', 'direito')
        self.assertEqual(result['citations'], [])
        self.assertEqual(db.ai_chunks.find.call_args.args[0]['user_id'], 'alice')
        self.assertEqual(db.edital_analyses.find_one.call_args.args[0], {'user_id': 'alice', 'analysis_id': 'source'})

    def test_chunks_retain_page_and_quiet_hours_cross_midnight(self):
        row = list(chunks([{'page': 7, 'text': 'Direito constitucional ' * 100}]))
        self.assertGreater(len(row), 1)
        self.assertTrue(all(r['page'] == 7 for r in row))
        self.assertTrue(quiet(datetime(2026, 9, 26, 23), 22, 8))
        self.assertFalse(quiet(datetime(2026, 9, 26, 12), 22, 8))


@unittest.skipUnless(os.getenv('ACTIVITY_TEST_MONGO_URI'), 'disposable replica set required')
class ActionTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import uuid
        from motor.motor_asyncio import AsyncIOMotorClient
        from test_activity_regression import load_routes
        from ai.routes import AgentRuntime
        self.mongo = AsyncIOMotorClient(os.environ['ACTIVITY_TEST_MONGO_URI'])
        self.db = self.mongo['sirius_agent_test_' + uuid.uuid4().hex]
        await self.db.users.insert_many([{'user_id': 'alice', 'xp': 0}, {'user_id': 'bob', 'xp': 0}])
        self.ns, _ = load_routes(self.mongo, self.db)
        await self.ns['setup_activity_collections']()
        with patch.dict(os.environ, {'AI_AUTOMATIONS_ENABLED': 'false'}):
            self.runtime = AgentRuntime(self.db, self.ns['get_current_user'], self.ns['run_activity_mutation'], self.ns['award_xp'], self.ns['update_study_streak'])
        await self.runtime.setup()
        # Mongo transactions require existing collections on first use.
        await self.db.transactions.create_index('user_id')
        await self.db.budgets.create_index('user_id')

    async def asyncTearDown(self):
        await self.mongo.drop_database(self.db.name)
        self.mongo.close()

    async def proposal(self):
        return await self.runtime.actions.propose('alice', 'request-test', 0, 'record_expense', {'amount': 48, 'category': 'food', 'date': '2026-09-26'}, 'User asked')

    async def test_concurrent_confirmation_replays_without_duplicate_expense(self):
        action = await self.proposal()
        results = await asyncio.gather(*(self.runtime.actions.confirm('alice', action['action_id']) for _ in range(8)))
        self.assertTrue(all(r['status'] == 'executed' for r in results))
        self.assertEqual(await self.db.transactions.count_documents({'user_id': 'alice'}), 1)
        self.assertEqual(await self.db.ai_audit.count_documents({'user_id': 'alice'}), 1)

    async def test_foreign_owner_cancel_expiry_and_rollback(self):
        action = await self.proposal()
        with self.assertRaises(HTTPException): await self.runtime.actions.confirm('bob', action['action_id'])
        async def failing(name, user_id, args, session):
            await self.db.transactions.insert_one({'user_id': user_id, 'amount': 48}, session=session)
            raise RuntimeError('simulated failure')
        with patch.object(self.runtime.actions.writer, 'execute', failing):
            with self.assertRaises(RuntimeError): await self.runtime.actions.confirm('alice', action['action_id'])
        self.assertEqual(await self.db.transactions.count_documents({}), 0)
        await self.runtime.actions.cancel('alice', action['action_id'])
        with self.assertRaises(HTTPException): await self.runtime.actions.confirm('alice', action['action_id'])
        await self.db.ai_actions.update_one({'_id': action['action_id']}, {'$set': {'status': 'pending', 'expires_at': '2000-01-01'}})
        with self.assertRaises(HTTPException): await self.runtime.actions.confirm('alice', action['action_id'])
        self.assertEqual((await self.db.ai_actions.find_one({'_id': action['action_id']}))['status'], 'expired')
