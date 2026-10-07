"""Daily quote cache and alerts from typed SQL facts."""
import random
from datetime import datetime,timezone,timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,func
from db.models.identity import User
from db.models.gamification import DailyQuote
from db.models.health import WorkoutLog
from db.models.planning import Habit,HabitCheck
from db.models.finance import Budget,FinancialTransaction
from db.repositories.identity import IdentityRepository
from db.repositories.planning import PlanningRepository
from db.session import unit_of_work
from services.auth_routes import account
from services.planning_routes import habit_json
from services.quote_text import quote_prompt,FALLBACK_QUOTES

router=APIRouter()


def utc_now():return datetime.now(timezone.utc)


def quote_json(row,cached):
    return {'quote':row.quote,'motivational_date':row.motivational_date.isoformat(),'cached':cached,
        'context':{'workouts_this_week':row.workouts_this_week,'habits_today':row.habits_today,'time_of_day':row.time_of_day}}


@router.get('/motivational-quote')
async def quote(request: Request):
    account_row=await account(request);uid=UUID(account_row['user_id'])
    async with unit_of_work() as session:
        user=await session.get(User,uid)
        if user is None:raise HTTPException(404,'User not found')
        now=utc_now().astimezone(ZoneInfo(user.timezone));day=now.date();motivational=(now-timedelta(hours=5)).date()
        previous=await session.scalar(select(DailyQuote).where(DailyQuote.user_id==uid,DailyQuote.motivational_date==motivational))
        if previous:return quote_json(previous,True)
        workouts=await session.scalar(select(func.count()).select_from(WorkoutLog).where(WorkoutLog.user_id==uid,
            WorkoutLog.completed.is_(True),WorkoutLog.date.between(day-timedelta(days=6),day)))
        habits=await session.scalar(select(func.count()).select_from(HabitCheck).join(Habit,
            (Habit.id==HabitCheck.habit_id)&(Habit.user_id==HabitCheck.user_id)).where(HabitCheck.user_id==uid,HabitCheck.date==day,Habit.archived_at.is_(None)))
        period='manhã' if now.hour<12 else 'tarde' if now.hour<18 else 'noite'
        name=user.name
    try:
        from server import call_llm
        response=await call_llm(prompt=quote_prompt(name,period,workouts,habits),session_id=f'motivation_{uid}_{motivational}',
            system_message='Você é um mestre motivacional. Responda somente com uma frase original em português.',user_id=str(uid),task='assistant_chat')
        text=response.strip()
        if not text or text.startswith('⚠'):raise ValueError('No usable quote')
        text=text[:1000]
    except Exception:
        return {'quote':random.choice(FALLBACK_QUOTES),'motivational_date':motivational.isoformat(),'fallback':True}
    async with unit_of_work() as session:
        if await IdentityRepository(session).by_id(uid,lock=True) is None:raise HTTPException(404,'User not found')
        previous=await session.scalar(select(DailyQuote).where(DailyQuote.user_id==uid,DailyQuote.motivational_date==motivational))
        if previous:return quote_json(previous,True)
        row=DailyQuote(user_id=uid,motivational_date=motivational,quote=text,workouts_this_week=workouts,habits_today=habits,time_of_day=period)
        session.add(row)
        return quote_json(row,False)


@router.get('/alerts')
async def alerts(request: Request):
    account_row=await account(request);uid=UUID(account_row['user_id'])
    async with unit_of_work() as session:
        user=await session.get(User,uid)
        if user is None:raise HTTPException(404,'User not found')
        day=utc_now().astimezone(ZoneInfo(user.timezone)).date();month=day.replace(day=1)
        totals=select(FinancialTransaction.category,func.sum(FinancialTransaction.amount).label('spent')).where(
            FinancialTransaction.user_id==uid,FinancialTransaction.type=='expense',FinancialTransaction.date.between(month,day)).group_by(FinancialTransaction.category).subquery()
        rows=(await session.execute(select(Budget,func.coalesce(totals.c.spent,0)).outerjoin(totals,totals.c.category==Budget.category)
            .where(Budget.user_id==uid,Budget.month==month,Budget.limit>0).order_by(Budget.category,Budget.id))).all()
        result=[]
        for budget,spent in rows:
            percentage=spent/budget.limit*100
            if percentage>=90:
                result.append({'type':'budget_alert','severity':'high' if percentage>=100 else 'warning',
                    'title':'Orçamento Estourado' if percentage>=100 else 'Orçamento Quase Estourado',
                    'message':f'Categoria {budget.category}: {percentage:.0f}% do orçamento usado',
                    'data':{'budget_id':str(budget.id),'category':budget.category,'month':month.strftime('%Y-%m'),'limit':budget.limit,'spent':spent}})
        for habit,dates in await PlanningRepository(session).habits_with_dates(uid):
            data=habit_json(habit,[d for d in dates if d<=day],day)
            if day not in dates and data['streak']>0:
                result.append({'type':'habit_reminder','severity':'info','title':'Hábito Pendente',
                    'message':f"{habit.name}: Não esqueça de marcar hoje! Streak: {data['streak']} dias",'data':data})
        return jsonable_encoder(result)
