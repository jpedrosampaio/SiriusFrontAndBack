import asyncio
import os
import sys
import unittest
from datetime import date, datetime, timezone
from uuid import uuid4
from db.engine import dispose_engine
from db.session import unit_of_work
from db.repositories.identity import IdentityRepository
from db.repositories.planning import PlanningRepository
from services.planning import set_task_completion, set_habit_completion
from services.time import local_today

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class PostgresPlanning(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await dispose_engine()

    async def test_mixed_activity_writers_and_undo(self):
        async with unit_of_work() as session:
            user = await IdentityRepository(session).create(email=f'{uuid4()}@example.test',name='Planning',password_hash='test-only')
            uid = user.id
            repo = PlanningRepository(session)
            task = await repo.create_task(uid, title='Monthly',date=date(2026,1,31),recurrence='monthly')
            habit = await repo.create_habit(uid, name='Daily')
            task_id,habit_id = task.id,habit.id
            self.assertEqual(len(await repo.tasks_on_date(uid,date(2026,2,28))),1)
            self.assertEqual(len(await repo.tasks_on_date(uid,date(2026,2,27))),0)
        day = date(2026,2,28)
        await asyncio.gather(*[set_task_completion(uid,task_id,day,'done') for _ in range(5)],
            *[set_habit_completion(uid,habit_id,day,True) for _ in range(5)])
        async with unit_of_work() as session:
            self.assertEqual((await IdentityRepository(session).by_id(uid)).xp,18)
            self.assertEqual(await PlanningRepository(session).habit_dates(uid,habit_id),[day])
        await asyncio.gather(set_task_completion(uid,task_id,day,'in_progress'),set_habit_completion(uid,habit_id,day,False))
        async with unit_of_work() as session:
            self.assertEqual((await IdentityRepository(session).by_id(uid)).xp,0)
            self.assertEqual((await PlanningRepository(session).task_instance(uid,task_id,day)).status,'in_progress')


class UserTimezone(unittest.TestCase):
    def test_midnight_is_users_calendar_day(self):
        instant = datetime(2026,10,1,1,30,tzinfo=timezone.utc)
        self.assertEqual(local_today('America/Sao_Paulo',now=instant),date(2026,9,30))
        self.assertEqual(local_today('Asia/Tokyo',now=instant),date(2026,10,1))
        with self.assertRaises(ValueError):
            local_today('UTC',now=datetime(2026,10,1))
