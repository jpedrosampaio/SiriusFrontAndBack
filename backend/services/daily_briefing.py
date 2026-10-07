"""Four-hour SQL briefing cache; AI executes outside write transactions."""
import json
import logging
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from uuid import UUID
from fastapi import APIRouter,Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field,ValidationError
from sqlalchemy import select,func
from db.models.reports import DailySummary
from db.models.studies import StudySession
from db.models.health import WorkoutLog
from db.repositories.planning import PlanningRepository
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.nutrition import period
from services.time import local_today
from ai.daily_progress import progress_score

router=APIRouter()
call_llm=None
RAW=('tasks_pending','tasks_done','habits_pending','habits_done','study_minutes','meals_count','calories','workouts_count')

class SummaryBody(BaseModel):
    greeting: str=Field(max_length=5000)
    progress_summary: str=Field(max_length=10000)
    pending_items: list[str]=Field(max_length=100)
    motivation: str=Field(max_length=5000)
    priority_action: str=Field(max_length=5000)
    score: int=Field(default=0,ge=0,le=100)


def configure(llm):
    global call_llm
    call_llm=llm


def public(row):
    return jsonable_encoder({'user_id':row.user_id,'date':row.date,'summary':{key:getattr(row,key) for key in SummaryBody.model_fields},
        'raw_data':{key:getattr(row,key) for key in RAW},'created_at':row.updated_at})


def fresh(row):return row is not None and row.updated_at>=datetime.now(timezone.utc)-timedelta(hours=4)


async def cached_summary(uid,day):
    async with unit_of_work() as session:
        row=await session.scalar(select(DailySummary).where(DailySummary.user_id==UUID(uid),DailySummary.date==day))
        return public(row) if fresh(row) else None


async def summary_context(uid,day):
    uid=UUID(uid)
    async with unit_of_work() as session:
        repo=PlanningRepository(session);pairs=await repo.tasks_on_date(uid,day)
        pending=[{'title':task.title} for task,instance in pairs if not instance or not instance.completed]
        done=[{'title':task.title} for task,instance in pairs if instance and instance.completed]
        habit_pairs=await repo.habits_with_dates(uid)
        habit_done=[{'name':habit.name} for habit,dates in habit_pairs if day in dates]
        habit_pending=[{'name':habit.name} for habit,dates in habit_pairs if day not in dates]
        study_count,minutes=(await session.execute(select(func.count(),func.coalesce(func.sum(StudySession.duration_minutes),0)).where(
            StudySession.user_id==uid,StudySession.date==day,StudySession.completed.is_(True)))).one()
        meals,_,_=await period(session,uid,day,day);values=meals.get(day,{})
        workout_count=await session.scalar(select(func.count()).select_from(WorkoutLog).where(WorkoutLog.user_id==uid,WorkoutLog.date==day,WorkoutLog.completed.is_(True)))
        return pending,done,habit_pending,habit_done,minutes,study_count,values.get('meals_count',0),values.get('calories',0),workout_count


async def save_summary(uid,day,result):
    async def apply(session,owner):
        row=await session.scalar(select(DailySummary).where(DailySummary.user_id==owner.id,DailySummary.date==day))
        if fresh(row):return public(row)
        values={**result['summary'],**result['raw_data']}
        if row is None:row=DailySummary(user_id=owner.id,date=day,**values);session.add(row)
        else:
            for key,value in values.items():setattr(row,key,value)
            row.updated_at=datetime.now(timezone.utc)
        await session.flush();await session.refresh(row);return public(row)
    return await run_activity(UUID(uid),None,['daily-summary',day.isoformat()],apply)


