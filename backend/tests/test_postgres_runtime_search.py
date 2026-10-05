import os
import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from uuid import UUID
from unittest.mock import patch
from db.session import unit_of_work
from db.models.planning import Task,Goal
from db.models.finance import FinancialTransaction
from db.models.studies import StudyNote,StudyTarget,StudyProgram,Notebook
import test_postgres_runtime_dashboard as setup
import test_postgres_runtime_catalog as catalog


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeSearch(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeDashboard.ok
    asyncTearDown=setup.RuntimeDashboard.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeDashboard.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        p=patch('services.global_search.account',account);p.start();self.patches.append(p)

    async def test_owned_literal_search_caps_results_and_excludes_archived(self):
        async with unit_of_work() as session:
            session.add_all([Task(user_id=self.uid,title='Needle '+str(i),date=self.today,xp_reward=5) for i in range(8)])
            session.add_all([Task(user_id=self.uid,title='Needle archived',date=self.today,xp_reward=5,archived_at=datetime.now(timezone.utc)),
                Task(user_id=self.bob,title='Needle foreign',date=self.today,xp_reward=5),
                Task(user_id=self.uid,title='Special %_ literal',date=self.today,xp_reward=5),
                FinancialTransaction(user_id=self.uid,date=self.today,type='expense',amount=Decimal('48.01'),category='food',description='Needle expense'),
                Goal(user_id=self.uid,title='Needle goal',target_date=self.today,progress=50)])
        results=self.ok(await self.http.get('/api/search/global',params={'q':'NEEDLE'}))['results']
        self.assertEqual(len([r for r in results if r['type']=='task']),5)
        self.assertFalse(any('foreign' in r['title'] or 'archived' in r['title'] for r in results))
        self.assertTrue(any('48.01' in r['title'] for r in results))
        literal=self.ok(await self.http.get('/api/search/global',params={'q':'%_'}))['results'];self.assertEqual(len(literal),1)
        self.assertEqual(self.ok(await self.http.get('/api/search/global',params={'q':'.*'}))['results'],[])
        self.assertEqual(self.ok(await self.http.get('/api/search/global',params={'q':'  '}))['results'],[])
        foreign=self.ok(await self.http.get('/api/search/global',params={'q':'needle'},headers={'Authorization':'Bearer bob'}))['results']
        self.assertEqual(len(foreign),1);self.assertIn('foreign',foreign[0]['title'])

    async def test_study_links_notes_and_archived_parent(self):
        _,program,book=await catalog.RuntimeCatalog.setup_catalog(self)
        async with unit_of_work() as session:
            row=await session.get(StudyProgram,UUID(program['program_id']));row.name='Needle Program'
            notebook=await session.get(Notebook,UUID(book['notebook_id']));notebook.name='Needle Book'
            session.add(StudyNote(user_id=self.uid,notebook_id=notebook.id,title='Needle Note',content='Text'))
            session.add(StudyTarget(user_id=self.uid,program_id=row.id,kind='concurso',name='Needle Target'))
        results=self.ok(await self.http.get('/api/search/global',params={'q':'needle'}))['results']
        self.assertEqual({r['type'] for r in results},{'study_programs','study_targets','notebooks','note'})
        link=next(r['link'] for r in results if r['type']=='notebooks');self.assertIn(book['notebook_id'],link);self.assertIn('view=estudar',link)
        self.ok(await self.http.delete('/api/study/programs/'+program['program_id']))
        self.assertEqual(self.ok(await self.http.get('/api/search/global',params={'q':'needle'}))['results'],[])
