from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class Conversation(Identity, Owned, Timestamps, Base):
    __tablename__ = 'ai_conversations'
    title: Mapped[str]
    summary: Mapped[str | None] = mapped_column(Text)
    primary: Mapped[bool] = mapped_column(default=False)
    messages: Mapped[list['Message']] = relationship(back_populates='conversation', passive_deletes=True)
    __table_args__ = (UniqueConstraint('user_id','id'),
        Index('ix_conversations_owner_updated','user_id','updated_at'),
        Index('uq_conversation_primary','user_id', unique=True, postgresql_where=primary.is_(True)))


class Message(Identity, Owned, Base):
    __tablename__ = 'ai_messages'
    conversation_id: Mapped[UUID]
    role: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    conversation: Mapped[Conversation] = relationship(back_populates='messages')
    __table_args__ = (ForeignKeyConstraint(['user_id','conversation_id'], ['ai_conversations.user_id','ai_conversations.id'], ondelete='CASCADE'),
        Index('ix_messages_conversation_created','conversation_id','created_at'),
        CheckConstraint("role IN ('user','assistant','system','tool')", name='role'))


class Memory(Identity, Owned, Timestamps, Base):
    __tablename__ = 'ai_memories'
    kind: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str]
    blocked: Mapped[bool] = mapped_column(default=False)
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (UniqueConstraint('user_id','kind','content_hash'),)


class Action(Identity, Owned, Timestamps, Base):
    __tablename__ = 'ai_actions'
    request_fingerprint: Mapped[str]
    tool: Mapped[str]
    version: Mapped[int]
    arguments: Mapped[dict] = mapped_column(JSONB)
    summary: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    autonomy: Mapped[str]
    status: Mapped[str] = mapped_column(default='pending')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint('user_id','id'), UniqueConstraint('user_id','request_fingerprint'),
        CheckConstraint("status IN ('pending','confirmed','executed','cancelled','expired')", name='status'),
        Index('ix_actions_owner_status_expiry','user_id','status','expires_at'))


class ActionAudit(Identity, Owned, Base):
    __tablename__ = 'ai_action_audit'
    action_id: Mapped[UUID]
    tool: Mapped[str]
    version: Mapped[int]
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (ForeignKeyConstraint(['user_id','action_id'], ['ai_actions.user_id','ai_actions.id'], ondelete='RESTRICT'),)


class Event(Identity, Owned, Base):
    __tablename__ = 'ai_events'
    event_type: Mapped[str]
    entity_type: Mapped[str | None]
    entity_id: Mapped[UUID | None]
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(default='pending')
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index('ix_events_status_lease','status','lease_until'), Index('ix_events_owner_created','user_id','created_at'))


class Preferences(Identity, Owned, Timestamps, Base):
    __tablename__ = 'ai_preferences'
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (UniqueConstraint('user_id'),)


class Usage(Identity, Owned, Base):
    __tablename__ = 'ai_usage'
    provider: Mapped[str]
    model: Mapped[str]
    task: Mapped[str]
    status: Mapped[str]
    duration_ms: Mapped[int]
    usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index('ix_ai_usage_owner_created','user_id','created_at'),)
