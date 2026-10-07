"""Bounded assistant projections over owned SQL domain records."""
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select, func
from db.models.identity import User
from db.models.planning import Habit, HabitCheck, Goal, CalendarEvent
from db.models.finance import FinancialTransaction, Budget
from db.models.studies import Notebook, StudyProgram, StudyTopic, StudySession, QuestionAttempt, ReviewEvent, StudyPlan, StudyPlanEntry
from db.models.health import WorkoutPlan, WorkoutDay, WorkoutLog
from db.models.files import FileRecord, EditalAnalysis
from db.repositories.planning import PlanningRepository
from db.session import unit_of_work
from services.time import local_today
from services.nutrition_data import period, MACROS


async def user_day(user_id):
    async with unit_of_work() as session:
        user = await session.get(User, UUID(str(user_id)))
        if user is None:
            raise HTTPException(404, 'User not found')
        return local_today(user.timezone)


async def page_context(user_id, raw):
    try:
        context = json.loads(raw) if isinstance(raw, str) else raw
        query = parse_qs(str(context.get('query', ''))[:1000].lstrip('?'))
    except (ValueError, TypeError, AttributeError):
        return {}
    selected = {}
    uid = UUID(str(user_id))
    async with unit_of_work() as session:
        for parameter, model, field, title in (
            ('program', StudyProgram, 'program_id', StudyProgram.name),
            ('notebook', Notebook, 'notebook_id', Notebook.name),
            ('analysis', EditalAnalysis, 'analysis_id', EditalAnalysis.filename),
            ('attachment', FileRecord, 'attachment_id', FileRecord.filename),
        ):
            value = context.get(field) or next(iter(query.get(parameter, [])), None)
            try:
                identity = UUID(value) if isinstance(value, str) else None
            except ValueError:
                continue
            if identity is None:
                continue
            statement = select(model.id, title).where(model.user_id == uid, model.id == identity)
            if hasattr(model, 'archived_at'):
                statement = statement.where(model.archived_at.is_(None))
            row = (await session.execute(statement)).first()
            if row:
                selected[parameter] = {field: str(row[0]), 'name' if parameter in ('program', 'notebook') else 'title': row[1]}
        key = context.get('topic_key') or next(iter(query.get('topic', [])), None)
        if 'notebook' in selected and isinstance(key, str) and re.fullmatch(r'\d+(?:_\d+)?', key):
            title = await session.scalar(select(StudyTopic.name).where(StudyTopic.user_id == uid,
                StudyTopic.notebook_id == UUID(selected['notebook']['notebook_id']), StudyTopic.topic_key == key, StudyTopic.archived_at.is_(None)))
            if title is not None:
                selected['topic'] = {'key': key, 'title': title}
    return selected


