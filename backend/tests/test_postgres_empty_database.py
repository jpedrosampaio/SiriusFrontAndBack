"""Build an isolated empty database, then register and exercise HTTP authentication."""
import asyncio
import os
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from fastapi import FastAPI
from httpx import ASGITransport,AsyncClient
from db.engine import database_url,dispose_engine
from services.auth_routes import router
from db.health import router as health_router

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true','Disposable PostgreSQL required')
class EmptyDatabase(unittest.IsolatedAsyncioTestCase):
    async def test_alembic_then_first_user(self):
        original = database_url()
        self.assertIn(original.host,('localhost','127.0.0.1','::1'),'Never create databases in Neon during CI')
        name = 'sirius_empty_'+uuid4().hex
        admin_url = original.set(drivername='postgresql',database='postgres').render_as_string(hide_password=False)
        target = original.set(drivername='postgresql',database=name).render_as_string(hide_password=False)
        old_url,old_direct = os.environ.get('DATABASE_URL'),os.environ.get('DATABASE_URL_DIRECT')
        await dispose_engine()
        with psycopg.connect(admin_url,autocommit=True) as admin:
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            env = {**os.environ,'DATABASE_URL':target,'DATABASE_URL_DIRECT':target}
            result = await asyncio.to_thread(subprocess.run,[sys.executable,'-m','alembic','upgrade','head'],
                cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            os.environ['DATABASE_URL'],os.environ['DATABASE_URL_DIRECT'] = target,target
            app = FastAPI()
            app.include_router(router,prefix='/api')
            app.include_router(health_router)
            async with AsyncClient(transport=ASGITransport(app),base_url='https://sirius.test') as client:
                self.assertEqual((await client.get('/health/ready')).status_code,200)
                registered = await client.post('/api/auth/register',json={'name':'First user','email':'first@example.test','password':'empty-db-test'})
                self.assertEqual(registered.status_code,200,registered.text)
                self.assertEqual((await client.get('/api/auth/me')).json()['xp'],0)
                await client.post('/api/auth/logout')
                self.assertEqual((await client.get('/api/auth/me')).status_code,401)
        finally:
            await dispose_engine()
            for key,previous in [('DATABASE_URL',old_url),('DATABASE_URL_DIRECT',old_direct)]:
                if previous is None:
                    os.environ.pop(key,None)
                else:
                    os.environ[key] = previous
            # Only the exact database created by this test can be removed.
            assert name.startswith('sirius_empty_') and len(name) == 45
            with psycopg.connect(admin_url,autocommit=True) as admin:
                admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
