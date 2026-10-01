import asyncio
import os
import sys
import unittest
from uuid import uuid4
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from db.engine import dispose_engine
from services.auth_routes import router

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class PostgresAuth(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await dispose_engine()

    async def test_first_registration_login_logout(self):
        app = FastAPI()
        app.include_router(router, prefix='/api')
        async with AsyncClient(transport=ASGITransport(app), base_url='https://sirius.test') as client:
            self.assertEqual((await client.get('/api/auth/me')).status_code, 401)
            body = {'name': 'New user', 'email': f'{uuid4()}@example.test', 'password': 'test-password'}
            registered = await client.post('/api/auth/register', json=body)
            self.assertEqual(registered.status_code, 200, registered.text)
            self.assertIn('HttpOnly', registered.headers['set-cookie'])
            self.assertIn('Secure', registered.headers['set-cookie'])
            profile = (await client.get('/api/auth/me')).json()
            self.assertEqual(profile['xp'], 0)
            self.assertNotIn('password_hash', profile)
            self.assertNotIn('credentials', profile)
            duplicate = await client.post('/api/auth/register', json={**body, 'email': body['email'].upper()})
            self.assertEqual(duplicate.status_code, 400)
            await client.post('/api/auth/logout')
            self.assertEqual((await client.get('/api/auth/me')).status_code, 401)
            self.assertEqual((await client.post('/api/auth/login', json={**body, 'password': 'wrong'})).status_code, 401)
            login = await client.post('/api/auth/login', json=body)
            self.assertEqual(login.status_code, 200)
            token = login.json()['session_token']
            client.cookies.clear()
            self.assertEqual((await client.get('/api/auth/me', headers={'Authorization': 'Bearer '+token})).status_code, 200)
            await client.post('/api/auth/logout', headers={'Authorization': 'Bearer '+token})
            self.assertEqual((await client.get('/api/auth/me', headers={'Authorization': 'Bearer '+token})).status_code, 401)
