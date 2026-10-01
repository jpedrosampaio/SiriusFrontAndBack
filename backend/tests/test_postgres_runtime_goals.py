import asyncio
import os
import sys
import unittest
from uuid import UUID,uuid4
from unittest.mock import patch
from httpx import ASGITransport,AsyncClient
from sqlalchemy import select,func
from db.engine import dispose_engine
from db.session import unit_of_work
from db.models.identity import User
from db.models.planning import GoalCheck

if sys.platform=='win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeGoals(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self): await dispose_engine()

    async def test_goal_lifecycle_replay_ownership_progress_and_archive(self):
        with patch.dict(os.environ,{'MONGO_URL':'mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=10','DB_NAME':'unavailable'}):
            import server
        async with AsyncClient(transport=ASGITransport(server.app),base_url='https://sirius.test') as client:
            registered=await client.post('/api/auth/register',json={'email':f'{uuid4()}@example.test','name':'Goal','password':'test-password'})
            self.assertEqual(registered.status_code,200,registered.text)
            uid=UUID(registered.json()['user']['user_id'])
            self.assertEqual((await client.get('/api/goals')).json(),[])
            created=await client.post('/api/goals',json={'title':'Read','target_date':'2026-12-31'})
            self.assertEqual(created.status_code,200,created.text)
            path='/api/goals/'+created.json()['goal_id']
            results=await asyncio.gather(*(client.post(path+'/check',params={'date':'2026-10-01'},headers={'Idempotency-Key':'goal-check-001'}) for _ in range(8)))
            for result in results: self.assertEqual(result.status_code,200,result.text)
            async with unit_of_work() as session:
                self.assertEqual((await session.get(User,uid)).xp,5)
                self.assertEqual(await session.scalar(select(func.count()).select_from(GoalCheck).where(GoalCheck.user_id==uid)),1)
            self.assertEqual((await client.get('/api/goals')).json()[0]['daily_checks'],['2026-10-01'])
            self.assertEqual((await client.patch(path,params={'progress':40})).status_code,200)
            self.assertEqual((await client.patch(path,params={'progress':101})).status_code,422)
            self.assertEqual((await client.get('/api/goals')).json()[0]['progress'],40)
            from services.planning import apply_xp
            def fail(user,delta):
                apply_xp(user,delta)
                raise RuntimeError('rollback goal')
            with patch('services.goals_routes.apply_xp',fail):
                with self.assertRaises(Exception): await client.post(path+'/check',params={'date':'2026-10-02'})
            self.assertEqual((await client.get('/api/goals')).json()[0]['daily_checks'],['2026-10-01'])
            token=registered.json()['session_token']
            await client.post('/api/auth/register',json={'email':f'{uuid4()}@example.test','name':'Other','password':'test-password'})
            for method,url,kwargs in [('patch',path,{'params':{'progress':80}}),('delete',path,{}),('post',path+'/check',{'params':{'date':'2026-10-01'}})]:
                self.assertEqual((await getattr(client,method)(url,**kwargs)).status_code,404)
            headers={'Authorization':'Bearer '+token}
            client.cookies.clear()
            self.assertEqual((await client.delete(path,headers=headers)).status_code,200)
            self.assertEqual((await client.get('/api/goals',headers=headers)).json(),[])
            self.assertEqual((await client.post(path+'/check',params={'date':'2026-10-01'},headers=headers)).status_code,404)
            async with unit_of_work() as session:
                self.assertEqual(await session.scalar(select(func.count()).select_from(GoalCheck).where(GoalCheck.user_id==uid)),1)
