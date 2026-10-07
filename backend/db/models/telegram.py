from datetime import datetime
from uuid import UUID
from sqlalchemy import BigInteger,DateTime,ForeignKey,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
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
