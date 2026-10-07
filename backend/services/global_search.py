"""Bounded owner-scoped search; user text is a literal SQL substring."""
from uuid import UUID
from urllib.parse import urlencode
from sqlalchemy import select,or_,func,case
from fastapi import APIRouter,Request
from db.session import unit_of_work
from db.models.finance import FinancialTransaction
from db.models.planning import Task,TaskInstance,Habit,HabitCheck,Goal,CalendarEvent
from db.models.health import WorkoutPlan,WorkoutDay,PlanExercise
from db.models.studies import StudyNote,Notebook,StudyProgram,StudyTarget
from services.auth_routes import account
from services.time import local_today
from services.planning import streaks

router=APIRouter()


@router.get('/search/global')
async def search(request: Request,q: str=''):
    user=await account(request);needle=q.strip()[:100]
    if len(needle)<2:return {'results':[]}
    uid=UUID(user['user_id']);today=local_today(user['timezone']);results=[]
    def match(*columns):return or_(*(column.icontains(needle,autoescape=True) for column in columns))
    def add(kind,title,subtitle,link,icon=None):
        value={'type':kind,'title':title,'subtitle':subtitle,'link':link}
        if icon:value['icon']={'money':'💰','check':'✅','repeat':'🔄','dumbbell':'🏋️','note':'📝','target':'🎯'}[icon]
        results.append(value)
    async with unit_of_work() as session:
        transactions=(await session.scalars(select(FinancialTransaction).where(FinancialTransaction.user_id==uid,
            match(FinancialTransaction.description,FinancialTransaction.category)).order_by(FinancialTransaction.date.desc(),FinancialTransaction.id).limit(5))).all()
        for row in transactions:add('transaction',f'{row.description or ""} - R$ {row.amount:.2f}',f'{row.category} - {row.date}','/finance','money')
        task_day=case((Task.recurrence=='once',Task.date),else_=today)
        tasks=(await session.execute(select(Task,TaskInstance.completed).outerjoin(TaskInstance,(TaskInstance.user_id==Task.user_id)&(TaskInstance.task_id==Task.id)&(TaskInstance.date==task_day))
            .where(Task.user_id==uid,Task.archived_at.is_(None),match(Task.title)).order_by(Task.created_at.desc(),Task.id).limit(5))).all()
        for row,completed in tasks:add('task',row.title,'Concluída' if completed else 'Pendente','/tasks','check')
        habits=(await session.scalars(select(Habit).where(Habit.user_id==uid,Habit.archived_at.is_(None),match(Habit.name)).order_by(Habit.created_at.desc(),Habit.id).limit(5))).all()
        dates={}
        if habits:
            for identity,day in (await session.execute(select(HabitCheck.habit_id,HabitCheck.date).where(HabitCheck.user_id==uid,HabitCheck.habit_id.in_([h.id for h in habits]),HabitCheck.date<=today))).all():
                dates.setdefault(identity,[]).append(day)
        for row in habits:add('habit',row.name,f'Streak: {streaks(dates.get(row.id,[]),today)[0]} dias','/habits','repeat')
        exercise_count=select(func.count()).select_from(PlanExercise).join(WorkoutDay,(WorkoutDay.id==PlanExercise.day_id)&(WorkoutDay.user_id==PlanExercise.user_id)).where(
            WorkoutDay.user_id==uid,WorkoutDay.plan_id==WorkoutPlan.id).correlate(WorkoutPlan).scalar_subquery()
        plans=(await session.execute(select(WorkoutPlan,exercise_count).where(WorkoutPlan.user_id==uid,WorkoutPlan.archived_at.is_(None),
            match(WorkoutPlan.name,WorkoutPlan.description)).order_by(WorkoutPlan.created_at.desc(),WorkoutPlan.id).limit(5))).all()
        for row,count in plans:add('workout_plan',row.name,f'{count} exercícios','/workouts','dumbbell')
        notes=(await session.scalars(select(StudyNote).join(Notebook,(Notebook.id==StudyNote.notebook_id)&(Notebook.user_id==StudyNote.user_id)).where(
            StudyNote.user_id==uid,Notebook.archived_at.is_(None),match(StudyNote.title,StudyNote.content)).order_by(StudyNote.created_at.desc(),StudyNote.id).limit(5))).all()
        for row in notes:add('note',row.title,'Nota de estudo','/studies','note')
        goals=(await session.scalars(select(Goal).where(Goal.user_id==uid,Goal.archived_at.is_(None),match(Goal.title)).order_by(Goal.created_at.desc(),Goal.id).limit(5))).all()
        for row in goals:add('goal',row.title,f'Progresso: {row.progress}%','/goals','target')
        programs=(await session.scalars(select(StudyProgram).where(StudyProgram.user_id==uid,StudyProgram.archived_at.is_(None),
            match(StudyProgram.name,StudyProgram.description)).order_by(StudyProgram.created_at.desc(),StudyProgram.id).limit(5))).all()
        for row in programs:add('study_programs',row.name,'Programa de estudos','/studies?'+urlencode({'program':str(row.id)}))
        targets=(await session.execute(select(StudyTarget,StudyProgram.name).join(StudyProgram,(StudyProgram.id==StudyTarget.program_id)&(StudyProgram.user_id==StudyTarget.user_id)).where(
            StudyTarget.user_id==uid,StudyProgram.archived_at.is_(None),match(StudyTarget.name,StudyTarget.institution,StudyTarget.board,StudyTarget.position))
            .order_by(StudyTarget.created_at.desc(),StudyTarget.id).limit(5))).all()
        for row,name in targets:add('study_targets',row.name or name,'Preparação','/studies?'+urlencode({'program':str(row.program_id)}))
        books=(await session.scalars(select(Notebook).where(Notebook.user_id==uid,Notebook.archived_at.is_(None),match(Notebook.name,Notebook.description))
            .order_by(Notebook.created_at.desc(),Notebook.id).limit(5))).all()
        for row in books:
            params={'notebook':str(row.id),'view':'estudar'}
            if row.program_id:params['program']=str(row.program_id)
            add('notebooks',row.name,'Matéria','/studies?'+urlencode(params))
        events=(await session.scalars(select(CalendarEvent).where(CalendarEvent.user_id==uid,match(CalendarEvent.title)).order_by(CalendarEvent.start_at.desc(),CalendarEvent.id).limit(5))).all()
        for row in events:add('calendar_commitments',row.title,'Compromisso','/calendar')
    return {'results':results}
