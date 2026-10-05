"""Daily SQL aggregates, preserving the analytics response contract."""
from datetime import date,timedelta
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select,func,Date
from db.models.identity import User
from db.models.planning import TaskInstance,Habit,HabitCheck,XPEntry
from db.models.finance import FinancialTransaction
from db.models.studies import StudySession,QuestionAttempt
from db.models.health import WorkoutLog
from db.session import unit_of_work
from services.time import local_today
from report_metrics import utc_bounds


async def analytics_snapshot(user_id,days=7,today=None):
    days=max(1,min(90,days));uid=UUID(str(user_id))
    async with unit_of_work() as session:
        user=await session.get(User,uid)
        last=date.fromisoformat(today) if isinstance(today,str) else today or local_today(user.timezone)
        first=last-timedelta(days=days-1);dates=[(first+timedelta(days=i)).isoformat() for i in range(days)]
        async def group(model,column,fields,*filters):
            rows=(await session.execute(select(column.label('day'),*[value.label(key) for key,value in fields.items()]).where(
                model.user_id==uid,column>=first,column<=last,*filters).group_by(column))).mappings().all()
            return {row['day'].isoformat():dict(row) for row in rows}
        tasks=await group(TaskInstance,TaskInstance.date,{'n':func.count()},TaskInstance.completed.is_(True))
        habit_rows=await group(HabitCheck,HabitCheck.date,{'n':func.count()});habits={day:row['n'] for day,row in habit_rows.items()}
        habit_total=await session.scalar(select(func.count()).select_from(Habit).where(Habit.user_id==uid,Habit.archived_at.is_(None)))
        finance=await group(FinancialTransaction,FinancialTransaction.date,{key:func.coalesce(func.sum(FinancialTransaction.amount).filter(FinancialTransaction.type==key),0) for key in ('income','expense')})
        study=await group(StudySession,StudySession.date,{'minutes':func.sum(StudySession.duration_minutes)},StudySession.completed.is_(True))
        workouts=await group(WorkoutLog,WorkoutLog.date,{'n':func.count(),'minutes':func.sum(WorkoutLog.duration_minutes)},WorkoutLog.completed.is_(True))
        lower,upper=utc_bounds(first,last,user.timezone)
        day=func.timezone(user.timezone,QuestionAttempt.answered_at).cast(Date)
        # UTC range preserves the indexed timestamp filter; local expression is only for grouping.
        rows=(await session.execute(select(day,func.sum(QuestionAttempt.total),func.sum(QuestionAttempt.correct)).where(
            QuestionAttempt.user_id==uid,QuestionAttempt.answered_at>=lower,QuestionAttempt.answered_at<upper,
            func.coalesce(QuestionAttempt.evidence['answered'].as_boolean(),True)).group_by(day))).all()
        questions={d.isoformat():{'n':total,'correct':correct} for d,total,correct in rows}
        xp=await group(XPEntry,XPEntry.date,{'n':func.sum(XPEntry.amount)})
    data, accumulated = [], 0
    for day in dates:
        income, expenses = finance.get(day, {}).get('income', Decimal(0)), finance.get(day, {}).get('expense', Decimal(0))
        earned = xp.get(day, {}).get('n', 0)
        accumulated += earned
        data.append({'date': day, 'label': day[5:], 'tasks': tasks.get(day, {}).get('n', 0),
                     'habits': habits.get(day, 0), 'habits_total': habit_total,
                     'income': round(income, 2), 'expenses': round(expenses, 2), 'balance': round(income - expenses, 2),
                     'study_min': study.get(day, {}).get('minutes', 0), 'workouts': workouts.get(day, {}).get('n', 0),
                     'workout_min': workouts.get(day, {}).get('minutes', 0), 'questions': questions.get(day, {}).get('n', 0),
                     'correct': questions.get(day, {}).get('correct', 0), 'xp': earned, 'xp_cumulative': accumulated})
    total = lambda key: sum(d[key] for d in data)
    return {'days': days, 'data': data, 'totals': {
        'tasks': total('tasks'), 'habits_avg': round(total('habits') / days, 1),
        'income': round(total('income'), 2), 'expenses': round(total('expenses'), 2),
        'study_hours': round(total('study_min') / 60, 1), 'workouts': total('workouts'),
        'questions': total('questions'), 'xp_earned': total('xp')}}
