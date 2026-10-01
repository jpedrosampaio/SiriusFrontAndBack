"""Shared SQL mutations for traditional endpoints and confirmed Agent actions."""
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from db.models.agent import Event
from db.models.planning import CalendarEvent
from db.models.studies import Notebook, StudySession
from db.repositories.finance import FinanceRepository
from db.repositories.planning import PlanningRepository
from services.planning import apply_xp


class CoreWrites:
    async def execute(self, name, user, args, session):
        day = date.fromisoformat(args['date'])
        if name == 'create_task':
            row = await PlanningRepository(session).create_task(user.id,title=args['title'],description=args.get('description'),
                date=day,priority=args['priority'],recurrence=args['recurrence'],xp_reward={'low':5,'medium':10,'high':15}[args['priority']])
            result = {**args,'task_id':str(row.id),'user_id':str(user.id),'xp_reward':row.xp_reward,'is_template':True,'completed':False}
            event = 'task.created'
        elif name in ('record_expense','record_income'):
            row = await FinanceRepository(session).create(user.id,type='expense' if name == 'record_expense' else 'income',
                amount=args['amount'],category=args['category'],description=args.get('description'),date=day)
            result = {**args,'transaction_id':str(row.id),'user_id':str(user.id),'type':row.type,'amount':str(row.amount)}
            event = 'finance.'+row.type+'.created'
        elif name == 'record_study_session':
            notebook_id = UUID(args['notebook_id'])
            notebook = await session.scalar(select(Notebook).where(Notebook.user_id == user.id,Notebook.id == notebook_id))
            if notebook is None:
                raise HTTPException(404,'Caderno não encontrado.')
            row = StudySession(user_id=user.id,notebook_id=notebook_id,date=day,duration_minutes=args['duration_minutes'],
                completed=True,completed_at=datetime.now(timezone.utc),source='manual',notes=args.get('notes'),xp_earned=args['duration_minutes']//15*10)
            session.add(row)
            apply_xp(user,row.xp_earned)
            await session.flush()
            result = {**args,'session_id':str(row.id),'user_id':str(user.id),'xp_earned':row.xp_earned}
            event = 'study.session.completed'
        elif name == 'create_calendar_event':
            if args['end_minute'] <= args['start_minute']:
                raise HTTPException(422,'O compromisso deve terminar depois do início.')
            midnight = datetime.combine(day,time(),tzinfo=ZoneInfo(user.timezone))
            start = (midnight+timedelta(minutes=args['start_minute'])).astimezone(timezone.utc)
            end = (midnight+timedelta(minutes=args['end_minute'])).astimezone(timezone.utc)
            clash = await session.scalar(select(CalendarEvent.id).where(CalendarEvent.user_id == user.id,
                CalendarEvent.start_at < end,CalendarEvent.end_at > start).limit(1))
            if clash:
                raise HTTPException(409,'Este horário conflita com outro compromisso.')
            row = CalendarEvent(user_id=user.id,title=args['title'],start_at=start,end_at=end)
            session.add(row)
            await session.flush()
            result = {**args,'event_id':str(row.id),'user_id':str(user.id)}
            event = 'calendar.event_created'
        else:
            raise HTTPException(422,'Ação indisponível.')
        result['created_at'] = datetime.now(timezone.utc).isoformat()
        session.add(Event(user_id=user.id,event_type=event,payload={'result':result}))
        await session.flush()
        return result
