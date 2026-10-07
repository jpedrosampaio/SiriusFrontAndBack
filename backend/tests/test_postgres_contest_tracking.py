import asyncio
import os
import threading
import unittest
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from uuid import UUID,uuid4
from unittest.mock import Mock,patch
from fastapi import FastAPI
from httpx import AsyncClient,ASGITransport
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.studies import StudyArea,StudyProgram
from db.models.contests import ContestSource,ContestUpdate,ContestHostLimit,ContestSourceVersion
from contest_watch import ContestWatcher
from contest_sources import GenericOfficialConnector,SourceUnavailable,SourcePage
from services import contest_tracking as tracking
import test_postgres_agent as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class ContestTracking(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await setup.PostgresAgent.asyncSetUp(self)
        async with unit_of_work() as session:
            area=StudyArea(user_id=self.uid,name='Study');session.add(area);await session.flush()
            program=StudyProgram(user_id=self.uid,area_id=area.id,name='Exam');session.add(program);await session.flush();self.pid=program.id
        async def auth(authorization=None,**kwargs):return SimpleNamespace(user_id=str(self.other if authorization=='Bearer bob' else self.uid))
        self.watcher=ContestWatcher(auth);app=FastAPI();app.include_router(self.watcher.router)
        self.http=AsyncClient(transport=ASGITransport(app),base_url='https://sirius.test')
        self.base='/study/v2/programs/'+str(self.pid);self.host=f'watch-{uuid4().hex}.example.test'
        self.url='https://'+self.host+'/contest'

    async def asyncTearDown(self):
        await self.http.aclose();await setup.PostgresAgent.asyncTearDown(self)

    def ok(self,response):
        self.assertEqual(response.status_code,200,response.text);return response.json()

    async def add(self,suffix=''):
        return self.ok(await self.http.post(self.base+'/sources',json={'url':self.url+suffix,'title':'Source','terms_allow_monitoring':True}))

    def page(self,text='First'):
        return GenericOfficialConnector().normalize(text+'<a href="/prova.pdf">Prova</a>',self.url)

    async def test_version_observations_unchanged_reversion_owner_and_pagination(self):
        source=await self.add();sid=source['source_id']
        for text in ('First','First','Second','First'):
            await self.reset_due(sid)
            claimed=await tracking.claim(str(self.uid),str(self.pid),sid)
            self.assertTrue(await tracking.finish(claimed,self.page(text)))
        response=self.ok(await self.http.get(self.base+'/sources/'+sid+'/versions?limit=2'))
        self.assertEqual(len(response['items']),2);self.assertEqual(response['next_offset'],2)
        self.assertNotIn('text',response['items'][0])
        older=self.ok(await self.http.get(self.base+'/sources/'+sid+'/versions?offset=2'))
        self.assertEqual(len(older['items']),1)
        self.assertEqual(response['items'][0]['hash'],older['items'][0]['hash'])
        vid=response['items'][0]['version_id']
        detail=self.ok(await self.http.get(self.base+'/sources/'+sid+'/versions/'+vid))
        self.assertIn('First',detail['text'])
        self.assertEqual((await self.http.get(self.base+'/sources/'+sid+'/versions/'+vid,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.get(self.base+'/radar',headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.get(self.base+'/sources/'+sid+'/versions?limit=51')).status_code,422)
        radar=self.ok(await self.http.get(self.base+'/radar'))
        self.assertEqual(len(radar['latest_versions']),1);self.assertEqual(radar['dates'],[])
        self.assertFalse(radar['plan_changed'])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(ContestSourceVersion).where(ContestSourceVersion.source_id==UUID(sid))),3)

    async def test_official_dates_pdf_changes_keep_document_type_and_provenance(self):
        source=self.ok(await self.http.post(self.base+'/sources',json={'url':self.url+'/prova.pdf','title':'Official PDF',
            'terms_allow_monitoring':True,'source_kind':'official_pdf'}));sid=source['source_id']
        self.assertEqual(source['trust'],'USER_PROVIDED')
        async with unit_of_work() as session:
            # Trusted domain classification fixture; no external service is used.
            row=await session.get(ContestSource,UUID(sid));row.trust='OFFICIAL'
        provider=SimpleNamespace(poll=Mock())
        with patch('contest_watch.provider_for',return_value=provider):
            for digest,text in [('hash1','Prova objetiva: 01/02/2027'),('hash2','Prova objetiva: 02/02/2027')]:
                provider.poll.return_value=SourcePage(text,[{'title':'Prova','url':source['url'],'document_url':source['url'],
                    'document_type':'exam','hash':digest,'hash_basis':'document_bytes','source_type':'OFFICIAL','official':True}],
                    digest,hash_basis='document_bytes')
                await self.reset_due(sid)
                self.ok(await self.http.post(self.base+'/sources/'+sid+'/poll'))
        exams=self.ok(await self.http.get(self.base+'/exams'))
        self.assertEqual(len(exams),2);self.assertTrue(all(row['document_type']=='exam' for row in exams))
        radar=self.ok(await self.http.get(self.base+'/radar'))
        self.assertEqual([d['date'] for d in radar['dates']],['2027-02-02'])
        self.assertEqual(radar['dates'][0]['hash'],'hash2');self.assertEqual(radar['dates'][0]['url'],source['url'])
        self.assertEqual(radar['latest_versions'][0]['hash_basis'],'document_bytes')
        self.assertEqual(radar['latest_versions'][0]['impact']['document_links_added'],[])
        self.assertEqual(radar['latest_versions'][0]['impact']['document_links_removed'],[])

    async def test_reactivated_source_uses_immutable_partial_prior_and_preserves_success(self):
        source=await self.add();sid=source['source_id']
        async with unit_of_work() as session:
            row=await session.get(ContestSource,UUID(sid));row.trust='OFFICIAL'
        page=self.page('First');page.partial=True
        claimed=await tracking.claim(str(self.uid),str(self.pid),sid)
        await tracking.finish(claimed,page,page.documents)
        async with unit_of_work() as session:
            successful=await tracking.official_freshness(session,self.uid,self.pid)
        self.assertIsNotNone(successful)
        await self.reset_due(sid)
        claimed=await tracking.claim(str(self.uid),str(self.pid),sid)
        await tracking.finish(claimed,error='Temporary failure')
        async with unit_of_work() as session:
            self.assertEqual(await tracking.official_freshness(session,self.uid,self.pid),successful)
        await tracking.remove(str(self.uid),str(self.pid),sid)
        await self.add();await self.reset_due(sid)
        claimed=await tracking.claim(str(self.uid),str(self.pid),sid)
        page=GenericOfficialConnector().normalize('Second<a href="/prova-v2.pdf">Prova</a>',self.url)
        await tracking.finish(claimed,page,page.documents)
        versions=self.ok(await self.http.get(self.base+'/sources/'+sid+'/versions'))['items']
        latest=versions[0]
        self.assertEqual(latest['impact']['removed'],['First'])
        self.assertTrue(latest['impact']['partial'])
        self.assertIn('/prova-v2.pdf',latest['impact']['document_links_added'][0]['url'])
        self.assertIn('/prova.pdf',latest['impact']['document_links_removed'][0]['url'])
        self.assertNotIn('documents',latest['details'])
        self.assertEqual(latest['previous_id'],versions[1]['version_id'])
        timeline=self.ok(await self.http.get(self.base+'/timeline'))
        linked=[item for item in timeline if item['url'].endswith('/prova-v2.pdf')]
        self.assertEqual(len(linked),1)
        async with unit_of_work() as session:
            row=await session.scalar(select(ContestUpdate).where(ContestUpdate.source_id==UUID(sid),ContestUpdate.url.endswith('/prova-v2.pdf')))
            self.assertEqual(str(row.version_id),latest['version_id'])

    async def reset_due(self,sid):
        async with unit_of_work() as session:
            row=await session.get(ContestSource,UUID(sid));row.next_poll=datetime.now(timezone.utc)-timedelta(seconds=1)
            host=await session.get(ContestHostLimit,self.host)
            if host:host.next_poll=datetime.now(timezone.utc)-timedelta(seconds=1)

    async def test_registration_owner_concurrency_cap_and_terms(self):
        responses=await asyncio.gather(*(self.add() for _ in range(6)))
        self.assertEqual(len({r['source_id'] for r in responses}),1)
        self.assertNotIn('snapshot',responses[0])
        more=await asyncio.gather(*(self.http.post(self.base+'/sources',json={'url':self.url+str(i),'title':'Source','terms_allow_monitoring':True}) for i in range(6)))
        self.assertEqual([r.status_code for r in more].count(200),4);self.assertEqual([r.status_code for r in more].count(409),2)
        self.assertEqual((await self.http.get(self.base+'/sources',headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.post(self.base+'/sources',json={'url':self.url,'title':'Source'})).status_code,422)
        self.assertEqual((await self.http.post(self.base+'/sources',json={'url':'https://127.0.0.1/a','title':'Source','terms_allow_monitoring':True})).status_code,422)

    async def test_poll_claim_timeline_diff_dedup_and_host_cooldown(self):
        row=await self.add();sid=row['source_id'];provider=SimpleNamespace(poll=Mock(return_value=self.page()))
        with patch('contest_watch.provider_for',return_value=provider):
            results=[self.ok(r) for r in await asyncio.gather(*(self.http.post(self.base+'/sources/'+sid+'/poll') for _ in range(5)))]
        self.assertEqual(provider.poll.call_count,1);self.assertEqual([r['status'] for r in results].count('ok'),1)
        timeline=self.ok(await self.http.get(self.base+'/timeline'));self.assertEqual(len(timeline),1);self.assertEqual(timeline[0]['document_type'],'exam')
        self.assertEqual(len(self.ok(await self.http.get(self.base+'/exams'))),1)
        second=await self.add('/second')
        with patch('contest_watch.provider_for',return_value=provider):
            self.assertEqual(self.ok(await self.http.post(self.base+'/sources/'+second['source_id']+'/poll'))['status'],'deferred')
        self.assertEqual(provider.poll.call_count,1)
        await self.reset_due(sid);provider.poll.return_value=self.page('Second')
        with patch('contest_watch.provider_for',return_value=provider):self.ok(await self.http.post(self.base+'/sources/'+sid+'/poll'))
        timeline=self.ok(await self.http.get(self.base+'/timeline'));self.assertEqual(len(timeline),2)
        change=next(r for r in timeline if r['document_type']=='page_change');self.assertIn('Second',change['changes']['added'][0])
        self.assertEqual((await self.http.get(self.base+'/timeline',headers={'Authorization':'Bearer bob'})).status_code,404)

    async def test_source_removed_during_fetch_revokes_ingestion(self):
        row=await self.add();sid=row['source_id'];entered=threading.Event();release=threading.Event()
        def fetch(*args):entered.set();release.wait(5);return self.page()
        with patch('contest_watch.provider_for',return_value=SimpleNamespace(poll=fetch)):
            task=asyncio.create_task(self.http.post(self.base+'/sources/'+sid+'/poll'))
            self.assertTrue(await asyncio.to_thread(entered.wait,5))
            self.ok(await self.http.delete(self.base+'/sources/'+sid));release.set()
            self.assertEqual(self.ok(await task)['status'],'removed')
        self.assertEqual(self.ok(await self.http.get(self.base+'/timeline')),[])
        self.assertEqual(self.ok(await self.http.get(self.base+'/sources')),[])

    async def test_backoff_archive_and_stale_lease(self):
        row=await self.add();sid=row['source_id']
        with patch('contest_watch.provider_for',return_value=SimpleNamespace(poll=Mock(side_effect=SourceUnavailable('robots disallowed')))):
            result=self.ok(await self.http.post(self.base+'/sources/'+sid+'/poll'));self.assertEqual(result['status'],'unavailable')
        async with unit_of_work() as session:
            source=await session.get(ContestSource,UUID(sid));self.assertEqual(source.failures,1)
            self.assertGreater(source.next_poll,datetime.now(timezone.utc)+timedelta(hours=11))
        await self.reset_due(sid);old=await tracking.claim(self.uid,self.pid,sid)
        await self.reset_due(sid);fresh=await tracking.claim(self.uid,self.pid,sid)
        page=self.page();self.assertFalse(await tracking.finish(old,page,page.documents))
        self.assertTrue(await tracking.finish(fresh,page,page.documents))
        async with unit_of_work() as session:
            program=await session.get(StudyProgram,self.pid);program.archived_at=datetime.now(timezone.utc)
        self.assertEqual((await self.http.get(self.base+'/sources')).status_code,404)
        self.assertFalse(any(str(self.pid)==pid for uid,pid,sid in await tracking.due()))
