from datetime import date, datetime
from sqlalchemy import CheckConstraint, DateTime, Index, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base, Identity, Timestamps
from db.models.planning import Owned


class Achievement(Identity, Owned, Base):
    __tablename__='achievements'
    key: Mapped[str]
    title: Mapped[str]
    description: Mapped[str]
    icon: Mapped[str]
    category: Mapped[str]
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('user_id','key'), Index('ix_achievements_owner_unlocked','user_id','unlocked_at'))


class WeeklyChallenge(Identity, Owned, Timestamps, Base):
    __tablename__='weekly_challenges'
    kind: Mapped[str]
    title: Mapped[str]
    description: Mapped[str]
    xp_reward: Mapped[int]
    week_start: Mapped[date]
    week_end: Mapped[date]
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('user_id','week_start','kind'),
        CheckConstraint('xp_reward >= 0 AND week_end > week_start',name='reward_period'))


class DailyQuote(Identity, Owned, Timestamps, Base):
    __tablename__='daily_quotes'
    motivational_date: Mapped[date]
    quote: Mapped[str] = mapped_column(Text)
    workouts_this_week: Mapped[int]
    habits_today: Mapped[int]
    time_of_day: Mapped[str]
    __table_args__=(UniqueConstraint('user_id','motivational_date'),)
