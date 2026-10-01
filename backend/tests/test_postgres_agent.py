import asyncio
import os
import sys
import unittest
from decimal import Decimal
from uuid import uuid4,UUID
from fastapi import HTTPException
from sqlalchemy import func,select
from db.engine import dispose_engine
from db.session import unit_of_work
from db.models.finance import FinancialTransaction
from db.models.agent import Action,ActionAudit
from db.repositories.identity import IdentityRepository
from services.agent_actions import Actions
from services.core_writes import CoreWrites

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true','Disposable PostgreSQL required')
class PostgresAgent(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async with unit_of_work() as session:
            repo = IdentityRepository(session)
            self.uid = (await repo.create(email=f'{uuid4()}@example.test',name='Agent',password_hash='test-only')).id
            self.other = (await repo.create(email=f'{uuid4()}@example.test',name='Other',password_hash='test-only')).id

    async def asyncTearDown(self):
        await dispose_engine()

    async def proposal(self,actions):
        p = await actions.propose(self.uid,'request',0,'record_expense',
            {'amount':'48.00','category':'Alimentação','date':'2026-10-01'},'Registre um gasto de R$ 48')
        return UUID(p['action_id'])

    async def test_confirm_48_replay_and_ownership(self):
        actions = Actions()
        action_id = await self.proposal(actions)
        with self.assertRaises(HTTPException) as error:
            await actions.confirm(self.other,action_id)
        self.assertEqual(error.exception.status_code,404)
        results = await asyncio.gather(*(actions.confirm(self.uid,action_id) for _ in range(10)))
        self.assertEqual(sum(bool(r.get('replayed')) for r in results),9)
        async with unit_of_work() as session:
            amounts = list((await session.scalars(select(FinancialTransaction.amount).where(FinancialTransaction.user_id == self.uid))).all())
            self.assertEqual(amounts,[Decimal('48.00')])
            self.assertEqual(await session.scalar(select(func.count()).select_from(ActionAudit).where(ActionAudit.user_id == self.uid)),1)

    async def test_failure_after_expense_rolls_back_proposal(self):
        class FailingWriter(CoreWrites):
            async def execute(self,*args):
                await super().execute(*args)
                raise RuntimeError('injected after expense')
        actions = Actions(FailingWriter())
        action_id = await self.proposal(actions)
        with self.assertRaises(RuntimeError):
            await actions.confirm(self.uid,action_id)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id == self.uid)),0)
            self.assertEqual((await session.get(Action,action_id)).status,'pending')
        await Actions().confirm(self.uid,action_id)
