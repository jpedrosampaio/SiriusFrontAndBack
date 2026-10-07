"""Owned achievements and weekly challenge rewards in SQL transactions."""
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from db.models.gamification import Achievement, WeeklyChallenge
from db.models.planning import TaskInstance, Habit, HabitCheck, Goal
from db.models.finance import FinancialTransaction
from db.models.studies import StudySession, Flashcard
from db.models.health import WorkoutLog, Meal
from db.repositories.identity import IdentityRepository
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.time import local_today
from services.planning import apply_xp, streaks
from services.study_activity_routes import streak_summary
from services.achievement_catalog import achievement_catalog

router=APIRouter()
CHALLENGES=(
    ('tasks','Mestre das Tarefas','Complete 10 tarefas esta semana',50),
    ('habits','Guardião dos Hábitos','Mantenha 5 dias de streak em qualquer hábito',75),
    ('finance','Controlador Financeiro','Registre todas as transações diárias por 5 dias',100),
)


def achievement_json(row):
    return jsonable_encoder({'achievement_id':row.id,'user_id':row.user_id,'title':row.title,'description':row.description,
        'icon':row.icon,'category':row.category,'unlocked_at':row.unlocked_at})


async def metrics(session,user):
    uid=user.id;day=local_today(user.timezone)
    data={}
    for key,model,filters in (
        ('tasks_completed',TaskInstance,[TaskInstance.completed.is_(True),TaskInstance.date<=day]),
        ('habits',Habit,[Habit.archived_at.is_(None)]),('transactions',FinancialTransaction,[]),
        ('flashcards',Flashcard,[Flashcard.archived_at.is_(None)]),('meals',Meal,[]),('goals',Goal,[Goal.archived_at.is_(None)]),
    ):
        data[key]=await session.scalar(select(func.count()).select_from(model).where(model.user_id==uid,*filters))
    for count_key,sum_key,model in (('study_sessions','total_study_minutes',StudySession),('workout_logs','total_workout_minutes',WorkoutLog)):
        data[count_key],data[sum_key]=(await session.execute(select(func.count(),func.coalesce(func.sum(model.duration_minutes),0))
            .where(model.user_id==uid,model.completed.is_(True),model.date<=day))).one()
    rows=(await session.execute(select(HabitCheck.habit_id,HabitCheck.date).join(Habit,
        (Habit.id==HabitCheck.habit_id)&(Habit.user_id==HabitCheck.user_id)).where(HabitCheck.user_id==uid,Habit.archived_at.is_(None),HabitCheck.date<=day))).all()
    dates={}
    for hid,stamp in rows:dates.setdefault(hid,[]).append(stamp)
    data['max_habit_streak']=max((streaks(values,day)[0] for values in dates.values()),default=0)
    data['longest_study_streak']=(await streak_summary(session,uid,user.timezone))['best_streak']
    return data


@router.get('/achievements')
async def achievements(request: Request):
    user=await account(request)
    async with unit_of_work() as session:
        rows=(await session.scalars(select(Achievement).where(Achievement.user_id==UUID(user['user_id']))
            .order_by(Achievement.unlocked_at,Achievement.id))).all()
        return [achievement_json(row) for row in rows]


@router.get('/achievements/full')
async def full(request: Request):
    account_row=await account(request)
    async with unit_of_work() as session:
        user=await IdentityRepository(session).by_id(UUID(account_row['user_id']),lock=True)
        if user is None:raise HTTPException(404,'User not found')
        definitions=achievement_catalog(await metrics(session,user),user.xp)
        unlocked=set((await session.scalars(select(Achievement.key).where(Achievement.user_id==user.id))).all())
        newly=[]
        for item in definitions:
            item['progress']=round(item['current']/item['target']*100,1)
            item['unlocked']=item['progress']>=100 or item['id'] in unlocked
            if item['progress']>=100 and item['id'] not in unlocked:
                session.add(Achievement(user_id=user.id,key=item['id'],unlocked_at=datetime.now(timezone.utc),
                    **{key:item[key] for key in ('title','description','icon','category')}))
                newly.append({key:item[key] for key in ('title','description')})
        total=sum(item['unlocked'] for item in definitions)
        return {'achievements':definitions,'total':len(definitions),'unlocked':total,'locked':len(definitions)-total,
            'completion_pct':round(total/len(definitions)*100,1),'newly_unlocked':newly}


def challenge_json(row):
    return jsonable_encoder({'challenge_id':row.id,'title':row.title,'description':row.description,'xp_reward':row.xp_reward,
        'week_start':row.week_start,'week_end':row.week_end,'created_at':row.created_at,'completed':row.completed_at is not None,
        'completed_by':[str(row.user_id)] if row.completed_at else []})


@router.get('/challenges/current')
async def current(request: Request):
    account_row=await account(request)
    async with unit_of_work() as session:
        user=await IdentityRepository(session).by_id(UUID(account_row['user_id']),lock=True)
        if user is None:raise HTTPException(404,'User not found')
        day=local_today(user.timezone);start=day-timedelta(days=day.weekday())
        rows=list((await session.scalars(select(WeeklyChallenge).where(WeeklyChallenge.user_id==user.id,WeeklyChallenge.week_start==start)
            .order_by(WeeklyChallenge.created_at,WeeklyChallenge.kind))).all())
        present={row.kind for row in rows}
        for kind,title,description,reward in CHALLENGES:
            if kind not in present:
                row=WeeklyChallenge(user_id=user.id,kind=kind,title=title,description=description,xp_reward=reward,week_start=start,week_end=start+timedelta(days=7))
                session.add(row);rows.append(row)
        await session.flush()
        order={kind:index for index,(kind,*_) in enumerate(CHALLENGES)}
        return [challenge_json(row) for row in sorted(rows,key=lambda row:order[row.kind])]


@router.post('/challenges/{challenge_id}/complete')
async def complete(request: Request,challenge_id: UUID):
    user=await account(request)
    async def apply(session,owner):
        row=await session.scalar(select(WeeklyChallenge).where(WeeklyChallenge.user_id==owner.id,WeeklyChallenge.id==challenge_id))
        if row is None:raise HTTPException(404,'Challenge not found')
        if row.completed_at is not None:raise HTTPException(409,'Challenge already completed')
        row.completed_at=datetime.now(timezone.utc)
        apply_xp(owner,row.xp_reward)
        session.add(Achievement(user_id=owner.id,key='challenge:'+str(row.id),title=row.title,description=row.description,
            icon='trophy',category='challenges',unlocked_at=row.completed_at))
        return {'message':'Challenge completed','xp_earned':row.xp_reward,'new_xp':owner.xp,'new_rank':owner.rank}
    return await run_activity(UUID(user['user_id']),'challenge_'+str(challenge_id),['challenge',str(challenge_id)],apply)
