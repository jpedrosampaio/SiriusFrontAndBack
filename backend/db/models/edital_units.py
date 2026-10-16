"""Small owned checkpoints; completed proposals are immutable across reruns."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class EditalUnit(Identity, Owned, Timestamps, Base):
    __tablename__ = 'edital_analysis_units'
    analysis_id: Mapped[UUID]
    job_id: Mapped[UUID]
    generation: Mapped[UUID]
    scope_key: Mapped[str]
    unit_key: Mapped[str]
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default='pending')
    source_blocks: Mapped[list] = mapped_column(JSONB,default=list)
    context_blocks: Mapped[list] = mapped_column(JSONB,default=list)
    attempts: Mapped[int] = mapped_column(default=0)
    provider_calls: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    lease_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    diagnostics: Mapped[dict] = mapped_column(JSONB,default=dict)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('user_id','analysis_id','generation','scope_key','unit_key'),
        ForeignKeyConstraint(['user_id','analysis_id'],['edital_analyses.user_id','edital_analyses.id'],ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id','job_id'],['edital_jobs.user_id','edital_jobs.id'],ondelete='CASCADE'),
        CheckConstraint("kind IN ('inventory','scope','detail','verify')",name='kind'),
        CheckConstraint("status IN ('pending','running','completed','failed','quota','waiting_provider','cancelled','split')",name='status'),
        CheckConstraint('attempts BETWEEN 0 AND 3 AND provider_calls BETWEEN 0 AND 12',name='attempts'),
        CheckConstraint('length(unit_key) = 64 AND length(scope_key) BETWEEN 1 AND 100',name='keys'),
        CheckConstraint("status != 'completed' OR (result IS NOT NULL AND jsonb_typeof(result) = 'object' AND finished_at IS NOT NULL)",name='completed_result'),
        CheckConstraint("status != 'running' OR (lease_token IS NOT NULL AND lease_until IS NOT NULL)",name='running_lease'),
        Index('ix_edital_units_claim','status','available_at','created_at'),
        Index('ix_edital_units_scope','user_id','analysis_id','generation','scope_key','status'),
    )
