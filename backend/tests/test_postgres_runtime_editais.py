import os
import unittest
import asyncio
from types import SimpleNamespace
from fastapi import FastAPI
from httpx import AsyncClient,ASGITransport
from edital_review_routes import review_router
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from unittest.mock import patch
from services import edital_analyses as analyses
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeEditais(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        async def account(request):
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid)}
        self.auth_edital=patch('services.edital_routes.account',account); self.auth_edital.start()

    async def asyncTearDown(self):
        self.auth_edital.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    def document(self,hash_value='hash',name='Analista',discipline='Português'):
        return {'analysis_id':str(uuid4()),'pdf_hash':hash_value,'analysis_version':5,'pdf_filename':'edital.pdf',
            'expires_at':(datetime.now(timezone.utc)+timedelta(days=90)).isoformat(),
            'pdf_text':'Texto privado integral','pdf_pages':[{'page':1,'text':'Página privada'}],
            'concurso':{'nome':'Concurso'},'multiple_cargos':False,
            'cargos':[{'nome':name,'disciplinas':[{'nome':discipline,'topicos':['Tema']}]}]}

    async def test_saved_analysis_owner_source_exclusion_and_delete_cache_copies(self):
        data=self.document(); await analyses.save(self.uid,data)
        copy=self.document(); copy['from_cache']=True; await analyses.save(self.uid,copy)
        await analyses.save(self.bob,self.document())
        url='/api/study/programs/editais/'+data['analysis_id']
        result=self.ok(await self.http.get(url))
        self.assertNotIn('pdf_text',result); self.assertNotIn('pdf_pages',result)
        self.assertEqual(result['pdf_filename'],'edital.pdf')
        self.assertEqual((await self.http.get(url,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.delete(url,headers={'Authorization':'Bearer bob'})).status_code,404)
        listing=self.ok(await self.http.get('/api/study/programs/editais'))
        self.assertEqual(listing['total'],1)
        self.assertNotIn('Página privada',str(listing))
        cached=await analyses.cached(self.uid,'hash',5)
        self.assertEqual(cached['pdf_text'],'Texto privado integral')
        self.assertIsNone(await analyses.cached(self.uid,'hash',4))
        self.assertEqual(self.ok(await self.http.delete(url))['deleted_count'],2)
        self.assertEqual(self.ok(await self.http.get('/api/study/programs/editais'))['total'],0)
        self.assertIsNotNone(await analyses.cached(self.bob,'hash',5))

    async def test_comparison_cargo_update_and_expired_cache(self):
        first=self.document('one'); second=self.document('two',discipline='Direito')
        second['expires_at']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        await analyses.save(self.uid,first); await analyses.save(self.uid,second)
        body={'analysis_id_a':first['analysis_id'],'analysis_id_b':second['analysis_id']}
        result=self.ok(await self.http.post('/api/study/programs/editais/compare',json=body))
        self.assertEqual(result['cargos_changed'][0]['disciplinas_added'],['Direito'])
        self.assertEqual(result['cargos_changed'][0]['disciplinas_removed'],['Português'])
        self.assertEqual((await self.http.post('/api/study/programs/editais/compare',json=body,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertIsNone(await analyses.cached(self.uid,'two',5))
        cargo={'nome':'Alterado','disciplinas':[{'nome':'Matemática'}]}
        await analyses.replace_cargo(self.uid,first['analysis_id'],0,cargo)
        self.assertEqual((await analyses.get(self.uid,first['analysis_id']))['cargos'][0],cargo)

    async def test_review_revision_conflict_source_and_owner(self):
        data=self.document(); await analyses.save(self.uid,data)
        async def authenticate(authorization=None,session_token=None):
            return SimpleNamespace(user_id=str(self.bob if authorization=='Bearer bob' else self.uid))
        app=FastAPI(); app.include_router(review_router(authenticate))
        async with AsyncClient(transport=ASGITransport(app),base_url='https://sirius.test') as http:
            base='/study/programs/editais/'+data['analysis_id']
            self.assertEqual(self.ok(await http.get(base+'/source/1'))['text'],'Página privada')
            self.assertEqual((await http.get(base+'/source/1',headers={'Authorization':'Bearer bob'})).status_code,404)
            body={'revision':0,'disciplinas':[{'nome':'Português','peso':2,'conteudo_programatico':[{'assunto':'Crase'}]}]}
            results=await asyncio.gather(*(http.put(base+'/cargos/0',json=body) for _ in range(2)))
            self.assertEqual(sorted(r.status_code for r in results),[200,409])
        result=await analyses.get(self.uid,data['analysis_id'])
        self.assertEqual(result['revision'],1)
        self.assertEqual(result['cargos'][0]['disciplinas'][0]['peso_status'],'informado_pelo_usuario')
