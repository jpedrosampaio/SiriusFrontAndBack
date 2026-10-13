from datetime import datetime
from uuid import UUID
from sqlalchemy import BigInteger,DateTime,ForeignKey,Text,UniqueConstraint,func,CheckConstraint,Index
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from db.base import Base,Identity
from db.models.planning import Owned


class TelegramLink(Identity,Owned,Base):
    __tablename__='telegram_links'
    chat_id: Mapped[int] = mapped_column(BigInteger,unique=True)
    telegram_name: Mapped[str]
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('user_id'),)


class TelegramCode(Identity,Owned,Base):
    __tablename__='telegram_link_codes'
    code_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('user_id'),)


class TelegramUpdate(Base):
    """Typed transport receipt; transaction writes and reply complete atomically."""
    __tablename__='telegram_updates'
    update_id: Mapped[int] = mapped_column(BigInteger,primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'),index=True)
    request_hash: Mapped[str]
    lease_token: Mapped[UUID | None]
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reply: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    binding_id: Mapped[UUID | None]
    delivery_status: Mapped[str] = mapped_column(default='pending', server_default='pending')
    delivery_attempts: Mapped[int] = mapped_column(default=0, server_default='0')
    next_delivery_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivery_error: Mapped[str | None]
    provider_receipt: Mapped[str | None]
    delivery_history: Mapped[list] = mapped_column(JSONB,default=list,server_default='[]')
    __table_args__=(CheckConstraint('delivery_attempts >= 0 AND delivery_attempts <= 8',name='delivery_attempts'),
        CheckConstraint("delivery_status IN ('pending','processing','delivered','failed','cancelled','uncertain')",name='delivery_status'),
        Index('ix_telegram_delivery_ready','delivery_status','next_delivery_at','lease_until'))
