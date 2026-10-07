from datetime import date
from decimal import Decimal, InvalidOperation
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.finance import FinancialTransaction


def money(value) -> Decimal:
    if isinstance(value, float):
        raise ValueError('Money must enter as Decimal or decimal text, never binary float')
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount != amount.quantize(Decimal('0.01')):
            raise ValueError('Money requires at most two decimal places')
        if abs(amount) > Decimal('1000000000'):
            raise ValueError('Money exceeds the supported amount')
        return amount.quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid monetary amount') from None


class FinanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id, *, type, amount, category, date, description=None, category_id=None):
        row = FinancialTransaction(user_id=user_id, type=type, amount=money(amount), category=category,
                                   category_id=category_id, date=date, description=description)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, user_id, transaction_id):
        return await self.session.scalar(select(FinancialTransaction).where(
            FinancialTransaction.user_id == user_id, FinancialTransaction.id == transaction_id))

    async def period_totals(self, user_id, start: date, end_exclusive: date):
        row = (await self.session.execute(select(
            func.coalesce(func.sum(FinancialTransaction.amount).filter(FinancialTransaction.type == 'income'), 0),
            func.coalesce(func.sum(FinancialTransaction.amount).filter(FinancialTransaction.type == 'expense'), 0),
        ).where(FinancialTransaction.user_id == user_id, FinancialTransaction.date >= start,
                FinancialTransaction.date < end_exclusive))).one()
        return {'income': row[0], 'expense': row[1], 'balance': row[0] - row[1]}

    async def list_period(self, user_id, start, end_exclusive, *, before=None, limit=100):
        statement = select(FinancialTransaction).where(FinancialTransaction.user_id == user_id,
            FinancialTransaction.date >= start, FinancialTransaction.date < end_exclusive)
        if before:
            from sqlalchemy import tuple_
            statement = statement.where(tuple_(FinancialTransaction.date, FinancialTransaction.id) < tuple_(*before))
        return list((await self.session.scalars(statement.order_by(FinancialTransaction.date.desc(), FinancialTransaction.id.desc()).limit(min(max(limit,1),200)))).all())
