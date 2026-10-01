import asyncio
import os
import sys
import unittest
from uuid import uuid4,UUID
from sqlalchemy import func,select
from db.engine import dispose_engine
from db.session import unit_of_work
from db.models.health import WorkoutLog
from db.repositories.identity import IdentityRepository
from db.repositories.health import HealthRepository
from services.workouts import start_session,complete_session

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true','Disposable PostgreSQL required')
class PostgresHealth(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await dispose_engine()

    async def test_four_week_plan_and_repeated_completion(self):
        async with unit_of_work() as session:
            uid = (await IdentityRepository(session).create(email=f'{uuid4()}@example.test',name='Workout',password_hash='test-only')).id
            days = [{'week':week,'day_label':f'Semana {week} - Dia {day}',
                'exercises':[{'name':'Agachamento','sets':3,'reps':12}]} for week in range(1,5) for day in range(1,6)]
            pid = (await HealthRepository(session).create_plan(uid,name='4 semanas',days=days)).id
        async with unit_of_work() as session:
            plan = await HealthRepository(session).plan(uid,pid)
            self.assertEqual(len(plan.days),20)
            self.assertEqual([d.week for d in plan.days[5:10]],[2]*5)
            self.assertEqual(plan.days[5].exercises[0].name,'Agachamento')
        started = await start_session(uid,pid,day_index=5,request_key='start_workout')
        sid = UUID(started['session_id'])
        self.assertEqual(started['day_index'],5)
        results = await asyncio.gather(*(complete_session(uid,sid,{},request_key='finish_workout') for _ in range(5)))
        self.assertEqual(sum(bool(r.get('replayed')) for r in results),4)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutLog).where(WorkoutLog.user_id == uid)),1)
            self.assertEqual((await IdentityRepository(session).by_id(uid)).xp,10)
