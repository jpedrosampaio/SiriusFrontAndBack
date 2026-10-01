from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base, Identity, Timestamps


class User(Identity, Timestamps, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(80), default='America/Sao_Paulo')
    xp: Mapped[int] = mapped_column(default=0)
    rank: Mapped[str] = mapped_column(default='Recruta')
    picture: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    credentials: Mapped[dict] = mapped_column(JSONB, default=dict)
    sessions: Mapped[list['UserSession']] = relationship(back_populates='user', passive_deletes=True)
    __table_args__ = (Index('uq_users_email_normalized', func.lower(email), unique=True),
                      CheckConstraint('xp >= 0', name='xp_nonnegative'))


class UserSession(Identity, Base):
    __tablename__ = 'user_sessions'
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user: Mapped[User] = relationship(back_populates='sessions')


class ActivityReceipt(Identity, Base):
    __tablename__ = 'activity_receipts'
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    request_key: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint('user_id', 'request_key'),)
