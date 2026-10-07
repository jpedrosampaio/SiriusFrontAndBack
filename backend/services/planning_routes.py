"""Planning HTTP contracts backed by SQL transactions and owner-scoped repositories."""
from datetime import datetime, timezone, timedelta
from services.time import CalendarDate as Date
from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field, field_validator
from ai.registry import TaskArgs
from db.activity import run_activity
from db.session import unit_of_work
from db.repositories.planning import PlanningRepository
from services.auth_routes import account
from services.core_writes import CoreWrites
from services.planning import set_task_completion, set_habit_completion, streaks
from services.time import local_today

router = APIRouter()


@router.get('/calendar/events')
async def get_calendar_events(request: Request, start: Date | None = None, end: Date | None = None):
    from services.calendar import calendar_events
    user = await account(request)
    today = local_today(user['timezone'])
    start = start or today.replace(day=1)
    end = end or (today.replace(day=28)+timedelta(days=4)).replace(day=1)
    if end < start or (end-start).days > 366:
        raise HTTPException(422,'O intervalo deve ter no máximo 367 dias e início anterior ao fim.')
    return await calendar_events(UUID(user['user_id']),start,end,user['timezone'])


class HabitBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    color: str = Field(default='#007AFF', pattern=r'^#[0-9a-fA-F]{6}$')


class TaskBody(TaskArgs):
    @field_validator('description', mode='before')
    @classmethod
    def optional_description(cls, value):
        return '' if value is None else value


class StatusBody(BaseModel):
    status: str = 'todo'
    date: Date | None = None


def habit_json(row, dates, today):
    current, best = streaks(dates, today)
    return {'habit_id': str(row.id), 'user_id': str(row.user_id), 'name': row.name,
        'description': row.description, 'color': row.color, 'streak': current, 'best_streak': best,
        'completions': [day.isoformat() for day in dates], 'created_at': row.created_at.isoformat()}


@router.get('/tasks')
async def get_tasks(request: Request, date: Date | None = None, recurrence: str | None = None):
    user = await account(request)
    day = date or local_today(user['timezone'])
    async with unit_of_work() as session:
        pairs = await PlanningRepository(session).tasks_on_date(UUID(user['user_id']), day, recurrence)
        return [{'task_id': str(task.id), 'user_id': str(task.user_id), 'title': task.title,
            'description': task.description, 'date': day.isoformat(), 'priority': task.priority,
            'recurrence': task.recurrence, 'xp_reward': task.xp_reward, 'is_template': True,
            'created_at': task.created_at.isoformat(), 'completed': bool(instance and instance.completed),
            'status': instance.status if instance else 'todo', 'instance_id': str(instance.id) if instance else None}
            for task, instance in pairs]


@router.post('/tasks')
async def create_task(request: Request, body: TaskBody):
    user = await account(request)
    args = body.model_dump(mode='json')
    async def apply(session, owner):
        return await CoreWrites().execute('create_task', owner, args, session)
    return await run_activity(UUID(user['user_id']), request.headers.get('Idempotency-Key'), ['create_task', args], apply)


@router.patch('/tasks/{task_id}')
async def update_task(request: Request, task_id: UUID, completed: bool, date: Date):
    user = await account(request)
    return await set_task_completion(UUID(user['user_id']), task_id, date, 'done' if completed else 'todo',
        request.headers.get('Idempotency-Key'))


@router.patch('/tasks/{task_id}/status')
async def update_task_status(request: Request, task_id: UUID, body: StatusBody):
    user = await account(request)
    return await set_task_completion(UUID(user['user_id']), task_id, body.date or local_today(user['timezone']),
        body.status, request.headers.get('Idempotency-Key'))


async def archive(request, identity, kind):
    user = await account(request)
    async def apply(session, owner):
        repo = PlanningRepository(session)
        row = await (repo.get_task(owner.id, identity) if kind == 'Task' else repo.get_habit(owner.id, identity))
        if row is None:
            raise HTTPException(404, f'{kind} not found')
        row.archived_at = datetime.now(timezone.utc)
        return {'message': f'{kind} deleted'}
    return await run_activity(UUID(user['user_id']), request.headers.get('Idempotency-Key'),
        ['archive', kind, str(identity)], apply)


@router.delete('/tasks/{task_id}')
async def delete_task(request: Request, task_id: UUID):
    return await archive(request, task_id, 'Task')


@router.get('/habits')
async def get_habits(request: Request):
    user = await account(request)
    async with unit_of_work() as session:
        pairs = await PlanningRepository(session).habits_with_dates(UUID(user['user_id']))
        return [habit_json(row, dates, local_today(user['timezone'])) for row, dates in pairs]


@router.post('/habits')
async def create_habit(request: Request, body: HabitBody):
    user = await account(request)
    async def apply(session, owner):
        row = await PlanningRepository(session).create_habit(owner.id, **body.model_dump())
        return habit_json(row, [], local_today(owner.timezone))
    return await run_activity(UUID(user['user_id']), request.headers.get('Idempotency-Key'),
        ['create_habit', body.model_dump()], apply)


@router.post('/habits/{habit_id}/complete')
async def complete_habit(request: Request, habit_id: UUID, date: Date, completed: bool | None = None):
    user = await account(request)
    return await set_habit_completion(UUID(user['user_id']), habit_id, date, completed,
        request.headers.get('Idempotency-Key'))


@router.delete('/habits/{habit_id}')
async def delete_habit(request: Request, habit_id: UUID):
    return await archive(request, habit_id, 'Habit')
