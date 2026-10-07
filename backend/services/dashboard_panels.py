"""SQL weekly summaries, activity streaks and deterministic reminders."""
from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.planning import Task,TaskInstance,Habit,HabitCheck
from db.models.finance import FinancialTransaction,Budget
from db.models.studies import StudySession
from db.models.health import WorkoutLog,WorkoutSession,Meal
from db.repositories.planning import PlanningRepository
from services.auth_routes import account
from services.time import local_today
from services.planning import streaks
from task_recurrence import expand_task_dates
from report_metrics import utc_bounds

router=APIRouter()


async def task_period_counts(session,uid,start,end):
    tasks=(await session.scalars(select(Task).where(Task.user_id==uid,Task.archived_at.is_(None),Task.date<=end,
        (Task.recurrence!='once')|(Task.date>=start)))).all()
    done=set((identity,day.isoformat()) for identity,day in (await session.execute(select(TaskInstance.task_id,TaskInstance.date).where(
        TaskInstance.user_id==uid,TaskInstance.completed.is_(True),TaskInstance.date.between(start,end)))).all())
    applicable={(task.id,day) for task in tasks for day in expand_task_dates({'date':task.date.isoformat(),'recurrence':task.recurrence},start.isoformat(),end.isoformat())}
    return len(applicable),len(applicable&done)


@router.get('/dashboard/weekly-summary')
async def weekly(request: Request):
    user=await account(request);uid=UUID(user['user_id']);today=local_today(user['timezone']);start=today-timedelta(days=today.weekday())
    async with unit_of_work() as session:
        money=(await session.execute(select(FinancialTransaction.type,func.sum(FinancialTransaction.amount),func.count()).where(
            FinancialTransaction.user_id==uid,FinancialTransaction.date.between(start,today)).group_by(FinancialTransaction.type))).all()
        sums={kind:amount for kind,amount,count in money};income=sums.get('income',0);expense=sums.get('expense',0)
        count,minutes,calories=(await session.execute(select(func.count(),func.coalesce(func.sum(WorkoutLog.duration_minutes),0),func.coalesce(func.sum(WorkoutLog.calories),0)).where(
            WorkoutLog.user_id==uid,WorkoutLog.completed.is_(True),WorkoutLog.date.between(start,today)))).one()
        lower,upper=utc_bounds(start,today,user['timezone'])
        sessions,difficulty=(await session.execute(select(func.count(),func.avg(WorkoutSession.feedback['difficulty'].as_float())).where(
            WorkoutSession.user_id==uid,WorkoutSession.status=='completed',WorkoutSession.completed_at>=lower,WorkoutSession.completed_at<upper))).one()
        habits=(await session.execute(select(Habit.id,Habit.created_at).where(Habit.user_id==uid,Habit.archived_at.is_(None)))).all()
        checks=await session.scalar(select(func.count()).select_from(HabitCheck).join(Habit,(Habit.id==HabitCheck.habit_id)&(Habit.user_id==HabitCheck.user_id)).where(
            HabitCheck.user_id==uid,Habit.archived_at.is_(None),HabitCheck.date.between(start,today)))
        possible=sum(max(0,(today-max(start,created.astimezone(ZoneInfo(user['timezone'])).date())).days+1) for identity,created in habits)
        tasks,done=await task_period_counts(session,uid,start,today)
        studied,duration=(await session.execute(select(func.count(),func.coalesce(func.sum(StudySession.duration_minutes),0)).where(
            StudySession.user_id==uid,StudySession.completed.is_(True),StudySession.date.between(start,today)))).one()
    return jsonable_encoder({'period':{'start':start.isoformat(),'end':today.isoformat()},
        'finance':{'income':income,'expense':expense,'balance':income-expense,'transactions_count':sum(count for kind,amount,count in money)},
        'workouts':{'count':count,'total_minutes':minutes,'total_calories':calories,'sessions_completed':sessions,'avg_difficulty':round(difficulty or 0,1)},
        'habits':{'completed':checks,'total_possible':possible,'completion_pct':round(checks/max(possible,1)*100),'active_habits':len(habits)},
        'tasks':{'completed':done,'total':tasks,'completion_pct':round(done/max(tasks,1)*100)},
        'study':{'sessions':studied,'total_minutes':duration},'xp':user['xp'],'rank':user['rank']})


@router.get('/streaks/global')
async def global_streaks(request: Request):
    user=await account(request);uid=UUID(user['user_id']);today=local_today(user['timezone']);start=today-timedelta(days=120)
    module_days={}
    async with unit_of_work() as session:
        for name,model,filters in [('tasks',TaskInstance,[TaskInstance.completed.is_(True)]),('habits',HabitCheck,[]),
            ('study',StudySession,[StudySession.completed.is_(True)]),('workouts',WorkoutLog,[WorkoutLog.completed.is_(True)]),('nutrition',Meal,[])]:
            module_days[name]=set((await session.scalars(select(model.date).distinct().where(model.user_id==uid,model.date.between(start,today),*filters))).all())
    active=set().union(*module_days.values());current,best=streaks(active,today)
    today_modules=[name for name,days in module_days.items() if today in days];combo=len(today_modules)
    heatmap=[]
    for offset in range(6,-1,-1):
        day=today-timedelta(days=offset);names=[name for name,days in module_days.items() if day in days]
        heatmap.append({'date':day.isoformat(),'active':day in active,'modules':names,'count':len(names)})
    return {'current_streak':current,'longest_streak':best,'total_active_days':len(active),'today_modules':today_modules,'combo_count':combo,
        'combo_bonus_xp':combo*5 if combo>=3 else combo*3 if combo>=2 else 0,'heatmap':heatmap,
        'module_streaks':{name:streaks(days,today)[0] for name,days in module_days.items()}}


