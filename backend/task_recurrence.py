"""One calendar rule for task lists, dashboard and calendar (São Paulo dates).

Monthly tasks anchored on 29/30/31 run on the last day of shorter months.
Legacy tasks without a scheduled date use their creation date; no migration guesses.
"""
from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def task_anchor(task):
    value = task.get('date') or task.get('start_date')
    if value:
        return date.fromisoformat(str(value)[:10])
    created = task.get('created_at')
    if not created:
        return None
    stamp = datetime.fromisoformat(created.replace('Z', '+00:00')) if isinstance(created, str) else created
    if stamp.tzinfo:
        stamp = stamp.astimezone(ZoneInfo('America/Sao_Paulo'))
    return stamp.date()


def expand_task_dates(task, start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first or (last - first).days > 366:
        raise ValueError('O intervalo deve ter no máximo 367 dias e início anterior ao fim.')
    anchor = task_anchor(task)
    if anchor is None or anchor > last:
        return []
    result = []
    current = max(first, anchor)
    recurrence = task.get('recurrence', 'once')
    while current <= last:
        applies = (recurrence == 'daily' or
                   recurrence == 'once' and current == anchor or
                   recurrence == 'weekly' and current.weekday() == anchor.weekday() or
                   recurrence == 'monthly' and current.day == min(anchor.day, monthrange(current.year, current.month)[1]))
        if applies:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


async def tasks_on_date(db, user_id, day, recurrence=None):
    query = {'user_id': user_id, 'is_template': True}
    if recurrence:
        query['recurrence'] = recurrence
    tasks = await db.tasks.find(query, {'_id': 0}).to_list(None)
    return [task for task in tasks if expand_task_dates(task, day, day)]


async def task_day_counts(db, user_id, day):
    tasks = await tasks_on_date(db, user_id, day)
    ids = [t['task_id'] for t in tasks]
    completed = await db.task_instances.distinct('task_id', {'user_id': user_id, 'date': day, 'completed': True, 'task_id': {'$in': ids}})
    return len(ids), len(completed)
