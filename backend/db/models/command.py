"""Small business audit: no provider prompts, credentials or duplicated ledgers."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, Index, CheckConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base, Identity
from db.models.planning import Owned


class CommandAudit(Identity, Owned, Base):
    __tablename__ = 'command_audit'
    actor: Mapped[str] = mapped_column(default='user')
    event: Mapped[str]
    action: Mapped[str]
    entity_type: Mapped[str]
    entity_id: Mapped[UUID | None]
    reason: Mapped[dict] = mapped_column(JSONB, default=dict)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    undo_kind: Mapped[str | None]
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("actor IN ('user', 'agent')", name='actor'),
        CheckConstraint("undo_kind IS NULL OR undo_kind IN ('availability', 'allocations')", name='undo_kind'),
        Index('ix_command_audit_owner_created', 'user_id', 'created_at', 'id'),
    )
