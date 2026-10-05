"""SQL period metrics; no raw documents reach AI."""
from datetime import date,datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
from uuid import UUID
from sqlalchemy import select,func
from db.models.identity import User
from db.models.planning import Task,TaskInstance,Habit,HabitCheck,Goal,GoalCheck
from db.models.finance import FinancialTransaction
from db.models.studies import StudySession,QuestionAttempt
from db.models.health import WorkoutLog
from db.session import unit_of_work
from services.nutrition import period


def report_window(kind, today, start=None, end=None):
    day = date.fromisoformat(today)
    if kind in ('diário', 'daily'):
        first = last = day
    elif kind in ('semanal', 'weekly'):
        first, last = day - timedelta(days=day.weekday()), day
    elif kind in ('mensal', 'monthly'):
        first, last = day.replace(day=1), day
    elif kind == 'sprint':
        if not start or not end:
            raise ValueError('Informe início e fim do sprint.')
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    else:
        raise ValueError('Tipo de relatório inválido.')
    if first > last or last > day or (last - first).days > 366:
        raise ValueError('Intervalo inválido: use até 367 dias, sem datas futuras.')
    return first.isoformat(), last.isoformat()



def utc_bounds(start,end,zone):
    return (datetime.combine(start,time(),tzinfo=ZoneInfo(zone)).astimezone(timezone.utc),
        datetime.combine(end+timedelta(days=1),time(),tzinfo=ZoneInfo(zone)).astimezone(timezone.utc))


async def period_metrics(user_id,start,end):
    uid=UUID(str(user_id));first=date.fromisoformat(start) if isinstance(start,str) else start;last=date.fromisoformat(end) if isinstance(end,str) else end
    async with unit_of_work() as session:
        user=await session.get(User,uid)
        lower,upper=utc_bounds(first,last,user.timezone)
        async def count(model,*filters):
            return await session.scalar(select(func.count()).select_from(model).where(model.user_id==uid,*filters))
        tasks=await count(Task,Task.created_at>=lower,Task.created_at<upper)
        habits=await count(Habit,Habit.created_at>=lower,Habit.created_at<upper)
        done=await count(TaskInstance,TaskInstance.date.between(first,last),TaskInstance.completed.is_(True))
        checks=await count(HabitCheck,HabitCheck.date.between(first,last))
        goal_checks=await count(GoalCheck,GoalCheck.date.between(first,last))
        goals,progress=(await session.execute(select(func.count(),func.coalesce(func.avg(Goal.progress),0)).where(
            Goal.user_id==uid,Goal.created_at>=lower,Goal.created_at<upper))).one()
        money=dict((await session.execute(select(FinancialTransaction.type,func.sum(FinancialTransaction.amount)).where(
            FinancialTransaction.user_id==uid,FinancialTransaction.date.between(first,last)).group_by(FinancialTransaction.type))).all())
        minutes=await session.scalar(select(func.coalesce(func.sum(StudySession.duration_minutes),0)).where(
            StudySession.user_id==uid,StudySession.date.between(first,last),StudySession.completed.is_(True)))
        total,correct=(await session.execute(select(func.coalesce(func.sum(QuestionAttempt.total),0),func.coalesce(func.sum(QuestionAttempt.correct),0)).where(
            QuestionAttempt.user_id==uid,QuestionAttempt.answered_at>=lower,QuestionAttempt.answered_at<upper,
            func.coalesce(QuestionAttempt.evidence['answered'].as_boolean(),True)))).one()
        workouts,duration=(await session.execute(select(func.count(),func.coalesce(func.sum(WorkoutLog.duration_minutes),0)).where(
            WorkoutLog.user_id==uid,WorkoutLog.date.between(first,last),WorkoutLog.completed.is_(True)))).one()
        meals,water,_=await period(session,uid,first,last)
        return {'start_date':first.isoformat(),'end_date':last.isoformat(),'tasks':tasks,'tasks_completed':done,'habits':habits,
            'total_habits_completions':checks,'income':money.get('income',0),'expenses':money.get('expense',0),'goals':goals,'goals_progress':progress,
            'goal_checks':goal_checks,'study_minutes':minutes,'questions_answered':total,'questions_correct':correct,
            'workouts':workouts,'workout_minutes':duration,'meals':sum(day['meals_count'] for day in meals.values()),
            'calories':sum(day['calories'] for day in meals.values()),'protein':sum(day['protein'] for day in meals.values()),'water_ml':sum(water.values()),
            'definitions':'tasks/habits/goals: cadastros criados no intervalo; goals_progress: progresso atual dessas metas, não histórico; demais métricas: atividades no intervalo.'}
