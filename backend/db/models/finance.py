from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlalchemy import CheckConstraint, Date, ForeignKeyConstraint, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class Category(Identity, Owned, Base):
    __tablename__ = 'finance_categories'
    name: Mapped[str]
    type: Mapped[str]
    __table_args__ = (UniqueConstraint('user_id','id'), UniqueConstraint('user_id','name','type'),
        CheckConstraint("type IN ('income','expense')", name='type'))


class FinancialTransaction(Identity, Owned, Timestamps, Base):
    __tablename__ = 'financial_transactions'
    type: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2))
    category_id: Mapped[UUID | None]
    category: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    date: Mapped[date] = mapped_column(Date)
    __table_args__ = (ForeignKeyConstraint(['user_id','category_id'], ['finance_categories.user_id','finance_categories.id'], ondelete='RESTRICT'),
        Index('ix_transactions_owner_date','user_id','date'),
        CheckConstraint("type IN ('income','expense')", name='type'), CheckConstraint('amount > 0', name='amount'))


class Budget(Identity, Owned, Timestamps, Base):
    __tablename__ = 'budgets'
    category: Mapped[str]
    month: Mapped[date] = mapped_column(Date)
    limit: Mapped[Decimal] = mapped_column(Numeric(18,2))
    __table_args__ = (UniqueConstraint('user_id','category','month'),
        CheckConstraint('"limit" >= 0', name='limit'), CheckConstraint('EXTRACT(DAY FROM month) = 1', name='month_start'))


class CreditCard(Identity, Owned, Timestamps, Base):
    __tablename__ = 'credit_cards'
    name: Mapped[str]
    limit: Mapped[Decimal] = mapped_column(Numeric(18,2))
    closing_day: Mapped[int]
    due_day: Mapped[int]
    color: Mapped[str] = mapped_column(default='#007AFF')
    __table_args__ = (UniqueConstraint('user_id','id'), CheckConstraint('closing_day BETWEEN 1 AND 31', name='closing_day'),
        CheckConstraint('due_day BETWEEN 1 AND 31', name='due_day'), CheckConstraint('"limit" >= 0', name='limit'))
