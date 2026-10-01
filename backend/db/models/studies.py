from datetime import date, datetime, time
from uuid import UUID
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKeyConstraint, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class MindMap(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_mindmaps'
    notebook_id: Mapped[UUID | None]
    title: Mapped[str]
    nodes: Mapped[list[dict]] = mapped_column(JSONB)
    source: Mapped[str]
    __table_args__ = (ForeignKeyConstraint(['user_id','notebook_id'], ['study_notebooks.user_id','study_notebooks.id'], ondelete='RESTRICT'),
        Index('ix_mindmaps_owner_created','user_id','created_at'),
        CheckConstraint("source IN ('file','text','topic','notebook')",name='source'))


class EssayCorrection(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_essay_corrections'
    filename: Mapped[str]
    instructions: Mapped[str] = mapped_column(Text)
    correction: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (Index('ix_essays_owner_created','user_id','created_at'),)


class StudyArea(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_areas'
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(default='#007AFF')
    icon: Mapped[str] = mapped_column(default='book')
    order: Mapped[int] = mapped_column(default=0)
    __table_args__ = (UniqueConstraint('user_id','id'),)


class StudyProgram(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_programs'
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    area_id: Mapped[UUID]
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(default='#007AFF')
    icon: Mapped[str] = mapped_column(default='book')
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(default='active')
    source_type: Mapped[str] = mapped_column(default='manual')
    edital_data: Mapped[dict] = mapped_column(JSONB,default=dict)
    notebooks: Mapped[list['Notebook']] = relationship(back_populates='program', passive_deletes=True)
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','area_id'], ['study_areas.user_id','study_areas.id'], ondelete='RESTRICT'),
        CheckConstraint("status IN ('active','completed','paused')", name='status'))


class StudyTarget(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_targets'
    name: Mapped[str | None]
    exam_date: Mapped[date | None] = mapped_column(Date)
    program_id: Mapped[UUID]
    kind: Mapped[str]
    institution: Mapped[str | None]
    board: Mapped[str | None]
    edition: Mapped[str | None]
    position: Mapped[str | None]
    metadata_origin: Mapped[str] = mapped_column(default='manual')
    __table_args__ = (UniqueConstraint('user_id','program_id'),
        ForeignKeyConstraint(['user_id','program_id'], ['study_programs.user_id','study_programs.id'], ondelete='CASCADE'))


class Notebook(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_notebooks'
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weight: Mapped[float] = mapped_column(default=1)
    dificuldade: Mapped[str] = mapped_column(default='media')
    user_difficulty: Mapped[str | None]
    num_questoes_edital: Mapped[int | None]
    peso_fonte: Mapped[str] = mapped_column(default='')
    peso_status: Mapped[str] = mapped_column(default='a_conferir')
    num_questoes_fonte: Mapped[str] = mapped_column(default='')
    num_questoes_status: Mapped[str] = mapped_column(default='a_conferir')
    grupo: Mapped[str] = mapped_column(default='')
    fontes: Mapped[list] = mapped_column(JSONB,default=list)
    recursos_recomendados: Mapped[list] = mapped_column(JSONB,default=list)
    area_id: Mapped[UUID]
    program_id: Mapped[UUID | None]
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(default='#007AFF')
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    syllabus: Mapped[dict] = mapped_column(JSONB, default=dict)
    program: Mapped[StudyProgram | None] = relationship(back_populates='notebooks')
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','area_id'], ['study_areas.user_id','study_areas.id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','program_id'], ['study_programs.user_id','study_programs.id'], ondelete='RESTRICT'))


class StudyTopic(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_topics'
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notebook_id: Mapped[UUID]
    parent_id: Mapped[UUID | None]
    topic_key: Mapped[str]
    name: Mapped[str] = mapped_column(Text)
    position: Mapped[int]
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (UniqueConstraint('user_id','id'), UniqueConstraint('user_id','notebook_id','topic_key'),
        ForeignKeyConstraint(['user_id','notebook_id'], ['study_notebooks.user_id','study_notebooks.id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','parent_id'], ['study_topics.user_id','study_topics.id'], ondelete='RESTRICT'))


class TopicProgress(Identity, Owned, Timestamps, Base):
    __tablename__ = 'topic_progress'
    topic_id: Mapped[UUID]
    studied: Mapped[bool] = mapped_column(default=False)
    reviewed: Mapped[bool] = mapped_column(default=False)
    confident: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (UniqueConstraint('user_id','topic_id'),
        ForeignKeyConstraint(['user_id','topic_id'], ['study_topics.user_id','study_topics.id'], ondelete='CASCADE'))


class StudySession(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_sessions'
    notebook_id: Mapped[UUID | None]
    topic_id: Mapped[UUID | None]
    date: Mapped[date] = mapped_column(Date)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int]
    break_minutes: Mapped[int | None]
    completed: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str] = mapped_column(default='manual')
    notes: Mapped[str | None] = mapped_column(Text)
    xp_earned: Mapped[int] = mapped_column(default=0)
    __table_args__ = (ForeignKeyConstraint(['user_id','notebook_id'], ['study_notebooks.user_id','study_notebooks.id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','topic_id'], ['study_topics.user_id','study_topics.id'], ondelete='RESTRICT'),
        Index('ix_study_sessions_owner_date','user_id','date'),
        CheckConstraint('duration_minutes >= 0', name='duration'),
        CheckConstraint('completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at', name='interval'))


class QuestionAttempt(Identity, Owned, Timestamps, Base):
    __tablename__ = 'question_attempts'
    notebook_id: Mapped[UUID | None]
    topic_id: Mapped[UUID | None]
    question_id: Mapped[UUID | None]
    exam_attempt_id: Mapped[UUID | None]
    source: Mapped[str]
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total: Mapped[int] = mapped_column(default=1)
    correct: Mapped[int]
    answer: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None]
    error_cause: Mapped[str | None]
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (ForeignKeyConstraint(['user_id','notebook_id'], ['study_notebooks.user_id','study_notebooks.id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','question_id'], ['questions.user_id','questions.id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','exam_attempt_id'], ['exam_attempts.user_id','exam_attempts.id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','topic_id'], ['study_topics.user_id','study_topics.id'], ondelete='RESTRICT'),
        Index('ix_attempts_owner_answered','user_id','answered_at'), Index('ix_attempts_owner_topic','user_id','topic_id'),
        CheckConstraint('total > 0 AND correct >= 0 AND correct <= total', name='counts'),
        CheckConstraint('duration_seconds IS NULL OR duration_seconds >= 0', name='duration'))


class ReviewEvent(Identity, Owned, Base):
    __tablename__ = 'study_review_events'
    topic_id: Mapped[UUID]
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result: Mapped[str]
    next_review: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (ForeignKeyConstraint(['user_id','topic_id'], ['study_topics.user_id','study_topics.id'], ondelete='RESTRICT'),
        Index('ix_review_owner_topic_date','user_id','topic_id','reviewed_at'))


class StudyNote(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_notes'
    notebook_id: Mapped[UUID]
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    links: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    __table_args__ = (ForeignKeyConstraint(['user_id','notebook_id'], ['study_notebooks.user_id','study_notebooks.id'], ondelete='RESTRICT'),)


class Flashcard(Identity, Owned, Timestamps, Base):
    __tablename__ = 'flashcards'
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String),default=list)
    notebook_id: Mapped[UUID]
    deck_name: Mapped[str]
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    ease_factor: Mapped[float] = mapped_column(default=2.5)
    interval_days: Mapped[int] = mapped_column(default=1)
    repetitions: Mapped[int] = mapped_column(default=0)
    next_review: Mapped[date] = mapped_column(Date)
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','notebook_id'], ['study_notebooks.user_id','study_notebooks.id'], ondelete='RESTRICT'),
        Index('ix_flashcards_owner_review','user_id','next_review'))


class FlashcardReview(Identity, Owned, Base):
    __tablename__ = 'flashcard_reviews'
    flashcard_id: Mapped[UUID]
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quality: Mapped[int]
    __table_args__ = (ForeignKeyConstraint(['user_id','flashcard_id'], ['flashcards.user_id','flashcards.id'], ondelete='RESTRICT'),
        CheckConstraint('quality BETWEEN 0 AND 5', name='quality'))


class StudyPlan(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_plans'
    program_id: Mapped[UUID]
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    availability: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    block_minutes: Mapped[int]
    adaptive: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (UniqueConstraint('user_id','id'),UniqueConstraint('user_id','program_id'),
        ForeignKeyConstraint(['user_id','program_id'],['study_programs.user_id','study_programs.id'],ondelete='RESTRICT'),
        CheckConstraint('end_date >= start_date AND block_minutes BETWEEN 15 AND 120',name='settings'),
        CheckConstraint('array_length(availability,1) = 7',name='availability'))


class StudyPlanEntry(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_plan_entries'
    plan_id: Mapped[UUID]
    notebook_id: Mapped[UUID]
    date: Mapped[date] = mapped_column(Date)
    name: Mapped[str]
    minutes: Mapped[int]
    kind: Mapped[str]
    completed: Mapped[bool] = mapped_column(default=False)
    manual: Mapped[bool] = mapped_column(default=False)
    fixed: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str] = mapped_column(Text,default='')
    __table_args__ = (ForeignKeyConstraint(['user_id','plan_id'],['study_plans.user_id','study_plans.id'],ondelete='RESTRICT'),
        ForeignKeyConstraint(['user_id','notebook_id'],['study_notebooks.user_id','study_notebooks.id'],ondelete='RESTRICT'),
        Index('ix_plan_entries_owner_date','user_id','date'),CheckConstraint('minutes > 0',name='minutes'))


class StudyDraft(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_drafts'
    notebook_id: Mapped[UUID]
    topic_key: Mapped[str] = mapped_column(default='general')
    text: Mapped[str] = mapped_column(Text,default='')
    revision: Mapped[int] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint('user_id','notebook_id','topic_key'),
        ForeignKeyConstraint(['user_id','notebook_id'],['study_notebooks.user_id','study_notebooks.id'],ondelete='RESTRICT'),
        CheckConstraint('revision > 0',name='revision'))


class StudySchedule(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_schedules'
    notebook_id: Mapped[UUID]
    day_of_week: Mapped[str]
    start_time: Mapped[time]
    end_time: Mapped[time]
    repeat: Mapped[bool] = mapped_column(default=True)
    tipo_estudo: Mapped[str] = mapped_column(default='Teoria + Questões')
    prioridade: Mapped[str] = mapped_column(default='media')
    assuntos_foco: Mapped[list[str]] = mapped_column(ARRAY(String),default=list)
    __table_args__ = (ForeignKeyConstraint(['user_id','notebook_id'],['study_notebooks.user_id','study_notebooks.id'],ondelete='RESTRICT'),
        CheckConstraint('end_time > start_time',name='interval'),
        CheckConstraint("day_of_week IN ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')",name='day'))


class StudyTask(Identity, Owned, Timestamps, Base):
    __tablename__ = 'study_tasks'
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notebook_id: Mapped[UUID | None]
    title: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(default='reading')
    recurrence: Mapped[str] = mapped_column(default='once')
    deadline: Mapped[date | None] = mapped_column(Date)
    reminder: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(default='medium')
    estimated_minutes: Mapped[int] = mapped_column(default=30)
    actual_minutes: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    xp_reward: Mapped[int] = mapped_column(default=10)
    __table_args__ = (UniqueConstraint('user_id','id'),
        ForeignKeyConstraint(['user_id','notebook_id'],['study_notebooks.user_id','study_notebooks.id'],ondelete='RESTRICT'),
        CheckConstraint("priority IN ('low','medium','high')",name='priority'),
        CheckConstraint("recurrence IN ('once','daily','weekly','monthly')",name='recurrence'),
        CheckConstraint('estimated_minutes >= 0 AND actual_minutes >= 0',name='minutes'))


class StudyTaskCheck(Identity, Owned, Base):
    __tablename__ = 'study_task_checks'
    task_id: Mapped[UUID]
    date: Mapped[date] = mapped_column(Date)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    xp_earned: Mapped[int]
    __table_args__ = (UniqueConstraint('user_id','task_id','date'),
        ForeignKeyConstraint(['user_id','task_id'],['study_tasks.user_id','study_tasks.id'],ondelete='RESTRICT'))