async def reminder_context(uid,today):
    uid=UUID(uid);month=today.replace(day=1);next_month=(month.replace(day=28)+timedelta(days=4)).replace(day=1)
    async with unit_of_work() as session:
        workouts=await session.scalar(select(func.count()).select_from(WorkoutLog).where(WorkoutLog.user_id==uid,WorkoutLog.completed.is_(True),
            WorkoutLog.date.between(today-timedelta(days=6),today)))
        budgets=[{'category':row.category,'limit':row.limit} for row in (await session.scalars(select(Budget).where(Budget.user_id==uid,Budget.month==month))).all()]
        expenses=dict((await session.execute(select(FinancialTransaction.category,func.sum(FinancialTransaction.amount)).where(FinancialTransaction.user_id==uid,
            FinancialTransaction.type=='expense',FinancialTransaction.date>=month,FinancialTransaction.date<next_month).group_by(FinancialTransaction.category))).all())
        habits=[{'name':habit.name,'completions':[d.isoformat() for d in dates],'streak':streaks(dates,today)[0]} for habit,dates in await PlanningRepository(session).habits_with_dates(uid)]
        done=select(TaskInstance.task_id).where(TaskInstance.user_id==uid,TaskInstance.task_id==Task.id,TaskInstance.date==Task.date,TaskInstance.completed.is_(True)).exists()
        overdue=await session.scalar(select(func.count()).select_from(Task).where(Task.user_id==uid,Task.archived_at.is_(None),Task.recurrence=='once',Task.date<today,~done))
        return workouts,budgets,expenses,habits,overdue


@router.get('/reminders/smart')
async def get_smart_reminders(request: Request):
    """Generate smart reminders based on user patterns"""
    user=await account(request)
    today_dt=local_today(user['timezone']);today=today_dt.isoformat()
    workout_count,budgets,expense_by_cat,habits,overdue_count=await reminder_context(user['user_id'],today_dt)
    reminders=[]
    if workout_count == 0:
        reminders.append({'type': 'workout', 'icon': '🏋️', 'message': 'Você não treinou nos últimos 7 dias! Que tal retomar hoje?', 'priority': 'high', 'action_link': '/workouts'})
    elif workout_count < 3:
        reminders.append({'type': 'workout', 'icon': '💪', 'message': f'Apenas {workout_count} treino(s) esta semana. Tente manter ao menos 3x/semana!', 'priority': 'medium', 'action_link': '/workouts'})
    for b in budgets:
        cat = b.get('category', '')
        limit_val = b.get('limit', 0)
        spent = expense_by_cat.get(cat, 0)
        if limit_val > 0 and spent > 0:
            pct = spent / limit_val * 100
            if pct >= 90:
                reminders.append({'type': 'finance', 'icon': '⚠️', 'message': f'Orçamento de {cat}: {pct:.0f}% usado (R$ {spent:.2f} de R$ {limit_val:.2f})', 'priority': 'high', 'action_link': '/finance'})
            elif pct >= 70:
                reminders.append({'type': 'finance', 'icon': '📊', 'message': f'Orçamento de {cat}: {pct:.0f}% usado. Fique atento!', 'priority': 'medium', 'action_link': '/finance'})
    for h in habits:
        completions = h.get('completions', [])
        if h.get('streak', 0) >= 3 and today not in completions:
            yesterday = (today_dt - timedelta(days=1)).strftime('%Y-%m-%d')
            if yesterday in completions:
                reminders.append({'type': 'habit', 'icon': '🔥', 'message': f"'{h.get('name', '')}': streak de {h.get('streak', 0)} dias em risco! Complete hoje.", 'priority': 'high', 'action_link': '/habits'})
    if overdue_count:
        reminders.append({'type': 'task', 'icon': '📋', 'message': f'Você tem {overdue_count} tarefa(s) atrasada(s)!', 'priority': 'high', 'action_link': '/tasks'})
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    reminders.sort(key=lambda r: priority_order.get(r.get('priority', 'low'), 2))
    return {'reminders': reminders}


@router.get('/dashboard/panels')
async def panels(request: Request):
    import asyncio
    from services.daily_briefing import get_daily_summary
    from services.workout_plan_routes import today_schedule
    await account(request)
    names=['weekly','reminders','streaks','daily','workout']
    results=await asyncio.gather(*(handler(request) for handler in [weekly,get_smart_reminders,global_streaks,get_daily_summary,today_schedule]),return_exceptions=True)
    return {'panels':{name:value for name,value in zip(names,results) if not isinstance(value,Exception)},
        'errors':[name for name,value in zip(names,results) if isinstance(value,Exception)]}
