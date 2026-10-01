import asyncio
import os
import sys
import unittest
from uuid import uuid4
from db.engine import dispose_engine
from db.session import unit_of_work
from db.models.files import FileRecord,RagSource
from db.repositories.identity import IdentityRepository
from db.repositories.rag import RagRepository

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true','Disposable PostgreSQL required')
class PostgresRag(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await dispose_engine()

    async def test_owner_hash_refresh_and_delete(self):
        async with unit_of_work() as session:
            identity = IdentityRepository(session)
            alice = (await identity.create(email=f'{uuid4()}@example.test',name='Alice',password_hash='test-only')).id
            bob = (await identity.create(email=f'{uuid4()}@example.test',name='Bob',password_hash='test-only')).id
            file = FileRecord(user_id=alice,storage_provider='metadata_only',filename='edital.pdf',mime_type='application/pdf',size_bytes=100,sha256='f'*64)
            session.add(file)
            await session.flush()
            source = RagSource(user_id=alice,file_id=file.id,generation='',source_type='attachment')
            session.add(source)
            await session.flush()
            sid = source.id
            chunks = [{'text':'Direito constitucional','hash':'a'*64,'terms':['direito','constitucional'],'page':1}]
            repo = RagRepository(session)
            self.assertFalse((await repo.replace_chunks(alice,sid,'v1',chunks))['unchanged'])
            self.assertTrue((await repo.replace_chunks(alice,sid,'v1',chunks))['unchanged'])
            self.assertEqual(len(await repo.lexical_search(alice,['direito'])),1)
            self.assertEqual(await repo.lexical_search(bob,['direito']),[])
            self.assertEqual(await repo.lexical_search(bob,['direito'],sid),[])
            await repo.remove_source(alice,sid)
            self.assertEqual(await repo.lexical_search(alice,['direito']),[])
