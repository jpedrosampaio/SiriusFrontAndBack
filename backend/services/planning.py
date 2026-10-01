from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from db.activity import run_activity
from db.models.planning import TaskInstance, HabitCheck
from db.repositories.planning import PlanningRepository
from services.time import local_today


def rank_for_xp(xp):
    ranks = [(0,'Recruta'),(200,'Soldado'),(500,'Cabo'),(1000,'Sargento'),(1800,'Subtenente'),
        (3000,'Tenente'),(4500,'Capitão'),(6500,'Major'),(9000,'Tenente-Coronel'),(12000,'Coronel'),
        (16000,'General de Brigada'),(21000,'General de Divisão'),(27000,'General de Exército'),(35000,'Marechal')]
    return next(name for threshold,name in reversed(ranks) if xp >= threshold)


def apply_xp(user, delta):
    user.xp = max(0, user.xp + delta)
    user.rank = rank_for_xp(user.xp)
    return user.xp, user.rank


def streaks(dates, today):
    dates = sorted(set(dates))
    best = length = 0
    previous = None
    for day in dates:
        length = length+1 if previous is not None and day-previous == timedelta(days=1) else 1
        best = max(best, length)
        previous = day
    valid = set(day for day in dates if day <= today)
    cursor = today if today in valid else today-timedelta(days=1)
    current = 0
    while cursor in valid:
        current += 1
        cursor -= timedelta(days=1)
    return current,best


async def set_task_completion(user_id, task_id, day, status, request_key=None):
    if status not in ('todo','in_progress','done'):
        raise HTTPException(400, 'Status must be todo, in_progress, or done')
    async def apply(session, user):
        repo = PlanningRepository(session)
        task = await repo.get_task(user.id, task_id)
        if task is None:
            raise HTTPException(404, 'Task not found')
        instance = await repo.task_instance(user.id, task_id, day)
        was_completed = bool(instance and instance.completed)
        completed = status == 'done'
        if instance is None:
            instance = TaskInstance(user_id=user.id, task_id=task_id, date=day)
            session.add(instance)
        instance.status, instance.completed = status, completed
        instance.completed_at = datetime.now(timezone.utc) if completed else None
        xp_earned = (int(completed)-int(was_completed))*task.xp_reward
        apply_xp(user, xp_earned)
        await session.flush()
        return {'message':'Task completed' if xp_earned > 0 else 'Task uncompleted' if xp_earned < 0 else 'Task updated',
            'task_id':str(task_id), 'date':day.isoformat(), 'completed':completed, 'status':status,
            'xp_earned':xp_earned, 'new_xp':user.xp, 'new_rank':user.rank, 'instance_id':str(instance.id)}
    return await run_activity(user_id, request_key, ['task',str(task_id),day.isoformat(),status], apply)


async def set_habit_completion(user_id, habit_id, day, completed, request_key=None):
    if completed is None and request_key is None:
        raise HTTPException(428, 'Send completed=true/false or an Idempotency-Key')
    async def apply(session, user):
        repo = PlanningRepository(session)
        habit = await repo.get_habit(user.id, habit_id)
        if habit is None:
            raise HTTPException(404, 'Habit not found')
        row = await repo.habit_check(user.id, habit_id, day)
        was_completed = row is not None
        target = not was_completed if completed is None else completed
        if target and row is None:
            session.add(HabitCheck(user_id=user.id, habit_id=habit_id, date=day, checked_at=datetime.now(timezone.utc)))
        elif not target and row is not None:
            await session.delete(row)
        await session.flush()
        current,best = streaks(await repo.habit_dates(user.id,habit_id),local_today(user.timezone))
        xp_earned = (int(target)-int(was_completed))*8
        apply_xp(user,xp_earned)
        return {'message':'Habit completed' if target else 'Habit uncompleted','completed':target,'uncompleted':not target,
            'streak':current,'best_streak':best,'xp_earned':xp_earned,'new_xp':user.xp,'new_rank':user.rank}
    return await run_activity(user_id, request_key, ['habit',str(habit_id),day.isoformat(),completed], apply)
