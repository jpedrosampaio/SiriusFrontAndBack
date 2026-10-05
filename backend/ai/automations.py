"""Deterministic suggestion worker: opt-in, cooldown, quiet hours, no business writes."""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal
from pymongo import ReturnDocument

EVENTS = frozenset(('task.created', 'task.completed', 'task.overdue', 'study.session.completed', 'study.review.overdue', 'study.performance.changed', 'workout.completed', 'workout.skipped', 'budget.threshold_reached', 'goal.progress_changed', 'calendar.event_created', 'edital.updated', 'finance.expense.created'))


def quiet(now, start, end):
    return start <= now.hour < end if start < end else now.hour >= start or now.hour < end if start != end else False


class Automations:
    def __init__(self, db, core, settings):
        self.db, self.core, self.settings, self.worker = db, core, settings, None

    async def emit(self, user_id, event, source, version='1', session=None):
        if event not in EVENTS: return
        key = hashlib.sha256(f'{user_id}:{event}:{source}:{version}'.encode()).hexdigest()
        await self.db.ai_events.update_one({'_id': key, 'user_id': user_id}, {'$setOnInsert': {'type': event, 'status': 'pending', 'created_at': datetime.now(timezone.utc).isoformat()}}, upsert=True, session=session)

    async def suggest(self, user_id, rule, title, evidence, link, now):
        from services.agent_actions import Actions
        prefs = await Actions().preferences(user_id)
        if not prefs.automations or quiet(now, prefs.quiet_start, prefs.quiet_end): return
        if await self.db.ai_insights.find_one({'user_id': user_id, 'rule': rule, 'feedback': 'never'}): return
        # One suggestion per rule per day. Dismissal/snooze cannot recreate it.
        day = now.date().isoformat()
        if await self.db.ai_insights.count_documents({'user_id': user_id, 'date': day}) >= prefs.daily_cap: return
        key = hashlib.sha256(f'{user_id}:{rule}:{day}'.encode()).hexdigest()
        await self.db.ai_insights.update_one({'_id': key, 'user_id': user_id}, {'$setOnInsert': {'insight_id': key, 'rule': rule, 'title': title, 'evidence': evidence, 'link': link, 'date': day, 'created_at': now.isoformat(), 'feedback': None, 'dry_run': self.settings.dry_run}}, upsert=True)

    async def process(self, event):
        user_id = event['user_id']
        now = datetime.now(ZoneInfo('America/Sao_Paulo'))
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
                now = datetime.now(timezone.utc).isoformat()
                event = await self.db.ai_events.find_one_and_update({'$or': [{'status': 'pending'}, {'status': 'processing', 'lease_until': {'$lt': now}}]}, {'$set': {'status': 'processing', 'lease_until': (datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat()}}, return_document=ReturnDocument.AFTER)
                if event:
                    await self.process(event)
                    await self.db.ai_events.update_one({'_id': event['_id'], 'user_id': event['user_id']}, {'$set': {'status': 'processed'}})
                else: await asyncio.sleep(20)
            except asyncio.CancelledError: raise
            except Exception:
                logging.warning('automation worker failed; retry deferred')
                await asyncio.sleep(30)

    async def start(self):
        await self.db.ai_events.create_index([('status', 1), ('lease_until', 1)])
        await self.db.ai_insights.create_index([('user_id', 1), ('date', -1)])
        if self.settings.automations: self.worker = asyncio.create_task(self.run())

    async def stop(self):
        if self.worker:
            self.worker.cancel()
            try: await self.worker
            except asyncio.CancelledError: pass
