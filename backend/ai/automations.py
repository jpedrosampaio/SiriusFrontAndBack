"""Deterministic suggestion worker: opt-in, cooldown, quiet hours, no business writes."""
import asyncio
import logging
from decimal import Decimal

EVENTS = frozenset(('task.created', 'task.completed', 'task.overdue', 'study.session.completed', 'study.review.overdue', 'study.performance.changed', 'workout.completed', 'workout.skipped', 'budget.threshold_reached', 'goal.progress_changed', 'calendar.event_created', 'edital.updated', 'finance.expense.created'))


def quiet(now, start, end):
    return start <= now.hour < end if start < end else now.hour >= start or now.hour < end if start != end else False


class Automations:
    def __init__(self, core, settings):
        self.core, self.settings, self.worker = core, settings, None

    async def emit(self, user_id, event, source, version='1', session=None):
        if event not in EVENTS: return
        from services.agent_automations import emit
        await emit(user_id,event,source,version,session)

    async def suggest(self, user_id, rule, title, evidence, link, now):
        from services.agent_automations import suggest
        return await suggest(user_id,rule,title,evidence,link,now,self.settings.dry_run)

    async def process(self, event):
        user_id = event['user_id']
        from services.agent_automations import local_now
        now = await local_now(user_id)
        if now is None: return
        if event['type'] in ('finance.expense.created', 'budget.threshold_reached'):
            for budget in await self.core.read('get_budget_status', user_id):
                limit = budget.get('amount') or budget.get('limit') or 0
                if limit > 0 and budget['spent'] >= limit * Decimal('0.8'):
                    await self.suggest(user_id, 'budget:' + budget.get('category', ''), 'Seu orçamento está próximo do limite', {'category': budget.get('category'), 'spent': str(budget['spent']), 'limit': str(limit)}, '/finance', now)
        elif event['type'] in ('study.session.completed', 'study.review.overdue', 'study.performance.changed'):
            await self.suggest(user_id, 'study_review', 'Confira seus próximos blocos de estudo', {'next_blocks': await self.core.read('get_next_study_block', user_id)}, '/studies', now)
        elif event['type'] in ('task.created', 'task.overdue', 'calendar.event_created'):
            await self.suggest(user_id, 'daily_plan', 'Revise a capacidade do seu dia', {'tasks': await self.core.read('get_today_tasks', user_id)}, '/assistant/settings', now)

    async def run(self):
        while True:
            try:
                from services.agent_automations import claim, finish
                event = await claim()
                if event:
                    await self.process(event)
                    await finish(event)
                else: await asyncio.sleep(20)
            except asyncio.CancelledError: raise
            except Exception:
                logging.warning('automation worker failed; retry deferred')
                await asyncio.sleep(30)

    async def start(self):
        if self.settings.automations and self.worker is None:
            self.worker = asyncio.create_task(self.run())

    async def stop(self):
        if self.worker:
            self.worker.cancel()
            try: await self.worker
            except asyncio.CancelledError: pass
            self.worker = None
