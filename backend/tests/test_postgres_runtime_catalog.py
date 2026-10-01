import asyncio
import os
import sys
import unittest
from datetime import date,datetime,timezone
from uuid import UUID,uuid4
from unittest.mock import patch
from httpx import ASGITransport,AsyncClient
from sqlalchemy import select,func
from db.engine import dispose_engine
from db.session import unit_of_work
from db.repositories.identity import IdentityRepository
from db.models.studies import StudyArea,StudySession,QuestionAttempt,StudyTopic

if sys.platform=='win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeCatalog(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch.dict(os.environ,{'MONGO_URL':'mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=10','DB_NAME':'unavailable'}):
            import server
        self.http=AsyncClient(transport=ASGITransport(server.app),base_url='https://sirius.test')
        async with unit_of_work() as session:
            repo=IdentityRepository(session)
            self.uid=(await repo.create(email=f'{uuid4()}@example.test',name='Study',password_hash='test-only')).id
            self.bob=(await repo.create(email=f'{uuid4()}@example.test',name='Other',password_hash='test-only')).id
        async def account(request):
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.auth=patch('services.studies_catalog_routes.account',account); self.auth.start()

    async def asyncTearDown(self):
        self.auth.stop(); await self.http.aclose(); await dispose_engine()

    def ok(self,response):
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    async def setup_catalog(self):
        areas=self.ok(await self.http.get('/api/study/areas'))
        program=self.ok(await self.http.post('/api/study/programs',json={'area_id':areas[0]['area_id'],'name':'Program'}))
        notebook=self.ok(await self.http.post('/api/study/notebooks',json={'area_id':areas[0]['area_id'],'program_id':program['program_id'],'name':'Português'}))
        return areas[0],program,notebook

    async def test_default_areas_are_concurrency_safe(self):
        responses=await asyncio.gather(*(self.http.get('/api/study/areas') for _ in range(8)))
        for response in responses: self.assertEqual(len(self.ok(response)),4)
        ids=[{r['area_id'] for r in response.json()} for response in responses]
        self.assertTrue(all(identity==ids[0] for identity in ids))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyArea).where(StudyArea.user_id==self.uid)),4)

    async def test_syllabus_notes_aggregates_and_archive(self):
        area,program,notebook=await self.setup_catalog(); nid=notebook['notebook_id']
        data={'conteudo_programatico':[{'assunto':'Crase','subtopicos':['Exceções']}],'weight':3,'user_difficulty':'alta'}
        updated=self.ok(await self.http.patch('/api/study/notebooks/'+nid,json=data))
        self.assertEqual(updated['user_difficulty'],'alta')
        note=self.ok(await self.http.post('/api/study/notes',json={'notebook_id':nid,'title':'Resumo','content':'Texto','links':[{'title':'Fonte','url':'https://example.test'}]}))
        self.ok(await self.http.patch('/api/study/notes/'+note['note_id'],json={'content':'Editado'}))
        self.assertEqual(self.ok(await self.http.get('/api/study/notes'))[0]['content'],'Editado')
        self.assertEqual((await self.http.post('/api/study/notes/'+note['note_id']+'/upload',files={'file':('file.pdf',b'pdf','application/pdf')})).status_code,503)
        async with unit_of_work() as session:
            topics=(await session.scalars(select(StudyTopic).where(StudyTopic.user_id==self.uid))).all()
            self.assertEqual({t.topic_key for t in topics},{'0','0_0'})
            session.add(StudySession(user_id=self.uid,notebook_id=UUID(nid),date=date(2026,10,1),duration_minutes=25,completed=True))
            session.add(QuestionAttempt(user_id=self.uid,notebook_id=UUID(nid),total=10,correct=7,source='manual',answered_at=datetime.now(timezone.utc)))
        totals=self.ok(await self.http.get('/api/study/programs'))[0]
        self.assertEqual((totals['total_questions'],totals['correct_questions'],totals['total_study_time_minutes']),(10,7,25))
        self.ok(await self.http.delete('/api/study/programs/'+program['program_id']))
        self.assertEqual(self.ok(await self.http.get('/api/study/notebooks')),[])
        self.assertEqual(self.ok(await self.http.get('/api/study/notes')),[])
        self.assertEqual((await self.http.patch('/api/study/notes/'+note['note_id'],json={'title':'Archived'})).status_code,404)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.user_id==self.uid)),1)

    async def test_owner_and_parent_links_are_enforced(self):
        area,program,notebook=await self.setup_catalog()
        foreign={'Authorization':'Bearer bob'}
        for path in ('areas/'+area['area_id'],'programs/'+program['program_id'],'notebooks/'+notebook['notebook_id']):
            self.assertEqual((await self.http.delete('/api/study/'+path,headers=foreign)).status_code,404)
        self.assertEqual((await self.http.post('/api/study/notes',json={'notebook_id':notebook['notebook_id'],'title':'Foreign'},headers=foreign)).status_code,404)
        self.assertEqual((await self.http.post('/api/study/programs',json={'area_id':area['area_id'],'name':'Foreign'},headers=foreign)).status_code,404)
        self.assertEqual(self.ok(await self.http.get('/api/study/notebooks',headers=foreign)),[])
        other=self.ok(await self.http.post('/api/study/areas',json={'name':'Other'}))
        self.assertEqual((await self.http.patch('/api/study/notebooks/'+notebook['notebook_id'],json={'area_id':other['area_id']})).status_code,422)
        self.assertEqual((await self.http.patch('/api/study/programs/'+program['program_id'],json={'status':'invalid'})).status_code,422)
