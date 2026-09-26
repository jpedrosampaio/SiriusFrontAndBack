"""Period bounds and Mongo-computed report metrics; no raw documents reach AI."""
import asyncio
from datetime import date, timedelta
from calendar import monthrange
from dashboard_service import aggregate_one


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


async def period_metrics(db, user_id, start, end):
    own = {'user_id': user_id}
    bounds = {'$gte': start, '$lte': end}
    dated = {**own, 'date': bounds}
    sum_fields = lambda *names: {n: {'$sum': '$' + n} for n in names}
    async def embedded(collection, field):
        rows = await collection.aggregate([
            {'$match': own}, {'$project': {field: {'$setUnion': [{'$ifNull': ['$' + field, []]}, []]}}},
            {'$unwind': '$' + field}, {'$match': {field: bounds}},
            {'$group': {'_id': None, 'count': {'$sum': 1}}},
        ]).to_list(1)
        return rows[0].get('count', 0) if rows else 0
    created = {**own, 'created_at': {'$gte': start, '$lt': (date.fromisoformat(end) + timedelta(days=1)).isoformat()}}
    tasks, habits, finance, goals, checks, study, focus, questions, workouts, meals, water, task_created, habit_created = await asyncio.gather(
        aggregate_one(db.task_instances, dated, {'done': {'$sum': {'$cond': ['$completed', 1, 0]}}}),
        embedded(db.habits, 'completions'),
        aggregate_one(db.transactions, dated, {k: {'$sum': {'$cond': [{'$eq': ['$type', k]}, '$amount', 0]}} for k in ('income', 'expense')}),
        aggregate_one(db.goals, created, {'count': {'$sum': 1}, 'progress': {'$avg': '$progress'}}),
        embedded(db.goals, 'daily_checks'),
        aggregate_one(db.study_sessions, dated, sum_fields('duration_minutes')),
        aggregate_one(db.focus_sessions, {**dated, 'completed': True}, sum_fields('focus_minutes')),
        aggregate_one(db.question_logs, dated, sum_fields('total', 'correct')),
        aggregate_one(db.workout_logs, {**dated, 'completed': True}, {'count': {'$sum': 1}, **sum_fields('duration_minutes', 'calories')}),
        aggregate_one(db.meals, dated, {'count': {'$sum': 1}, **sum_fields('total_calories', 'total_protein')}),
        aggregate_one(db.water_logs, dated, sum_fields('amount_ml')),
        db.tasks.count_documents(created), db.habits.count_documents(created),
    )
    return {
        'start_date': start, 'end_date': end,
        'tasks': task_created, 'tasks_completed': tasks.get('done', 0),
        'habits': habit_created, 'total_habits_completions': habits,
        'income': finance.get('income', 0), 'expenses': finance.get('expense', 0),
        'goals': goals.get('count', 0), 'goals_progress': goals.get('progress') or 0,
        'goal_checks': checks,
        'study_minutes': study.get('duration_minutes', 0) + focus.get('focus_minutes', 0),
        'questions_answered': questions.get('total', 0), 'questions_correct': questions.get('correct', 0),
        'workouts': workouts.get('count', 0), 'workout_minutes': workouts.get('duration_minutes', 0),
        'meals': meals.get('count', 0), 'calories': meals.get('total_calories', 0),
        'protein': meals.get('total_protein', 0), 'water_ml': water.get('amount_ml', 0),
        'definitions': 'tasks/habits/goals: cadastros criados no intervalo; goals_progress: progresso atual dessas metas, não histórico; demais métricas: atividades no intervalo.',
    }
