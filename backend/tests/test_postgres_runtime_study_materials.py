import os
import json
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.models.studies import MindMap,EssayCorrection
from db.models.identity import User
from db.session import unit_of_work
import test_postgres_runtime_catalog as catalog_tests

MAP={'title':'Direito','nodes':[{'id':'1','label':'Constituição','children':[]}]}
ESSAY={'nota_geral':8,'nota_maxima':10,'competencias':[],'nivel':'Bom'}


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeStudyMaterials(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok
    setup_catalog=catalog_tests.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        _,_,self.book=await self.setup_catalog()
        async def account(request): return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.gemini=AsyncMock(return_value=SimpleNamespace(text=json.dumps(MAP)))
        self.patches=[patch('services.study_material_routes.account',account),patch('services.study_material_routes._key',AsyncMock(return_value='test-only')),
            patch('services.study_material_routes._gemini',self.gemini)]
        for p in self.patches: p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches): p.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def test_map_notebook_owner_replay_archive_and_delete(self):
        data={'notebook_id':self.book['notebook_id']}
        self.assertEqual((await self.http.post('/api/study/mindmap/generate',data=data,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.gemini.assert_not_awaited()
        responses=await asyncio.gather(*(self.http.post('/api/study/mindmap/generate',data=data,headers={'Idempotency-Key':'mindmap-retry-001'}) for _ in range(5)))
        results=[self.ok(r) for r in responses]; self.assertTrue(all({k:v for k,v in r.items() if k!='replayed'}=={k:v for k,v in results[0].items() if k!='replayed'} for r in results))
        self.assertEqual(self.ok(await self.http.get('/api/study/mindmaps'))[0]['data'],MAP)
        self.assertEqual(self.ok(await self.http.get('/api/study/mindmaps',headers={'Authorization':'Bearer bob'})),[])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(MindMap).where(MindMap.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,10)
        url='/api/study/mindmaps/'+results[0]['mindmap_id']
        self.assertEqual((await self.http.delete(url,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.ok(await self.http.delete('/api/study/notebooks/'+self.book['notebook_id']))
        self.assertEqual(self.ok(await self.http.get('/api/study/mindmaps')),[])
        self.ok(await self.http.delete(url))

    async def test_invalid_ai_and_failed_xp_leave_no_artifact(self):
        self.gemini.return_value=SimpleNamespace(text='{"title":"Incomplete","nodes":[]}')
        self.assertEqual((await self.http.post('/api/study/mindmap/generate',data={'topic':'Direito'})).status_code,502)
        self.gemini.return_value=SimpleNamespace(text=json.dumps(MAP))
        with patch('services.study_material_routes.apply_xp',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError): await self.http.post('/api/study/mindmap/generate',data={'topic':'Direito'})
        self.assertEqual(self.ok(await self.http.get('/api/study/mindmaps')),[])

    async def test_essay_replay_history_owner_and_atomic_failure(self):
        self.gemini.return_value=SimpleNamespace(text=json.dumps(ESSAY))
        async def submit(): return await self.http.post('/api/study/redacao/correct',files={'file':('essay.txt',b'Argumento','text/plain')},headers={'Idempotency-Key':'essay-retry-001'})
        responses=await asyncio.gather(*(submit() for _ in range(4)))
        self.assertTrue(all(r.status_code in (200,409) for r in responses))
        results=[self.ok(r) for r in responses if r.status_code==200]
        results.append(self.ok(await submit()))
        self.assertEqual(self.gemini.await_count,1)
        self.assertFalse(results[0]['correction']['official'])
        self.assertTrue(all({k:v for k,v in r.items() if k!='replayed'}=={k:v for k,v in results[0].items() if k!='replayed'} for r in results))
        self.assertEqual(len(self.ok(await self.http.get('/api/study/redacao/history'))),1)
        self.assertEqual(self.ok(await self.http.get('/api/study/redacao/history',headers={'Authorization':'Bearer bob'})),[])
        with patch('services.study_material_routes.apply_xp',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError): await self.http.post('/api/study/redacao/correct',files={'file':('essay.txt',b'Novo','text/plain')})
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(EssayCorrection).where(EssayCorrection.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,15)

    async def test_temporary_upload_removed_on_provider_failure(self):
        paths=[]
        async def fail(path,uid):
            paths.append(path); self.assertTrue(Path(path).exists()); raise RuntimeError('upload failed')
        with patch('services.study_material_routes._upload',fail):
            with self.assertRaises(RuntimeError): await self.http.post('/api/study/mindmap/generate',files={'file':('map.pdf',b'%PDF fake','application/pdf')})
        self.assertTrue(paths); self.assertTrue(all(not Path(p).exists() for p in paths))
        self.assertEqual(self.ok(await self.http.get('/api/study/mindmaps')),[])
