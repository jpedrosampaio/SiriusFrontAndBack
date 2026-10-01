"""Real PostgreSQL tests. Requires an empty disposable DB upgraded with Alembic."""
import asyncio
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from db.activity import run_activity
from db.engine import dispose_engine
from db.models.identity import User, ActivityReceipt
from db.models.finance import Category, FinancialTransaction
from db.models.studies import StudyArea, StudyProgram, Notebook, QuestionAttempt
from db.repositories.identity import IdentityRepository
from db.repositories.finance import FinanceRepository, money
from db.session import unit_of_work

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class PostgresFoundation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async with unit_of_work() as session:
            repository = IdentityRepository(session)
            self.alice = (await repository.create(email=f'{uuid4()}@example.test', name='Alice', password_hash='test-only')).id
            self.bob = (await repository.create(email=f'{uuid4()}@example.test', name='Bob', password_hash='test-only')).id

    async def asyncTearDown(self):
        await dispose_engine()

    async def test_money_exact_and_owned(self):
        async with unit_of_work() as session:
            repo = FinanceRepository(session)
            first = await repo.create(self.alice, type='expense', amount='0.10', category='test', date=date(2026,10,1))
            await repo.create(self.alice, type='expense', amount='0.20', category='test', date=date(2026,10,1))
            await repo.create(self.bob, type='expense', amount='99.99', category='test', date=date(2026,10,1))
            totals = await repo.period_totals(self.alice, date(2026,10,1), date(2026,11,1))
            self.assertEqual(totals['expense'], Decimal('0.30'))
            self.assertIsNone(await repo.get(self.bob, first.id))

    async def test_rollback_domain_and_xp(self):
        async def fail(session, user):
            await FinanceRepository(session).create(user.id, type='expense', amount='48', category='test', date=date(2026,10,1))
            user.xp += 10
            await session.flush()
            raise RuntimeError('injected failure after all writes')
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            await run_activity(self.alice, 'rollback_test', ['test'], fail)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id == self.alice)), 0)
            self.assertEqual((await IdentityRepository(session).by_id(self.alice)).xp, 0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(ActivityReceipt).where(ActivityReceipt.user_id == self.alice)), 0)

    async def test_concurrent_idempotency_one_expense(self):
        async def apply(session, user):
            row = await FinanceRepository(session).create(user.id, type='expense', amount='48', category='test', date=date(2026,10,1))
            user.xp += 10
            return {'transaction_id': str(row.id)}
        results = await asyncio.gather(*(run_activity(self.alice, 'expense_48', ['expense','48'], apply) for _ in range(10)))
        self.assertEqual(len({r['transaction_id'] for r in results}), 1)
        self.assertEqual(sum(bool(r.get('replayed')) for r in results), 9)
        async with unit_of_work() as session:
            self.assertEqual((await IdentityRepository(session).by_id(self.alice)).xp, 10)
            self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id == self.alice)), 1)

    async def test_cross_owner_fk_rejected(self):
        async with unit_of_work() as session:
            category = Category(user_id=self.bob, name='Bob only', type='expense')
            session.add(category)
            await session.flush()
            category_id = category.id
        with self.assertRaises(IntegrityError):
            async with unit_of_work() as session:
                await FinanceRepository(session).create(self.alice, type='expense', amount='1', category='Bob only',
                    category_id=category_id, date=date(2026,10,1))

    async def test_session_expiry_revocation_and_sql_injection(self):
        token = uuid4().hex
        async with unit_of_work() as session:
            repo = IdentityRepository(session)
            await repo.add_session(self.alice, token, datetime.now(timezone.utc)+timedelta(hours=1))
            self.assertEqual((await repo.authenticated(token)).id, self.alice)
            self.assertIsNone(await repo.by_email("' OR 1=1 --"))
            await repo.revoke(token)
            self.assertIsNone(await repo.authenticated(token))
            await repo.add_session(self.alice, token, datetime.now(timezone.utc)-timedelta(seconds=1))
            self.assertIsNone(await repo.authenticated(token))
            self.assertGreaterEqual(await repo.expire_sessions(), 1)

    async def test_study_relationships_and_facts(self):
        async with unit_of_work() as session:
            area = StudyArea(user_id=self.alice, name='Studies')
            session.add(area)
            await session.flush()
            program = StudyProgram(user_id=self.alice, area_id=area.id, name='Preparation')
            session.add(program)
            await session.flush()
            notebook = Notebook(user_id=self.alice, area_id=area.id, program_id=program.id, name='Portuguese')
            session.add(notebook)
            await session.flush()
            notebook_id = notebook.id
            session.add(QuestionAttempt(user_id=self.alice, notebook_id=notebook.id, source='manual', total=10, correct=7,
                answered_at=datetime.now(timezone.utc)))
        with self.assertRaises(IntegrityError):
            async with unit_of_work() as session:
                session.add(QuestionAttempt(user_id=self.bob, notebook_id=notebook_id, source='manual', total=10, correct=7,
                    answered_at=datetime.now(timezone.utc)))
        with self.assertRaises(IntegrityError):
            async with unit_of_work() as session:
                session.add(QuestionAttempt(user_id=self.alice, notebook_id=notebook_id, source='manual', total=10, correct=11,
                    answered_at=datetime.now(timezone.utc)))


class MoneyValidation(unittest.TestCase):
    def test_money_boundary(self):
        self.assertEqual(money('0.10') + money('0.20'), Decimal('0.30'))
        for value in (0.1, 'NaN', 'Infinity', '0.001'):
            with self.assertRaises(ValueError):
                money(value)


if __name__ == '__main__':
    unittest.main()
