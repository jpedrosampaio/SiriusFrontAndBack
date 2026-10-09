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

    async def life_context(self, user_id):
        from services.life_state import daily, agent_context, agent_plan
        result=await daily(user_id)
        return {'get_daily_plan':agent_plan(result['plan']),
            'get_life_state':agent_context(result['state'])}

    async def read(self, name, user_id, arguments=None):
        from services.agent_reads import read
        if name in ('get_finance_state','simulate_finances','compare_debt_strategies'):
            from services.finance_intelligence import FinanceEngine,agent_context,exact_wire
            from services.finance_debt import compare_debts
            from finance_contracts import FinanceScenario,DebtScenario
            if name=='get_finance_state':return agent_context(await FinanceEngine().get_state(user_id))
            if name=='compare_debt_strategies':return exact_wire(compare_debts(DebtScenario.model_validate(arguments or {})))
            result=await FinanceEngine().simulate(user_id,FinanceScenario.model_validate(arguments or {}))
            return {**{k:v for k,v in result.items() if k!='state'},'state':agent_context(result['state'])}
        if name == 'get_dashboard_summary':
            names = ('get_today_tasks', 'get_study_progress', 'get_workout_progress', 'get_finance_summary')
            return dict(zip(names, await asyncio.gather(*(self.read(n, user_id) for n in names))))
        if name == 'get_daily_plan':
            from services.life_state import daily,agent_plan
            return agent_plan((await daily(user_id))['plan'])
        if name == 'get_life_state':
            from services.life_state import snapshot,agent_context
            return agent_context(await snapshot(user_id))
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
