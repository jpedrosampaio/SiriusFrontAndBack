"""Preserve analytics response contract while grouping histories in MongoDB."""
import asyncio
from datetime import datetime, timedelta, timezone


async def analytics_snapshot(db, user_id, days=7, today=None):
    days = max(1, min(90, days))
    today = today or datetime.now(timezone.utc).date().isoformat()
    dates = [(datetime.fromisoformat(today) - timedelta(days=i)).date().isoformat() for i in range(days - 1, -1, -1)]
    own = {'user_id': user_id}
    bounds = {'$gte': dates[0], '$lte': dates[-1]}
    async def group(collection, fields, extra=None):
        rows = await collection.aggregate([{'$match': {**own, 'date': bounds, **(extra or {})}},
                                           {'$group': {'_id': '$date', **fields}}]).to_list(days)
        return {r['_id']: r for r in rows}
    async def habits_by_day():
        rows = await db.habits.aggregate([
            {'$match': own}, {'$project': {'dates': {'$setUnion': [{'$ifNull': ['$completions', []]}, []]}}},
            {'$unwind': '$dates'}, {'$match': {'dates': bounds}},
            {'$group': {'_id': '$dates', 'n': {'$sum': 1}}},
        ]).to_list(days)
        return {r['_id']: r['n'] for r in rows}
    tasks, habits, habit_total, finance, study, workouts, questions, xp = await asyncio.gather(
        group(db.task_instances, {'n': {'$sum': 1}}, {'completed': True}), habits_by_day(), db.habits.count_documents(own),
        group(db.transactions, {k: {'$sum': {'$cond': [{'$eq': ['$type', k]}, '$amount', 0]}} for k in ('income', 'expense')}),
        group(db.study_sessions, {'minutes': {'$sum': '$duration_minutes'}}),
        group(db.workout_logs, {'n': {'$sum': 1}, 'minutes': {'$sum': '$duration_minutes'}}, {'completed': True}),
        group(db.question_logs, {'n': {'$sum': '$total'}, 'correct': {'$sum': '$correct'}}),
        group(db.xp_logs, {'n': {'$sum': '$amount'}}),
    )
    data, accumulated = [], 0
    for day in dates:
        income, expenses = finance.get(day, {}).get('income', 0), finance.get(day, {}).get('expense', 0)
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
