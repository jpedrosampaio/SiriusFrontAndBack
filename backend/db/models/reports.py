from datetime import date
from decimal import Decimal
from sqlalchemy import Date,Index,Numeric,Text,CheckConstraint,UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped,mapped_column
from db.base import Base,Identity,Timestamps
from db.models.planning import Owned

class Report(Identity,Owned,Timestamps,Base):
    __tablename__='reports'
    type: Mapped[str]
    start_date: Mapped[date]=mapped_column(Date)
    end_date: Mapped[date]=mapped_column(Date)
    insights: Mapped[str]=mapped_column(Text)
    definitions: Mapped[str]=mapped_column(Text)
    tasks: Mapped[int]
    tasks_completed: Mapped[int]
    habits: Mapped[int]
    total_habits_completions: Mapped[int]
    income: Mapped[Decimal]=mapped_column(Numeric(18,2))
    expenses: Mapped[Decimal]=mapped_column(Numeric(18,2))
    goals: Mapped[int]
    goals_progress: Mapped[float]
    goal_checks: Mapped[int]
    study_minutes: Mapped[int]
    questions_answered: Mapped[int]
    questions_correct: Mapped[int]
    workouts: Mapped[int]
    workout_minutes: Mapped[int]
    meals: Mapped[int]
    calories: Mapped[float]
    protein: Mapped[float]
    water_ml: Mapped[int]
    __table_args__=(Index('ix_reports_owner_created','user_id','created_at'),CheckConstraint('end_date >= start_date',name='period'))


class DailySummary(Identity,Owned,Timestamps,Base):
    __tablename__='daily_summaries'
    date: Mapped[date]=mapped_column(Date)
    greeting: Mapped[str]=mapped_column(Text)
    progress_summary: Mapped[str]=mapped_column(Text)
    pending_items: Mapped[list[str]]=mapped_column(ARRAY(Text))
    motivation: Mapped[str]=mapped_column(Text)
    priority_action: Mapped[str]=mapped_column(Text)
    score: Mapped[int]
    tasks_pending: Mapped[int]
    tasks_done: Mapped[int]
    habits_pending: Mapped[int]
    habits_done: Mapped[int]
    study_minutes: Mapped[int]
    meals_count: Mapped[int]
    calories: Mapped[int]
    workouts_count: Mapped[int]
    __table_args__=(UniqueConstraint('user_id','date'),CheckConstraint('score BETWEEN 0 AND 100',name='score'))
