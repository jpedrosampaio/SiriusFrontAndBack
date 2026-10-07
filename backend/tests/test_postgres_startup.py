import os
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from db.engine import database_url


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class PostgresStartup(unittest.TestCase):
    def test_empty_database_migrations_lifespan_and_no_mongo(self):
        base=database_url().set(drivername='postgresql')
        self.assertIn(base.host,('localhost','127.0.0.1','::1'),'Never create smoke databases in Neon')
        # Disposable testing only; use a fresh unique database, never clear current data.
        self.assertIn('test',base.database.lower())
        name='sirius_smoke_'+uuid4().hex
        admin=base.set(database='postgres').render_as_string(hide_password=False)
        root=Path(__file__).resolve().parents[1]
        env=dict(os.environ,DATABASE_URL=base.set(database=name).render_as_string(hide_password=False),PYTHON_DOTENV_DISABLED='1',
            TELEGRAM_BOT_TOKEN='',TELEGRAM_BOT_WEBHOOK_SECRET='',LOCAL_DEVELOPMENT_STORAGE_DIR='',AI_AUTOMATIONS_ENABLED='true')
        for key in ('MONGO_URL','DB_NAME','DATABASE_URL_DIRECT'):env.pop(key,None)
        with psycopg.connect(admin,autocommit=True) as connection:
            connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            for args in ([sys.executable,'-m','alembic','upgrade','head'],[sys.executable,'-m','alembic','check'],[sys.executable,'scripts/smoke_postgres.py']):
                result=subprocess.run(args,cwd=root,env=env,capture_output=True,text=True,timeout=120,encoding='utf-8',errors='replace')
                self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-10000:])
            self.assertIn('PASS: empty PostgreSQL',result.stdout)
        finally:
            self.assertTrue(name.startswith('sirius_smoke_') and len(name)==45)
            with psycopg.connect(admin,autocommit=True) as connection:
                connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