async def read(name, user_id):
    uid = UUID(str(user_id))
    async with unit_of_work() as session:
        user = await session.get(User, uid)
        if user is None:
            raise HTTPException(404, 'User not found')
        day = local_today(user.timezone)
        start = day.replace(day=1)
        if name in ('get_today_tasks', 'get_tasks'):
            pairs = await PlanningRepository(session).tasks_on_date(uid, day)
            # Display limits must never drop temporal constraints from the planner.
            selected = pairs[:60] + [(task, instance) for task, instance in pairs[60:] if task.scheduled_time is not None]
            return {'date': day.isoformat(), 'timezone': user.timezone, 'total': len(pairs),
                'completed': sum(bool(instance and instance.completed) for task, instance in pairs),
                'items': [{'task_id': str(task.id), 'title': task.title, 'priority': task.priority,
                    'date': task.date.isoformat(), 'recurrence': task.recurrence, 'duration_minutes': task.duration_minutes,
                    'scheduled_time': task.scheduled_time.strftime('%H:%M') if task.scheduled_time else None,
                    'completed': bool(instance and instance.completed)} for task, instance in selected], 'truncated': len(selected) < len(pairs)}
        if name == 'get_habits':
            rows = (await session.execute(select(Habit, HabitCheck.id).outerjoin(HabitCheck,
                (HabitCheck.habit_id == Habit.id) & (HabitCheck.user_id == Habit.user_id) & (HabitCheck.date == day))
                .where(Habit.user_id == uid, Habit.archived_at.is_(None)).order_by(Habit.created_at, Habit.id).limit(30))).all()
            return [{'habit_id': str(row.id), 'name': row.name, 'completed_today': check is not None} for row, check in rows]
        if name == 'get_finance_summary':
            totals = dict((await session.execute(select(FinancialTransaction.type, func.sum(FinancialTransaction.amount)).where(
                FinancialTransaction.user_id == uid, FinancialTransaction.date.between(start, day)).group_by(FinancialTransaction.type))).all())
            income, expense = (totals.get(key, Decimal('0.00')) for key in ('income', 'expense'))
            return {'start': start.isoformat(), 'end': day.isoformat(), 'income': income, 'expense': expense, 'balance': income-expense}
        if name == 'get_budget_status':
            spent = select(FinancialTransaction.category, func.sum(FinancialTransaction.amount).label('amount')).where(
                FinancialTransaction.user_id == uid, FinancialTransaction.type == 'expense', FinancialTransaction.date.between(start, day)
            ).group_by(FinancialTransaction.category).subquery()
            rows = (await session.execute(select(Budget, func.coalesce(spent.c.amount, 0)).outerjoin(spent, spent.c.category == Budget.category)
                .where(Budget.user_id == uid, Budget.month == start).order_by(Budget.created_at, Budget.id).limit(30))).all()
            return [{'budget_id': str(row.id), 'category': row.category, 'amount': row.limit, 'limit': row.limit, 'spent': amount} for row, amount in rows]
        if name == 'get_study_progress':
            minutes = select(func.coalesce(func.sum(StudySession.duration_minutes), 0)).where(StudySession.user_id == uid,
                StudySession.notebook_id == Notebook.id, StudySession.completed.is_(True)).correlate(Notebook).scalar_subquery()
            rows = (await session.execute(select(Notebook, minutes).where(Notebook.user_id == uid, Notebook.archived_at.is_(None))
                .order_by(Notebook.created_at, Notebook.id).limit(30))).all()
            return [{'notebook_id': str(book.id), 'name': book.name, 'program_id': str(book.program_id) if book.program_id else None,
                'total_study_time_minutes': total} for book, total in rows]
        if name == 'get_wrong_questions':
            latest = select(ReviewEvent).where(ReviewEvent.user_id == uid).distinct(ReviewEvent.topic_id).order_by(
                ReviewEvent.topic_id, ReviewEvent.reviewed_at.desc(), ReviewEvent.id.desc()).subquery()
            attempts = select(QuestionAttempt).where(QuestionAttempt.user_id == uid).distinct(QuestionAttempt.topic_id).order_by(
                QuestionAttempt.topic_id, QuestionAttempt.answered_at.desc(), QuestionAttempt.id.desc()).subquery()
            rows = (await session.execute(select(StudyTopic, Notebook.program_id, latest.c.next_review, attempts.c.total, attempts.c.correct)
                .join(Notebook, (Notebook.id == StudyTopic.notebook_id) & (Notebook.user_id == StudyTopic.user_id))
                .join(latest, latest.c.topic_id == StudyTopic.id).outerjoin(attempts, attempts.c.topic_id == StudyTopic.id)
                .where(StudyTopic.user_id == uid, StudyTopic.archived_at.is_(None), Notebook.archived_at.is_(None))
                .order_by(latest.c.next_review, StudyTopic.id).limit(30))).all()
            return [{'topic_key': topic.topic_key, 'title': topic.name, 'notebook_id': str(topic.notebook_id),
                'program_id': str(program) if program else None, 'due_date': due.isoformat() if due else None,
                'total': total or 0, 'correct': correct or 0, 'accuracy': round(correct/total*100, 1) if total else 0}
                for topic, program, due, total, correct in rows]
        if name == 'get_next_study_block':
            rows = (await session.execute(select(StudyPlanEntry, StudyPlan.program_id)
                .join(StudyPlan, (StudyPlan.id == StudyPlanEntry.plan_id) & (StudyPlan.user_id == StudyPlanEntry.user_id))
                .join(StudyProgram, (StudyProgram.id == StudyPlan.program_id) & (StudyProgram.user_id == StudyPlan.user_id))
                .join(Notebook, (Notebook.id == StudyPlanEntry.notebook_id) & (Notebook.user_id == StudyPlanEntry.user_id))
                .where(StudyPlanEntry.user_id == uid, StudyPlanEntry.date >= day, StudyPlanEntry.completed.is_(False),
                    StudyProgram.archived_at.is_(None), Notebook.archived_at.is_(None))
                .order_by(StudyPlanEntry.date, StudyPlanEntry.id).limit(5))).all()
            return [{'entry_id': str(row.id), 'program_id': str(program), 'notebook_id': str(row.notebook_id),
                'date': row.date.isoformat(), 'name': row.name, 'minutes': row.minutes, 'kind': row.kind,
                'completed': row.completed, 'manual': row.manual, 'fixed': row.fixed, 'reason': row.reason} for row, program in rows]
        if name == 'get_active_workout':
            weeks = select(func.max(WorkoutDay.week)).where(WorkoutDay.user_id == uid, WorkoutDay.plan_id == WorkoutPlan.id).correlate(WorkoutPlan).scalar_subquery()
            rows = (await session.execute(select(WorkoutPlan.id, WorkoutPlan.name, weeks).where(WorkoutPlan.user_id == uid,
                WorkoutPlan.archived_at.is_(None)).order_by(WorkoutPlan.created_at.desc(), WorkoutPlan.id).limit(5))).all()
            return [{'plan_id': str(identity), 'name': title, 'duration_weeks': duration or 0, 'active': True} for identity, title, duration in rows]
        if name == 'get_workout_progress':
            count, minutes = (await session.execute(select(func.count(), func.coalesce(func.sum(WorkoutLog.duration_minutes), 0)).where(
                WorkoutLog.user_id == uid, WorkoutLog.completed.is_(True), WorkoutLog.date.between(start, day)))).one()
            return {'sessions': count, 'minutes': minutes}
        if name == 'get_nutrition_today':
            meals, _, _ = await period(session, uid, day, day)
            return {'total_'+key: meals.get(day, {}).get(key, 0) for key in MACROS}
        if name == 'get_calendar':
            zone = ZoneInfo(user.timezone)
            lower = datetime.combine(day, datetime.min.time(), zone)
            upper = datetime.combine(day+timedelta(days=1), datetime.min.time(), zone)
            rows = (await session.scalars(select(CalendarEvent).where(CalendarEvent.user_id == uid,
                CalendarEvent.start_at < upper, CalendarEvent.end_at > lower).order_by(CalendarEvent.start_at, CalendarEvent.id))).all()
            # All commitments must reserve capacity; truncating this list could suggest occupied time.
            result = []
            for row in rows:
                begin, end = max(row.start_at.astimezone(zone), lower), min(row.end_at.astimezone(zone), upper)
                result.append({'event_id': str(row.id), 'title': row.title, 'date': day.isoformat(),
                    'start_minute': begin.hour*60+begin.minute, 'end_minute': 1440 if end == upper else end.hour*60+end.minute})
            return result
        if name in ('get_goals', 'get_upcoming_deadlines'):
            statement = select(Goal).where(Goal.user_id == uid, Goal.archived_at.is_(None))
            if name == 'get_upcoming_deadlines':
                statement = statement.where(Goal.progress < 100).order_by(Goal.target_date, Goal.id).limit(10)
            else:
                statement = statement.order_by(Goal.created_at, Goal.id).limit(30)
            rows = (await session.scalars(statement)).all()
            return [{'goal_id': str(row.id), 'title': row.title, 'progress': row.progress,
                'target_date': row.target_date.isoformat(), 'completed': row.progress >= 100} for row in rows]
    raise ValueError('Unknown read tool')