@router.get('/dashboard/daily-summary')
async def get_daily_summary(request: Request):
    """Generate AI-powered daily briefing"""
    profile=await account(request);user=SimpleNamespace(**profile)
    day=local_today(user.timezone);today_str=day.isoformat()
    cached=await cached_summary(user.user_id,day)
    if cached:
        async with unit_of_work() as session:
            repo=PlanningRepository(session)
            tasks=await repo.tasks_on_date(UUID(user.user_id),day)
            habits=await repo.habits_with_dates(UUID(user.user_id))
            done=sum(bool(instance and instance.completed) for _,instance in tasks)
            checked=sum(day in dates for _,dates in habits)
        cached['raw_data'].update(tasks_done=done,tasks_pending=len(tasks)-done,
            habits_done=checked,habits_pending=len(habits)-checked)
        cached['summary']['score']=progress_score(cached['raw_data'])
        return cached
    pending_tasks,done_tasks,habits_pending,habits_done,study_minutes,study_count,meal_count,total_calories,workout_count=await summary_context(user.user_id,day)
    raw = {'tasks_pending':len(pending_tasks),'tasks_done':len(done_tasks),'habits_pending':len(habits_pending),'habits_done':len(habits_done),'study_minutes':study_minutes,'meals_count':meal_count,'calories':round(total_calories),'workouts_count':workout_count}
    context = f"Dados do dia ({today_str}) do usuário {user.name}:\n- Rank: {user.rank} | XP: {user.xp}\n- Tarefas pendentes: {len(pending_tasks)} ({', '.join((t['title'] for t in pending_tasks[:5]))})\n- Tarefas concluídas: {len(done_tasks)}\n- Hábitos pendentes: {len(habits_pending)} ({', '.join((h['name'] for h in habits_pending[:5]))})\n- Hábitos concluídos: {len(habits_done)}\n- Estudo: {study_minutes} minutos em {study_count} sessões\n- Refeições: {meal_count} registradas, {total_calories:.0f} kcal total\n- Treinos: {workout_count} realizados"
    prompt = f'{context}\n\nGere um resumo diário motivacional e prático em PORTUGUÊS. Responda em JSON com greeting, progress_summary, pending_items (lista), motivation e priority_action. Não calcule score; o progresso é calculado pelo sistema.'
    summary_data = None
    try:
        resp_text = await call_llm(prompt + '\n\nResponda APENAS com JSON puro, sem markdown, sem texto extra.', f'daily_summary_{user.user_id}', 'Você é um assistente motivacional que gera resumos diários em JSON.', user_id=user.user_id, task='assistant_chat')
        if resp_text and (not resp_text.startswith('⚠')):
            first_brace = resp_text.find('{')
            if first_brace >= 0:
                resp_text = resp_text[first_brace:]
                last_brace = resp_text.rfind('}')
                if last_brace >= 0:
                    resp_text = resp_text[:last_brace + 1]
                parsed=json.loads(resp_text)
                parsed['score']=progress_score(raw)
                summary_data = SummaryBody.model_validate(parsed).model_dump()
    except Exception as e:
        logging.error(f'Daily summary AI error: {e}')
    if not summary_data:
        total_items = len(pending_tasks) + len(habits_pending) + len(done_tasks) + len(habits_done)
        done_items = len(done_tasks) + len(habits_done)
        score = round(done_items / max(total_items, 1) * 100)
        summary_data = {'greeting': f'Bom dia, {user.name}! Seu rank atual é {user.rank}.', 'progress_summary': f"Você já concluiu {len(done_tasks)} tarefas e {len(habits_done)} hábitos hoje. {('Estudou ' + str(study_minutes) + ' min. ' if study_minutes else '')}{('Treinou! ' if workout_count else '')}{('Registrou ' + str(meal_count) + ' refeições.' if meal_count else '')}", 'pending_items': [t['title'] for t in pending_tasks[:5]] + [h['name'] for h in habits_pending[:5]], 'motivation': 'Disciplina é o que te move quando a motivação falta. Continue!', 'priority_action': pending_tasks[0]['title'] if pending_tasks else habits_pending[0]['name'] if habits_pending else 'Dia limpo! Descanse ou avance no extra.', 'score': score}
    summary_data['score']=progress_score(raw)
    result = {'user_id': user.user_id, 'date': today_str, 'summary': summary_data, 'raw_data': {'tasks_pending': len(pending_tasks), 'tasks_done': len(done_tasks), 'habits_pending': len(habits_pending), 'habits_done': len(habits_done), 'study_minutes': study_minutes, 'meals_count': meal_count, 'calories': round(total_calories), 'workouts_count': workout_count}, 'created_at': datetime.now(timezone.utc).isoformat()}
    return await save_summary(user.user_id,day,result)

