"""Exercise the real server routes with Mongo unreachable, not a substitute app."""
import asyncio
import os
import sys
import unittest
from uuid import uuid4,UUID
from unittest.mock import patch
from cryptography.fernet import Fernet
from httpx import ASGITransport,AsyncClient
from db.engine import dispose_engine
from db.session import unit_of_work
from db.repositories.identity import IdentityRepository
from ai.credentials import Credentials

if sys.platform=='win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeAuth(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await dispose_engine()

    async def test_actual_server_identity_profile_and_credentials(self):
        # During the domain-by-domain cutover, importing unported domains still
        # constructs Motor. No Mongo server is running and auth must never use it.
        with patch.dict(os.environ,{'MONGO_URL':'mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=10','DB_NAME':'unavailable',
                'AI_KEY_ENCRYPTION_KEY':Fernet.generate_key().decode()}):
            import server
            async with AsyncClient(transport=ASGITransport(server.app),base_url='https://sirius.test') as client:
                data={'email':f'{uuid4()}@example.test','name':'Runtime','password':'runtime-password'}
                registered=await client.post('/api/auth/register',json=data)
                self.assertEqual(registered.status_code,200,registered.text)
                uid=UUID(registered.json()['user']['user_id'])
                profile=await client.patch('/api/auth/profile',json={'name':'Updated','birth_date':'1990-03-10',
                    'timezone':'Asia/Tokyo','gemini_api_key':'secret-gemini-1234'})
                self.assertEqual(profile.status_code,200,profile.text)
                self.assertEqual(profile.json()['gemini_key_last4'],'1234')
                self.assertNotIn('secret-gemini',profile.text)
                me=await client.get('/api/auth/me')
                self.assertEqual(me.json()['name'],'Updated')
                self.assertEqual(me.json()['timezone'],'Asia/Tokyo')
                self.assertEqual((await client.get('/api/auth/birthday-check')).status_code,200)
                result=await client.post('/api/auth/upload-picture',files={'file':('photo.png',b'png','image/png')})
                self.assertEqual(result.status_code,503)
                self.assertEqual(await Credentials().get(uid),{'gemini':'secret-gemini-1234'})
                async with unit_of_work() as session:
                    repo=IdentityRepository(session)
                    other=(await repo.create(email=f'{uuid4()}@example.test',name='Other',password_hash='test-only')).id
                    stored=await repo.by_id(uid)
                    self.assertNotIn('secret-gemini',str(stored.credentials))
                self.assertEqual(await Credentials().get(other),{})
                await Credentials().save(uid,'gemini','')
                self.assertEqual(await Credentials().get(uid),{})
                await client.post('/api/auth/logout')
                self.assertEqual((await client.get('/api/auth/me')).status_code,401)
