import os
import unittest
from datetime import datetime,time,timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from unittest.mock import patch,AsyncMock
from db.models.studies import StudySession,QuestionAttempt
from db.session import unit_of_work
from services.time import local_today
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeStudyHistory(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok
    setup_catalog=catalog_tests.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        _,self.program,self.book=await self.setup_catalog()
        async def account(request): return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.history_auth=patch('services.study_history_routes.account',account); self.history_auth.start()

    async def asyncTearDown(self):
        self.history_auth.stop(); await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def test_lessons_require_owned_active_notebook_before_provider(self):
        url='/api/study/notebooks/'+self.book['notebook_id']+'/lessons'
        provider=AsyncMock(return_value={'videos':[],'status':'not_configured'})
        with patch('services.study_history_routes.youtube_lessons',provider):
            self.assertEqual((await self.http.get(url,headers={'Authorization':'Bearer bob'})).status_code,404)
            provider.assert_not_awaited()
            self.ok(await self.http.get(url,params={'topic':'  Crase  '}))
            self.assertEqual(provider.call_args.args[0],'Português Crase aula concurso')
            self.ok(await self.http.delete('/api/study/notebooks/'+self.book['notebook_id']))
            self.assertEqual((await self.http.get(url)).status_code,404)
            self.assertEqual(provider.await_count,1)

    async def test_history_civil_dates_range_cumulative_and_owner(self):
        url='/api/study/programs/'+self.program['program_id']+'/progress-history'
        self.assertEqual(self.ok(await self.http.get(url))['history'],[])
        today=local_today('America/Sao_Paulo'); nid=UUID(self.book['notebook_id']); zone=ZoneInfo('America/Sao_Paulo')
        async with unit_of_work() as session:
            for delta,minutes,total,correct in [(0,60,10,8),(1,30,5,2),(3,90,20,20)]:
                d=today-timedelta(days=delta)
                session.add(StudySession(user_id=self.uid,notebook_id=nid,date=d,duration_minutes=minutes,completed=True,source='manual'))
                session.add(QuestionAttempt(user_id=self.uid,notebook_id=nid,answered_at=datetime.combine(d,time(23,30),zone),total=total,correct=correct,source='manual'))
            session.add(StudySession(user_id=self.uid,notebook_id=nid,date=today,duration_minutes=200,completed=False,source='focus'))
        result=self.ok(await self.http.get(url,params={'days':2}))
        self.assertEqual([r['date'] for r in result['history']],[(today-timedelta(days=1)).isoformat(),today.isoformat()])
        last=result['history'][-1]
        self.assertEqual((last['Português_questoes'],last['Português_acerto'],last['Português_horas']),(15,66.7,1.5))
        self.assertEqual((await self.http.get(url,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertEqual((await self.http.get(url,params={'days':0})).status_code,422)
        self.ok(await self.http.delete('/api/study/programs/'+self.program['program_id']))
        self.assertEqual((await self.http.get(url)).status_code,404)
