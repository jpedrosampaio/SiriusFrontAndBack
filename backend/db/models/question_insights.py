from uuid import UUID
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class QuestionInsight(Identity,Owned,Timestamps,Base):
    __tablename__='question_insights'
    program_id: Mapped[UUID]
    fingerprint: Mapped[str]
    status: Mapped[str] = mapped_column(default='active')
    details: Mapped[dict] = mapped_column(JSONB)
    __table_args__=(UniqueConstraint('user_id','program_id','fingerprint'),
        ForeignKeyConstraint(['user_id','program_id'],['study_programs.user_id','study_programs.id'],ondelete='RESTRICT'),
        CheckConstraint("status IN ('active','dismissed','superseded')",name='status'),
        Index('ix_question_insights_owner_program_status','user_id','program_id','status'))
