from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class Question(Identity, Owned, Timestamps, Base):
    __tablename__ = 'questions'
    notebook_id: Mapped[UUID | None]
    topic_id: Mapped[UUID | None]
    statement: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str]
    options: Mapped[list] = mapped_column(JSONB,default=list)
    correct_answer: Mapped[str | None]
    explanation: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str]
    provenance: Mapped[dict] = mapped_column(JSONB,default=dict)
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','notebook_id'],['study_notebooks.user_id','study_notebooks.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','topic_id'],['study_topics.user_id','study_topics.id'],ondelete='RESTRICT'))


class Exam(Identity, Owned, Timestamps, Base):
    __tablename__ = 'exams'
    program_id: Mapped[UUID | None]
    notebook_id: Mapped[UUID | None]
    title: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str]
    status: Mapped[str]
    duration_minutes: Mapped[int | None]
    blueprint: Mapped[dict] = mapped_column(JSONB,default=dict)
    provenance: Mapped[dict] = mapped_column(JSONB,default=dict)
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','program_id'],['study_programs.user_id','study_programs.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','notebook_id'],['study_notebooks.user_id','study_notebooks.id'],ondelete='RESTRICT'))


class ExamQuestion(Identity, Owned, Base):
    __tablename__ = 'exam_questions'
    exam_id: Mapped[UUID]
    question_id: Mapped[UUID]
    position: Mapped[int]
    weight: Mapped[float] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint('user_id','exam_id','position'),
        ForeignKeyConstraint(['user_id','exam_id'],['exams.user_id','exams.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','question_id'],['questions.user_id','questions.id'],ondelete='RESTRICT'),
        CheckConstraint('weight > 0 AND position >= 0',name='weight_position'))


class ExamAttempt(Identity, Owned, Base):
    __tablename__ = 'exam_attempts'
    exam_id: Mapped[UUID]
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int]
    score: Mapped[float]
    scoring_version: Mapped[str]
    result_details: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','exam_id'],['exams.user_id','exams.id'],ondelete='RESTRICT'),
        CheckConstraint('score BETWEEN 0 AND 100 AND duration_seconds >= 0',name='score_duration'),
        Index('ix_exam_attempt_owner_completed','user_id','completed_at'))
