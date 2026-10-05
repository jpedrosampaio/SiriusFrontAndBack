"""Read-only SQL facts for the assistant system context."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select, func
from db.models.identity import User
from db.models.finance import FinancialTransaction
from db.models.studies import StudySession
from db.models.health import WorkoutLog
from db.repositories.planning import PlanningRepository
from db.session import unit_of_work


async def snapshot(user_id, *, now=None):
    uid = UUID(str(user_id))
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError('An instant must have a timezone')
    async with unit_of_work() as session:
        user = await session.get(User, uid)
        if user is None:
            raise HTTPException(404, 'User not found')
        local = instant.astimezone(ZoneInfo(user.timezone))
        day = local.date()
        start = day.replace(day=1)
        tasks = await PlanningRepository(session).tasks_on_date(uid, day)
        finances = dict((await session.execute(
            select(FinancialTransaction.type, func.sum(FinancialTransaction.amount))
            .where(FinancialTransaction.user_id == uid, FinancialTransaction.date.between(start, day))
            .group_by(FinancialTransaction.type)
        )).all())
        study_minutes = await session.scalar(select(func.coalesce(func.sum(StudySession.duration_minutes), 0)).where(
            StudySession.user_id == uid, StudySession.completed.is_(True), StudySession.date.between(start, day)))
        workouts = await session.scalar(select(func.count()).select_from(WorkoutLog).where(
            WorkoutLog.user_id == uid, WorkoutLog.completed.is_(True), WorkoutLog.date.between(start, day)))
        return local, {
            'user': {'name': user.name, 'xp': user.xp, 'rank': user.rank},
            'tasks_today': len(tasks),
            'tasks_done': sum(bool(instance and instance.completed) for task, instance in tasks),
            'finance_month': {kind: finances.get(kind, Decimal('0.00')) for kind in ('income', 'expense')},
            'study_minutes_month': study_minutes,
            'workouts_month': workouts,
        }
