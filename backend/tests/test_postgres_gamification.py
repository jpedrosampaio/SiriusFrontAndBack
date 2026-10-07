import asyncio
import os
import unittest
from datetime import datetime,timezone,timedelta
from uuid import UUID,uuid4
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import select,func
from db.models.gamification import Achievement,WeeklyChallenge
from db.models.identity import User
from db.models.planning import Habit,HabitCheck,XPEntry
from db.models.studies import StudySession
from db.session import unit_of_work
from db.activity import run_activity
from services.planning import apply_xp,rank_for_xp
import test_postgres_runtime_dashboard as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class Gamification(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeDashboard.ok
    asyncTearDown=setup.RuntimeDashboard.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeDashboard.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid)}
        p=patch('services.gamification.account',account);p.start();self.patches.append(p)

    async def test_empty_catalog_concurrent_unlocks_and_completed_facts(self):
        empty=self.ok(await self.http.get('/api/achievements/full'))
        self.assertEqual(empty['total'],27);self.assertEqual(empty['unlocked'],0)
        async with unit_of_work() as session:
            habit=Habit(user_id=self.uid,name='Reading');session.add(habit);await session.flush()
            session.add_all([HabitCheck(user_id=self.uid,habit_id=habit.id,date=self.today-timedelta(days=i),checked_at=datetime.now(timezone.utc)) for i in range(7)])
            session.add(StudySession(user_id=self.uid,date=self.today,completed=True,source='focus',duration_minutes=600))
            session.add(StudySession(user_id=self.uid,date=self.today,completed=False,duration_minutes=5000))
            session.add(StudySession(user_id=self.uid,date=self.today+timedelta(days=1),completed=True,duration_minutes=5000))
        responses=[self.ok(r) for r in await asyncio.gather(*(self.http.get('/api/achievements/full') for _ in range(6)))]
        self.assertEqual(sum(len(r['newly_unlocked']) for r in responses),4)
        values={r['id']:r for r in responses[0]['achievements']}
        self.assertTrue(values['habit_streak_7']['unlocked']);self.assertTrue(values['study_hours_10']['unlocked'])
        self.assertFalse(values['study_hours_50']['unlocked'])
        self.assertEqual(len(self.ok(await self.http.get('/api/achievements'))),4)
        self.assertEqual(self.ok(await self.http.get('/api/achievements',headers={'Authorization':'Bearer bob'})),[])

    async def test_challenge_defaults_owned_concurrent_reward_and_rollback(self):
        pages=[self.ok(r) for r in await asyncio.gather(*(self.http.get('/api/challenges/current') for _ in range(5)))]
        self.assertTrue(all(len(page)==3 for page in pages))
        self.assertEqual(len({row['challenge_id'] for page in pages for row in page}),3)
        chosen=pages[0][0];sid=chosen['challenge_id']
        self.assertEqual((await self.http.post('/api/challenges/'+sid+'/complete',headers={'Authorization':'Bearer bob'})).status_code,404)
        values=[self.ok(r) for r in await asyncio.gather(*(self.http.post('/api/challenges/'+sid+'/complete') for _ in range(8)))]
        self.assertEqual(sum(bool(v.get('replayed')) for v in values),7)
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User,self.uid)).xp,chosen['xp_reward'])
            self.assertEqual(await session.scalar(select(func.count()).select_from(Achievement).where(Achievement.user_id==self.uid)),1)
        second=pages[0][1]['challenge_id']
        def fail(user,delta):apply_xp(user,delta);raise RuntimeError('after XP')
        with patch('services.gamification.apply_xp',fail):
            with self.assertRaises(RuntimeError):await self.http.post('/api/challenges/'+second+'/complete')
        async with unit_of_work() as session:
            self.assertIsNone((await session.get(WeeklyChallenge,UUID(second))).completed_at)
            self.assertEqual((await session.get(User,self.uid)).xp,chosen['xp_reward'])

    async def award(self,uid,amount):
        async def apply(session,user):
            xp,rank=apply_xp(user,amount)
            return {'xp':xp,'rank':rank}
        return await run_activity(uid,None,['xp_test',amount],apply)

    async def test_xp_concurrent_awards_deductions_and_owner(self):
        async with unit_of_work() as session:
            user=await session.get(User,self.uid);user.xp=190;user.rank=rank_for_xp(190)
            other=await session.get(User,self.bob);other.xp=500;other.rank=rank_for_xp(500)
        await asyncio.gather(*(self.award(self.uid,8) for _ in range(40)))
        async with unit_of_work() as session:
            user=await session.get(User,self.uid);self.assertEqual((user.xp,user.rank),(510,'Cabo'))
            self.assertEqual((await session.get(User,self.bob)).xp,500)
        await asyncio.gather(*(self.award(self.bob,amount) for amount in [10,-8]*20))
        async with unit_of_work() as session:
            user=await session.get(User,self.bob);self.assertEqual((user.xp,user.rank),(540,'Cabo'))

    async def test_xp_nonnegative_default_missing_user_and_same_transaction_changes(self):
        await asyncio.gather(*(self.award(self.uid,8) for _ in range(30)))
        async with unit_of_work() as session:
            user=await session.get(User,self.uid);self.assertEqual((user.xp,user.rank),(240,'Soldado'))
        await asyncio.gather(*(self.award(self.uid,-8) for _ in range(40)))
        async with unit_of_work() as session:
            user=await session.get(User,self.uid);self.assertEqual((user.xp,user.rank),(0,'Recruta'))
            self.assertEqual(await session.scalar(select(func.sum(XPEntry.amount)).where(XPEntry.user_id==self.uid)),0)
            user.xp=198
            self.assertEqual(apply_xp(user,8),(206,'Soldado'))
            self.assertEqual(apply_xp(user,-3),(203,'Soldado'))
        with self.assertRaises(HTTPException) as error:await self.award(uuid4(),8)
        self.assertEqual(error.exception.status_code,404)
