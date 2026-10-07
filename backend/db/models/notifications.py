from datetime import date,datetime,time
from uuid import UUID
from sqlalchemy import DateTime,ForeignKeyConstraint,UniqueConstraint,String,Text,CheckConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped,mapped_column
from db.base import Base,Identity,Timestamps
from db.models.planning import Owned


class Notification(Identity,Owned,Timestamps,Base):
    __tablename__='notifications'
    title: Mapped[str]
    message: Mapped[str] = mapped_column(Text)
    type: Mapped[str]
    category: Mapped[str]
    scheduled_time: Mapped[time | None]
    repeat: Mapped[str] = mapped_column(default='none')
    repeat_days: Mapped[list[str]] = mapped_column(ARRAY(String),default=list)
    enabled: Mapped[bool] = mapped_column(default=True)
    channels: Mapped[list[str]] = mapped_column(ARRAY(String),default=lambda:['in_app'])
    last_sent: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_occurrence: Mapped[date | None]
    program_id: Mapped[UUID | None]
    schedule_id: Mapped[UUID | None]
    reminder_kind: Mapped[str | None]
    __table_args__=(UniqueConstraint('user_id','id'),UniqueConstraint('user_id','schedule_id','reminder_kind'),
        ForeignKeyConstraint(['user_id','program_id'],['study_programs.user_id','study_programs.id'],ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id','schedule_id'],['study_schedules.user_id','study_schedules.id'],ondelete='CASCADE'),
        CheckConstraint("repeat IN ('none','daily','weekly','custom')",name='repeat'))


class NotificationDelivery(Identity,Owned,Base):
    __tablename__='notification_deliveries'
    notification_id: Mapped[UUID]
    occurrence: Mapped[date]
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str]
    status: Mapped[str] = mapped_column(default='sent')
    __table_args__=(ForeignKeyConstraint(['user_id','notification_id'],['notifications.user_id','notifications.id'],ondelete='CASCADE'),
        UniqueConstraint('user_id','notification_id','occurrence','channel'))
