"""Round-trip only in an explicitly created disposable loopback database."""
import asyncio
import os
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
import psycopg
from psycopg import sql
from sqlalchemy import select
from db.engine import database_url, dispose_engine
from db.session import unit_of_work
from db.models.contests import ContestSource, ContestSourceVersion
from db.models.studies import StudyArea, StudyProgram
from db.repositories.identity import IdentityRepository

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class ContestMigration(unittest.IsolatedAsyncioTestCase):
    async def test_backfill_roundtrip_preserves_legacy_source(self):
        original=database_url()
        self.assertIn(original.host, ('localhost','127.0.0.1','::1'))
        name='sirius_radar_'+uuid4().hex
        admin_url=original.set(drivername='postgresql',database='postgres').render_as_string(hide_password=False)
        target=original.set(drivername='postgresql',database=name).render_as_string(hide_password=False)
        old={key:os.environ.get(key) for key in ('DATABASE_URL','DATABASE_URL_DIRECT')}
        await dispose_engine()
        with psycopg.connect(admin_url,autocommit=True) as admin:
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        async def migrate(*args):
            result=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','alembic',*args],
                cwd=Path(__file__).resolve().parents[1],env={**os.environ,'DATABASE_URL':target,'DATABASE_URL_DIRECT':target},
                capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
        try:
            await migrate('upgrade','head')
            os.environ['DATABASE_URL']=target;os.environ['DATABASE_URL_DIRECT']=target
            async with unit_of_work() as session:
                uid=(await IdentityRepository(session).create(email='migration@example.test',name='Migration',password_hash='test')).id
                area=StudyArea(user_id=uid,name='Area');session.add(area);await session.flush()
                program=StudyProgram(user_id=uid,area_id=area.id,name='Program');session.add(program);await session.flush()
                source=ContestSource(user_id=uid,program_id=program.id,url='https://orgao.gov.br/edital',url_hash='legacy',
                    title='Legacy',trust='OFFICIAL',provider='generic',terms_confirmed_at=datetime.now(timezone.utc),
                    next_poll=datetime.now(timezone.utc),snapshot='Original text',content_hash='original-hash')
                session.add(source);await session.flush();sid=source.id
            await dispose_engine()
            await migrate('downgrade','84d2a71ef309')
            await migrate('upgrade','head')
            await migrate('check')
            async with unit_of_work() as session:
                row=await session.get(ContestSource,sid)
                self.assertEqual((row.snapshot,row.content_hash,row.source_kind),('Original text','original-hash','unknown'))
                version=await session.scalar(select(ContestSourceVersion).where(ContestSourceVersion.source_id==sid))
                self.assertEqual(version.snapshot_text,'Original text')
                self.assertEqual(version.content_hash,'original-hash')
                self.assertTrue(version.details['legacy']);self.assertEqual(version.dates,[])
        finally:
            await dispose_engine()
            for key,value in old.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value
            assert name.startswith('sirius_radar_') and len(name)==45
            with psycopg.connect(admin_url,autocommit=True) as admin:
                admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
