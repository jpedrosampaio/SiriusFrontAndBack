import asyncio
import os
import unittest
from datetime import date
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.studies import QuestionAttempt,ReviewEvent
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeWorkspace(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok
    setup_catalog=catalog_tests.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        async def account(request):
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.patches=[patch('services.study_workspace.account',account),patch('services.study_activity_routes.account',account),
            patch('services.study_workspace.local_today',return_value=date(2026,9,28))]
        for item in self.patches: item.start()
        _,self.program,self.notebook=await self.setup_catalog()
        self.nid=self.notebook['notebook_id']; self.pid=self.program['program_id']

    async def asyncTearDown(self):
        for item in reversed(self.patches): item.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def test_save_read_retry_and_conflicting_tabs(self):
        url=f'/api/study/notebooks/{self.nid}/draft?topic_key=0_1'
        self.assertEqual(self.ok(await self.http.get(url)),{'text':'','revision':0})
        self.ok(await self.http.put(url,json={'text':'Minha anotação','revision':0}))
        self.assertEqual(self.ok(await self.http.get(url))['text'],'Minha anotação')
        self.ok(await self.http.put(url,json={'text':'Minha anotação','revision':0}))
        responses=await asyncio.gather(*(self.http.put(url,json={'text':text,'revision':1}) for text in ('aba A','aba B')))
        self.assertEqual(sorted(row.status_code for row in responses),[200,409])
        foreign={'Authorization':'Bearer bob'}
        self.assertEqual((await self.http.get(url,headers=foreign)).status_code,404)
        self.assertEqual((await self.http.put(url,json={'text':'x','revision':0},headers=foreign)).status_code,404)
        self.assertEqual((await self.http.get(f'/api/study/notebooks/{self.nid}/draft?topic_key=0.$set')).status_code,422)

    async def test_dated_plan_preserves_done_blocks_and_rejects_overbooking(self):
        url=f'/api/study/programs/{self.pid}/dated-plan'
        self.assertEqual(self.ok(await self.http.get(url)),{'entries':[],'settings':None})
        settings={'start_date':'2026-09-28','end_date':'2026-10-02','availability':[60,60,60,60,60,0,0],'block_minutes':60}
        entries=self.ok(await self.http.post(url,json=settings))['entries']
        self.assertEqual(len(entries),5)
        path=url+'/'+entries[0]['entry_id']
        self.assertEqual((await self.http.patch(path,json={'date':entries[1]['date']})).status_code,422)
        self.ok(await self.http.patch(path,json={'completed':True}))
        self.assertEqual((await self.http.patch(path,json={'date':'2026-09-29'})).status_code,409)
        regenerated=self.ok(await self.http.post(url,json={**settings,'adaptive':True}))
        self.assertTrue(any(row['entry_id']==entries[0]['entry_id'] and row['completed'] for row in regenerated['entries']))
        self.assertEqual((await self.http.get(url,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.patch(path,json={'date':'2026-02-31'})).status_code,422)

    async def test_topic_practice_replay_owner_and_counts(self):
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={'conteudo_programatico':[{'assunto':'Crase','subtopicos':['Exceções']}]}))
        url=f'/api/study/notebooks/{self.nid}/practice'; body={'topic_key':'0_0','total':10,'correct':5}
        headers={'Idempotency-Key':'practice-replay-001'}
        self.assertEqual(self.ok(await self.http.post(url,json=body,headers=headers))['title'],'Exceções')
        self.assertTrue(self.ok(await self.http.post(url,json=body,headers=headers))['replayed'])
        async with unit_of_work() as session:
            for model in (QuestionAttempt,ReviewEvent):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),1)
        self.assertEqual(self.ok(await self.http.get('/api/study/notebooks'))[0]['total_questions'],10)
        self.assertEqual(self.ok(await self.http.get(f'/api/study/notebooks/{self.nid}/learning-summary'))['accuracy'],50)
        self.assertEqual(self.ok(await self.http.get(f'/api/study/notebooks/{self.nid}/reviews'))[0]['topic_key'],'0_0')
        self.assertEqual((await self.http.post(url,json=body,headers={**headers,'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.post(url,json={**body,'correct':11},headers=headers)).status_code,422)
