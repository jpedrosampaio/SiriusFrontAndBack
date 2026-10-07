from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKeyConstraint, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class Category(Identity, Owned, Base):
    __tablename__ = 'finance_categories'
    name: Mapped[str]
    type: Mapped[str]
    icon: Mapped[str] = mapped_column(default='')
    color: Mapped[str] = mapped_column(default='')
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
    purchase_id: Mapped[UUID | None]
    bill_id: Mapped[UUID | None]
    __table_args__ = (UniqueConstraint('user_id','id'), UniqueConstraint('user_id','bill_id'),
        ForeignKeyConstraint(['user_id','purchase_id'], ['card_purchases.user_id','card_purchases.id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','bill_id'], ['monthly_bills.user_id','monthly_bills.id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','category_id'], ['finance_categories.user_id','finance_categories.id'], ondelete='RESTRICT'),
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


class CardPurchase(Identity, Owned, Timestamps, Base):
    __tablename__ = 'card_purchases'
    card_id: Mapped[UUID]
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str]
    payment_type: Mapped[str]
    installments: Mapped[int]
    first_month: Mapped[date] = mapped_column(Date)
    start_month: Mapped[str]
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','card_id'], ['credit_cards.user_id','credit_cards.id'], ondelete='RESTRICT'),
        CheckConstraint('amount > 0 AND installments BETWEEN 1 AND 120',name='amount_installments'))


class Invoice(Identity, Owned, Timestamps, Base):
    __tablename__ = 'card_invoices'
    card_id: Mapped[UUID]
    month: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2))
    paid: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (ForeignKeyConstraint(['user_id','card_id'], ['credit_cards.user_id','credit_cards.id'],ondelete='RESTRICT'),
        UniqueConstraint('user_id','card_id','month'),CheckConstraint('amount >= 0',name='amount'))


class Projection(Identity, Owned, Timestamps, Base):
    __tablename__ = 'financial_projections'
    month: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2))
    category: Mapped[str]
    projection_type: Mapped[str] = mapped_column(default='manual')
    is_fixed: Mapped[bool] = mapped_column(default=False)
    repeat_count: Mapped[int | None]
    remaining_repeats: Mapped[int | None]
    purchase_id: Mapped[UUID | None]
    installment_number: Mapped[int | None]
    total_installments: Mapped[int | None]
    card_id: Mapped[UUID | None]
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','purchase_id'],['card_purchases.user_id','card_purchases.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','card_id'],['credit_cards.user_id','credit_cards.id'],ondelete='RESTRICT'),
        Index('ix_projections_owner_month','user_id','month'),CheckConstraint('amount > 0',name='amount'))


class MonthlyBill(Identity, Owned, Timestamps, Base):
    __tablename__ = 'monthly_bills'
    month: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2))
    category: Mapped[str]
    paid: Mapped[bool] = mapped_column(default=False)
    paid_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(default='manual')
    projection_id: Mapped[UUID | None]
    card_id: Mapped[UUID | None]
    installment_info: Mapped[str | None]
    __table_args__ = (UniqueConstraint('user_id','id'),UniqueConstraint('user_id','projection_id'),
        ForeignKeyConstraint(['user_id','projection_id'],['financial_projections.user_id','financial_projections.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','card_id'],['credit_cards.user_id','credit_cards.id'],ondelete='RESTRICT'),
        Index('ix_bills_owner_month','user_id','month'),CheckConstraint('amount > 0',name='amount'))
