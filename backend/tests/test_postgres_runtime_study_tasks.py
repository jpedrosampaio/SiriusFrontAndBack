import os
import asyncio
import unittest
from datetime import date,datetime,timezone,timedelta
from uuid import UUID
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.models.studies import StudyTaskCheck,StudySession
from db.models.identity import User
from db.session import unit_of_work
from services.time import local_today
import test_postgres_runtime_catalog as catalog_tests


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeStudyTasks(unittest.IsolatedAsyncioTestCase):
    ok=catalog_tests.RuntimeCatalog.ok
    setup_catalog=catalog_tests.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await catalog_tests.RuntimeCatalog.asyncSetUp(self)
        _,_,book=await self.setup_catalog(); self.nid=book['notebook_id']
        async def account(request): return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.patches=[patch(module+'.account',account) for module in ('services.study_tasks','services.study_activity_routes','services.study_statistics')]
        for p in self.patches: p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches): p.stop()
        await catalog_tests.RuntimeCatalog.asyncTearDown(self)

    async def task(self,recurrence='once'):
        return self.ok(await self.http.post('/api/study/tasks',json={'notebook_id':self.nid,'title':'Ler capítulo',
            'recurrence':recurrence,'deadline':'','priority':'high','estimated_minutes':20}))

    async def test_once_completion_retry_undo_and_owner(self):
        task=await self.task(); url='/api/study/tasks/'+task['task_id']
        self.assertIsNone(task['deadline'])
        responses=await asyncio.gather(*(self.http.patch(url,json={'completed':True},headers={'Idempotency-Key':f'complete-once-{i}'}) for i in range(8)))
        for r in responses: self.assertTrue(self.ok(r)['completed'])
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User,self.uid)).xp,15)
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyTaskCheck).where(StudyTaskCheck.user_id==self.uid)),1)
        self.assertEqual(self.ok(await self.http.get('/api/study/stats'))['tasks_completed'],1)
        self.assertEqual((await self.http.patch(url,json={'completed':False},headers={'Authorization':'Bearer bob'})).status_code,404)
        self.assertFalse(self.ok(await self.http.patch(url,json={'completed':False}))['completed'])
        async with unit_of_work() as session: self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_recurring_check_once_per_day_and_streak(self):
        task=await self.task('daily'); url='/api/study/tasks/'+task['task_id']; today=local_today('America/Sao_Paulo')
        for _ in range(3):
            value=self.ok(await self.http.patch(url,json={'completed':True}))
            self.assertFalse(value['completed']); self.assertTrue(value['completed_today'])
        self.assertEqual(self.ok(await self.http.get('/api/study/streak'))['total_study_days'],1)
        with patch('services.study_tasks.local_today',return_value=today+timedelta(days=1)):
            self.assertFalse(self.ok(await self.http.get('/api/study/tasks'))[0]['completed_today'])
            self.ok(await self.http.patch(url,json={'completed':True}))
        self.assertEqual((await self.http.patch(url,json={'recurrence':'once'})).status_code,409)
        self.assertEqual(self.ok(await self.http.get('/api/study/tasks'))[0]['recurrence'],'daily')
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User,self.uid)).xp,30)
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyTaskCheck).where(StudyTaskCheck.user_id==self.uid)),2)

    async def test_failed_completion_rolls_back_and_archive_preserves_check(self):
        task=await self.task(); url='/api/study/tasks/'+task['task_id']
        with patch('services.study_tasks.apply_xp',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError): await self.http.patch(url,json={'completed':True})
        self.assertFalse(self.ok(await self.http.get('/api/study/tasks'))[0]['completed'])
        self.ok(await self.http.patch(url,json={'completed':True}))
        self.ok(await self.http.delete(url)); self.assertEqual(self.ok(await self.http.get('/api/study/tasks')),[])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyTaskCheck).where(StudyTaskCheck.user_id==self.uid)),1)

    async def test_stats_empty_states_period_filter_focus_and_suggestions(self):
        empty=self.ok(await self.http.get('/api/study/stats'))
        self.assertEqual(empty['total_study_time_minutes'],0)
        today=local_today('America/Sao_Paulo')
        async with unit_of_work() as session:
            session.add_all([StudySession(user_id=self.uid,notebook_id=UUID(self.nid),date=today,duration_minutes=30,completed=True,source='focus'),
                StudySession(user_id=self.uid,date=today-timedelta(days=10),duration_minutes=45,completed=True,source='focus')])
        stats=self.ok(await self.http.get('/api/study/stats'))
        self.assertEqual(stats['total_study_time_minutes'],75)
        self.assertEqual(stats['daily_time_last_7_days'],{today.isoformat():30})
        overall=self.ok(await self.http.get('/api/study/overall-stats'))
        self.assertEqual(len(overall['focus_daily']),7); self.assertEqual(sum(r['minutos'] for r in overall['focus_daily']),30)
        with patch('services.study_cards._llm',AsyncMock(return_value='Sugestão')):
            self.assertEqual(self.ok(await self.http.post('/api/study/ai-suggestions'))['suggestions'],'Sugestão')
