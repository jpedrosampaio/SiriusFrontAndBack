from datetime import date, datetime
from uuid import UUID
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base, Identity, Timestamps


class Owned:
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)


class Task(Identity, Owned, Timestamps, Base):
    __tablename__ = 'tasks'
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    date: Mapped[date] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(default='medium')
    recurrence: Mapped[str] = mapped_column(default='once')
    completed: Mapped[bool] = mapped_column(default=False)
    xp_reward: Mapped[int] = mapped_column(default=10)
    __table_args__ = (UniqueConstraint('user_id', 'id'), Index('ix_tasks_owner_date', 'user_id', 'date'),
        CheckConstraint("priority IN ('low','medium','high')", name='priority'),
        CheckConstraint("recurrence IN ('once','daily','weekly','monthly')", name='recurrence'))


class TaskInstance(Identity, Owned, Base):
    __tablename__ = 'task_instances'
    task_id: Mapped[UUID]
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(default='todo')
    completed: Mapped[bool] = mapped_column(default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['user_id','task_id'], ['tasks.user_id','tasks.id'], ondelete='CASCADE'),
        UniqueConstraint('user_id','task_id','date'), CheckConstraint("status IN ('todo','in_progress','done')", name='status'),
        CheckConstraint("completed = (status = 'done')", name='completion_status'))


class Habit(Identity, Owned, Timestamps, Base):
    __tablename__ = 'habits'
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(default='#007AFF')
    __table_args__ = (UniqueConstraint('user_id','id'),)


class HabitCheck(Identity, Owned, Base):
    __tablename__ = 'habit_checks'
    habit_id: Mapped[UUID]
    date: Mapped[date] = mapped_column(Date)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['user_id','habit_id'], ['habits.user_id','habits.id'], ondelete='RESTRICT'),
        UniqueConstraint('user_id','habit_id','date'))


class Goal(Identity, Owned, Timestamps, Base):
    __tablename__ = 'goals'
    title: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    target_date: Mapped[date] = mapped_column(Date)
    progress: Mapped[float] = mapped_column(default=0)
    sprint_duration: Mapped[int] = mapped_column(default=60)
    __table_args__ = (UniqueConstraint('user_id','id'), CheckConstraint('progress BETWEEN 0 AND 100', name='progress'))


class GoalCheck(Identity, Owned, Base):
    __tablename__ = 'goal_checks'
    goal_id: Mapped[UUID]
    date: Mapped[date] = mapped_column(Date)
    __table_args__ = (ForeignKeyConstraint(['user_id','goal_id'], ['goals.user_id','goals.id'], ondelete='RESTRICT'),
        UniqueConstraint('user_id','goal_id','date'))


class CalendarEvent(Identity, Owned, Timestamps, Base):
    __tablename__ = 'calendar_events'
    title: Mapped[str]
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str | None]
    source_id: Mapped[UUID | None]
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (Index('ix_calendar_owner_start','user_id','start_at'),
        CheckConstraint('end_at >= start_at', name='interval'))
