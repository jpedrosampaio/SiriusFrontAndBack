"""Owned, bounded domain reads shared by the Agent, briefs and automations."""
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from report_metrics import period_metrics


def today():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


class Core:
    def __init__(self, db=None):
        # The optional argument remains until AgentRuntime loses its other Mongo services.
        pass

    async def page_context(self, user_id, raw):
        from services.agent_reads import page_context
        return await page_context(user_id, raw)

    async def read(self, name, user_id):
        from services.agent_reads import read
        if name == 'get_dashboard_summary':
            names = ('get_today_tasks', 'get_study_progress', 'get_workout_progress', 'get_finance_summary')
            return dict(zip(names, await asyncio.gather(*(self.read(n, user_id) for n in names))))
        if name == 'get_daily_plan':
            from ai.planning import plan_day
            tasks, commitments = await asyncio.gather(self.read('get_today_tasks', user_id), self.read('get_calendar', user_id))
            return plan_day(tasks['items'], commitments, tasks['date'])
        if name == 'get_weekly_review': return await self.weekly(user_id)
        return await read(name, user_id)

    async def weekly(self, user_id):
        from services.agent_reads import user_day
        end = await user_day(user_id)
        start = end - timedelta(days=end.weekday())
        current, previous = await asyncio.gather(period_metrics(user_id, start.isoformat(), end.isoformat()), period_metrics(user_id, (start-timedelta(days=7)).isoformat(), (end-timedelta(days=7)).isoformat()))
        adjustments = []
        if current['study_minutes'] < previous['study_minutes']: adjustments.append('Reserve um bloco de estudo compatível com a agenda desta semana.')
        if current['expenses'] > current['income']: adjustments.append('Revise as despesas do período antes de assumir novos gastos.')
        if current['workouts'] < previous['workouts']: adjustments.append('Revise a disponibilidade para os próximos treinos.')
        if current['questions_answered'] and current['questions_correct'] / current['questions_answered'] < .7: adjustments.append('Priorize a revisão das questões erradas.')
        return {'current': current, 'previous_same_weekdays': previous, 'adjustments': adjustments[:5], 'method': 'Períodos com os mesmos dias da semana. Metas criadas e progresso atual não representam variação histórica; tarefas criadas não representam tarefas planejadas.'}
