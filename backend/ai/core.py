"""Owned, bounded domain reads shared by the Agent, briefs and automations."""
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dashboard_service import aggregate_one
from report_metrics import period_metrics


def today():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


class Core:
    def __init__(self, db):
        self.db = db

    async def rows(self, user_id, collection, fields, query=None, limit=30):
        return await self.db[collection].find({'user_id': user_id, **(query or {})},
            {'_id': 0, **{k: 1 for k in fields}}).to_list(limit)

    async def page_context(self, user_id, raw):
        import json
        from urllib.parse import parse_qs
        try:
            context = json.loads(raw) if isinstance(raw, str) else raw
            query = parse_qs(str(context.get('query', ''))[:1000].lstrip('?'))
        except (ValueError, TypeError, AttributeError): return {}
        selected = {}
        for parameter, collection, field in [('program', 'study_programs', 'program_id'), ('notebook', 'notebooks', 'notebook_id'), ('analysis', 'edital_analyses', 'analysis_id')]:
            value = context.get(field) or next(iter(query.get(parameter, [])), None)
            if isinstance(value, str) and value and len(value) <= 100:
                row = await self.db[collection].find_one({'user_id': user_id, field: value}, {'_id': 0, field: 1, 'name': 1, 'title': 1})
                if row: selected[parameter] = row
        return selected

    async def read(self, name, user_id):
        own = {'user_id': user_id}
        day = today().isoformat()
        start = day[:8] + '01'
        if name in ('get_today_tasks', 'get_tasks'):
            from task_recurrence import tasks_on_date
            tasks = await tasks_on_date(self.db, user_id, day)
            done = set(await self.db.task_instances.distinct('task_id', {**own, 'date': day, 'completed': True}))
            return {'date': day, 'total': len(tasks), 'completed': len([t for t in tasks if t['task_id'] in done]),
                    'items': [{k: t.get(k) for k in ('task_id', 'title', 'priority', 'date', 'recurrence', 'duration_minutes')} | {'completed': t['task_id'] in done} for t in tasks[:60]], 'truncated': len(tasks) > 60}
        if name == 'get_habits':
            rows = await self.rows(user_id, 'habits', ['habit_id', 'name', 'title', 'completions'])
            return [{k: v for k, v in r.items() if k != 'completions'} | {'completed_today': day in r.get('completions', [])} for r in rows]
        if name == 'get_finance_summary':
            data = await aggregate_one(self.db.transactions, {**own, 'date': {'$gte': start, '$lte': day}},
                {k: {'$sum': {'$cond': [{'$eq': ['$type', k]}, '$amount', 0]}} for k in ('income', 'expense')})
            return {'start': start, 'end': day, 'income': data.get('income', 0), 'expense': data.get('expense', 0), 'balance': data.get('income', 0)-data.get('expense', 0)}
        if name == 'get_budget_status':
            budgets = await self.rows(user_id, 'budgets', ['category', 'amount', 'limit', 'budget_id'], {'month': day[:7]})
            amounts = await self.db.transactions.aggregate([{'$match': {**own, 'type': 'expense', 'date': {'$gte': start, '$lte': day}}}, {'$group': {'_id': '$category', 'spent': {'$sum': '$amount'}}}]).to_list(200)
            spent = {r['_id']: r['spent'] for r in amounts}
            return [b | {'spent': spent.get(b.get('category'), 0)} for b in budgets]
        if name == 'get_study_progress':
            return await self.rows(user_id, 'notebooks', ['notebook_id', 'title', 'name', 'total_study_time_minutes', 'program_id'])
        if name == 'get_wrong_questions':
            return await self.rows(user_id, 'study_topic_reviews', ['topic_key', 'title', 'notebook_id', 'program_id', 'due_date', 'total', 'correct', 'accuracy'])
        if name == 'get_next_study_block':
            plans = await self.rows(user_id, 'study_dated_plans', ['program_id', 'entries'], limit=10)
            entries = [dict(e, program_id=p.get('program_id')) for p in plans for e in p.get('entries', []) if e.get('date', '') >= day and not e.get('completed')]
            return sorted(entries, key=lambda e: (e.get('date', ''), e.get('start_time', '')))[:5]
        if name == 'get_active_workout':
            return await self.rows(user_id, 'workout_plans', ['plan_id', 'name', 'title', 'current_week', 'duration_weeks', 'active'], limit=5)
        if name == 'get_workout_progress':
            return await aggregate_one(self.db.workout_logs, {**own, 'completed': True, 'date': {'$gte': start, '$lte': day}}, {'sessions': {'$sum': 1}, 'minutes': {'$sum': '$duration_minutes'}})
        if name == 'get_nutrition_today':
            return await aggregate_one(self.db.meals, {**own, 'date': day}, {k: {'$sum': '$' + k} for k in ('total_calories', 'total_protein', 'total_carbs', 'total_fat')})
        if name == 'get_calendar':
            return await self.rows(user_id, 'calendar_commitments', ['event_id', 'title', 'date', 'start_minute', 'end_minute'], {'date': day})
        if name in ('get_goals', 'get_upcoming_deadlines'):
            rows = await self.rows(user_id, 'goals', ['goal_id', 'title', 'name', 'progress', 'target_date', 'completed'])
            return rows if name == 'get_goals' else sorted([r for r in rows if r.get('target_date') and not r.get('completed') and r.get('progress', 0) < 100], key=lambda r: r['target_date'])[:10]
        if name == 'get_dashboard_summary':
            names = ('get_today_tasks', 'get_study_progress', 'get_workout_progress', 'get_finance_summary')
            return dict(zip(names, await asyncio.gather(*(self.read(n, user_id) for n in names))))
        if name == 'get_daily_plan':
            from ai.planning import plan_day
            tasks, commitments = await asyncio.gather(self.read('get_today_tasks', user_id), self.read('get_calendar', user_id))
            return plan_day(tasks['items'], commitments, day)
        if name == 'get_weekly_review': return await self.weekly(user_id)
        raise ValueError('Unknown read tool')

    async def weekly(self, user_id):
        end = today()
        start = end - timedelta(days=end.weekday())
        current, previous = await asyncio.gather(period_metrics(self.db, user_id, start.isoformat(), end.isoformat()), period_metrics(self.db, user_id, (start-timedelta(days=7)).isoformat(), (end-timedelta(days=7)).isoformat()))
        adjustments = []
        if current['study_minutes'] < previous['study_minutes']: adjustments.append('Reserve um bloco de estudo compatível com a agenda desta semana.')
        if current['expenses'] > current['income']: adjustments.append('Revise as despesas do período antes de assumir novos gastos.')
        if current['workouts'] < previous['workouts']: adjustments.append('Revise a disponibilidade para os próximos treinos.')
        if current['questions_answered'] and current['questions_correct'] / current['questions_answered'] < .7: adjustments.append('Priorize a revisão das questões erradas.')
        return {'current': current, 'previous_same_weekdays': previous, 'adjustments': adjustments[:5], 'method': 'Períodos com os mesmos dias da semana. Metas criadas e progresso atual não representam variação histórica; tarefas criadas não representam tarefas planejadas.'}
