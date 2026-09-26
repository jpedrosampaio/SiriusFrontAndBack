"""Domain mutations accept an existing transaction; never call a model."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException


class CoreWrites:
    def __init__(self, db, award_xp, update_streak):
        self.db, self.award_xp, self.update_streak = db, award_xp, update_streak

    async def execute(self, name, user_id, args, session):
        stamp = datetime.now(timezone.utc).isoformat()
        document = {**args, 'user_id': user_id, 'created_at': stamp}
        if name == 'create_task':
            document.update(task_id='task_' + uuid.uuid4().hex[:12], xp_reward={'low': 5, 'medium': 10, 'high': 15}[args['priority']], is_template=True)
            collection, event = 'tasks', 'task.created'
        elif name in ('record_expense', 'record_income'):
            document.update(transaction_id='trans_' + uuid.uuid4().hex[:12], type='expense' if name == 'record_expense' else 'income', amount=float(Decimal(str(args['amount'])).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)))
            if document['amount'] <= 0:
                raise HTTPException(422, 'Valor deve ser de pelo menos um centavo.')
            if name == 'record_expense':
                await self.db.budgets.update_one({'user_id': user_id, 'category': args['category'], 'month': args['date'][:7]}, {'$inc': {'spent': document['amount']}}, session=session)
            collection, event = 'transactions', 'finance.' + document['type'] + '.created'
        elif name == 'record_study_session':
            owned = await self.db.notebooks.find_one({'user_id': user_id, 'notebook_id': args['notebook_id']}, {'_id': 1}, session=session)
            if not owned: raise HTTPException(404, 'Caderno não encontrado.')
            document.update(session_id='ssession_' + uuid.uuid4().hex[:12], xp_earned=args['duration_minutes']//15*10)
            await self.db.notebooks.update_one({'user_id': user_id, 'notebook_id': args['notebook_id']}, {'$inc': {'total_study_time_minutes': args['duration_minutes']}}, session=session)
            await self.award_xp(user_id, document['xp_earned'], session=session)
            await self.update_streak(user_id, session=session)
            collection, event = 'study_sessions', 'study.session.completed'
        elif name == 'create_calendar_event':
            if args['end_minute'] <= args['start_minute']:
                raise HTTPException(422, 'O compromisso deve terminar depois do início.')
            clash = await self.db.calendar_commitments.find_one({'user_id': user_id, 'date': args['date'], 'start_minute': {'$lt': args['end_minute']}, 'end_minute': {'$gt': args['start_minute']}}, {'_id': 1}, session=session)
            if clash: raise HTTPException(409, 'Este horário conflita com outro compromisso.')
            document.update(event_id='event_' + uuid.uuid4().hex[:12])
            collection, event = 'calendar_commitments', 'calendar.event_created'
        else:
            raise HTTPException(422, 'Ação indisponível.')
        await self.db[collection].insert_one(document, session=session)
        document.pop('_id', None)
        await self.db.ai_events.insert_one({'event_id': uuid.uuid4().hex, 'user_id': user_id, 'type': event, 'created_at': stamp, 'status': 'pending'}, session=session)
        return document
