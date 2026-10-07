"""Calendar projection: owner/date predicates run in SQL before serialization."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from db.session import unit_of_work
from db.models.planning import Task, TaskInstance, Habit, HabitCheck, CalendarEvent
from db.models.health import WorkoutLog, Meal, MealItem
from db.models.studies import StudySession, Notebook, StudyPlan, StudyPlanEntry
from task_recurrence import expand_task_dates


async def calendar_events(user_id, start, end, timezone):
    events = []
    async with unit_of_work() as session:
        tasks = (await session.scalars(select(Task).where(Task.user_id == user_id,
            Task.archived_at.is_(None), Task.date <= end,
            (Task.recurrence != 'once') | (Task.date >= start)))).all()
        instances = (await session.scalars(select(TaskInstance).where(TaskInstance.user_id == user_id,
            TaskInstance.date.between(start,end)))).all()
        completed = {(row.task_id,row.date.isoformat()):row.completed for row in instances}
        for task in tasks:
            for day in expand_task_dates({'date':task.date.isoformat(),'recurrence':task.recurrence},start.isoformat(),end.isoformat()):
                events.append({'id':f'task_{task.id}_{day}','title':task.title,'date':day,'type':'task',
                    'color':'#007AFF','completed':completed.get((task.id,day),False),'priority':task.priority,'ref_id':str(task.id)})
        checks = (await session.execute(select(HabitCheck,Habit.name).join(Habit,
            (Habit.id == HabitCheck.habit_id) & (Habit.user_id == HabitCheck.user_id)).where(
            HabitCheck.user_id == user_id,HabitCheck.date.between(start,end),Habit.archived_at.is_(None)))).all()
        for row,name in checks:
            events.append({'id':f'habit_{row.habit_id}_{row.date}','title':name,'date':row.date.isoformat(),
                'type':'habit','color':'#39FF14','completed':True,'ref_id':str(row.habit_id)})
        studies = (await session.execute(select(StudySession,Notebook.name).outerjoin(Notebook,
            (Notebook.id == StudySession.notebook_id) & (Notebook.user_id == StudySession.user_id)).where(
            StudySession.user_id == user_id,StudySession.date.between(start,end)))).all()
        for row,name in studies:
            events.append({'id':f'study_{row.id}','title':f'Estudo: {name or "Sessão"}','date':row.date.isoformat(),
                'type':'study','color':'#A855F7','completed':row.completed,'duration_minutes':row.duration_minutes,'ref_id':str(row.id)})
        workouts = (await session.scalars(select(WorkoutLog).where(WorkoutLog.user_id == user_id,
            WorkoutLog.date.between(start,end)))).all()
        for row in workouts:
            events.append({'id':f'workout_{row.id}','title':f'Treino: {row.name}','date':row.date.isoformat(),
                'type':'workout','color':'#EF4444','completed':row.completed,'duration_minutes':row.duration_minutes,'ref_id':str(row.id)})
        meals = (await session.execute(select(Meal,func.coalesce(Meal.reported_calories,func.sum(MealItem.calories*MealItem.quantity),0)).outerjoin(MealItem,
            (MealItem.meal_id == Meal.id) & (MealItem.user_id == Meal.user_id)).where(Meal.user_id == user_id,
            Meal.date.between(start,end)).group_by(Meal.id))).all()
        for row,calories in meals:
            events.append({'id':f'meal_{row.id}','title':row.meal_type.capitalize(),'date':row.date.isoformat(),
                'type':'meal','color':'#22C55E','completed':True,'calories':calories,'ref_id':str(row.id)})
        entries = (await session.execute(select(StudyPlanEntry,StudyPlan.program_id).join(StudyPlan,
            (StudyPlan.id == StudyPlanEntry.plan_id) & (StudyPlan.user_id == StudyPlanEntry.user_id)).where(
            StudyPlanEntry.user_id == user_id,StudyPlanEntry.date.between(start,end)))).all()
        for row,program_id in entries:
            events.append({'id':str(row.id),'title':row.name+' · '+row.kind,'date':row.date.isoformat(),
                'type':'study','completed':row.completed,'duration_minutes':row.minutes,
                'link':f'/studies?program={program_id}&view=cronograma'})
        zone = ZoneInfo(timezone)
        first = datetime.combine(start,time(),tzinfo=zone)
        last = datetime.combine(end+timedelta(days=1),time(),tzinfo=zone)
        commitments = (await session.scalars(select(CalendarEvent).where(CalendarEvent.user_id == user_id,
            CalendarEvent.start_at >= first, CalendarEvent.start_at < last))).all()
        for row in commitments:
            local = row.start_at.astimezone(zone)
            events.append({'id':str(row.id),'date':local.date().isoformat(),'title':f'{local:%H:%M} · {row.title}',
                'type':'commitment','completed':False,'duration_minutes':int((row.end_at-row.start_at).total_seconds()/60),
                'link':'/assistant/settings'})
    return {'events':sorted(events,key=lambda e:(e['date'],e['id'])),'start':start.isoformat(),'end':end.isoformat()}
