from uuid import UUID
from fastapi import APIRouter,Request,Query
from sqlalchemy import select,func,or_
from db.models.health import WorkoutLog,WorkoutLogExercise,SessionExercise,WorkoutPlan
from db.repositories.health import HealthRepository
from db.session import unit_of_work
from services.auth_routes import account
from services.workout_logs import serialize_logs
from services.workout_plan_routes import plan_json

router=APIRouter()


def matching_exercise(uid,name,exact):
    def matches(column):
        normalized=func.lower(func.trim(column))
        return normalized==name.strip().lower() if exact else normalized.contains(name.strip().lower(),autoescape=True)
    manual=select(WorkoutLogExercise.id).where(WorkoutLogExercise.user_id==uid,WorkoutLogExercise.log_id==WorkoutLog.id,matches(WorkoutLogExercise.name)).exists()
    session=select(SessionExercise.id).where(SessionExercise.user_id==uid,SessionExercise.session_id==WorkoutLog.session_id,matches(SessionExercise.name)).exists()
    return or_(manual,session)


async def history_logs(session,uid,name=None,exact=False,limit=500):
    query=select(WorkoutLog).where(WorkoutLog.user_id==uid,WorkoutLog.completed.is_(True))
    if name:query=query.where(matching_exercise(uid,name,exact))
    rows=(await session.scalars(query.order_by(WorkoutLog.date.desc(),WorkoutLog.created_at.desc(),WorkoutLog.id).limit(limit))).all()
    return await serialize_logs(session,uid,rows)


@router.get('/workouts/exercise-history')
async def exercise_history(request: Request,exercise_name: str=Query('',max_length=300)):
    user=await account(request)
    if not exercise_name.strip():return {'history':[]}
    async with unit_of_work() as session:
        logs=await history_logs(session,UUID(user['user_id']),exercise_name,True,5)
    result=[]
    for log in logs:
        ex=next((ex for ex in log['exercises_completed'] if ex['name'].strip().lower()==exercise_name.strip().lower()),None)
        if ex: result.append({'date':log['date'],'log_name':log['name'],'exercise_name':ex['name'],
            **{k:ex[k] for k in ('sets_data','weight','reps','sets_completed')}})
    return {'history':result}


@router.get('/workout-stats/exercise-evolution')
async def evolution(request: Request,exercise_name: str | None=Query(None,max_length=300)):
    user=await account(request)
    async with unit_of_work() as session:logs=await history_logs(session,UUID(user['user_id']),exercise_name)
    result={}
    for log in reversed(logs):
        for ex in log['exercises_completed']:
            name=ex['name'].strip()
            if exercise_name and exercise_name.strip().lower() not in name.lower():continue
            common={'date':log['date'],'source':'session' if log['session_id'] else 'log','plan_name':log['name']}
            if ex['sets_data']:
                points=[{**common,'weight':s['weight'],'reps':s['reps']} for s in ex['sets_data'] if s['completed']]
            else:points=[{**common,'weight':ex['weight'],'reps':ex['reps'],'sets':ex['sets_completed']}]
            result.setdefault(name,[]).extend(points)
    return {'exercises':result,'exercise_names':sorted(result) if not exercise_name else [exercise_name]}


@router.get('/workouts/next-loads')
async def next_loads(request: Request,plan_id: UUID | None=None):
    from services.training_intelligence import load_state, normalized, decimal
    from services.time import local_today
    from sqlalchemy import text
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        if plan_id is None:plan_id=await session.scalar(select(WorkoutPlan.id).where(WorkoutPlan.user_id==uid,WorkoutPlan.archived_at.is_(None)).order_by(WorkoutPlan.created_at.desc(),WorkoutPlan.id).limit(1))
        plan=await HealthRepository(session).plan(uid,plan_id) if plan_id else None
        if plan is None:return {'suggestions':[]}
        document=plan_json(plan)
        state=await load_state(session,uid,local_today(user['timezone']),user['timezone'],plan_id=plan.id)
    by_key={(normalized(ex.name),normalized(ex.muscle_group)):ex for ex in state.exercises}
    suggestions=[]
    for day in document['days']:
        for ex in day['exercises']:
            previous=by_key.get((normalized(ex['name']),normalized(ex['muscle_group'])))
            progress=previous.progression if previous else None
            # A historical recommendation must also match the currently displayed prescription.
            last=previous.history[-1] if previous and previous.history else None
            matches=last and last.prescribed_sets==ex['sets'] and str(last.target_reps)==str(ex['reps'])
            prescribed=decimal(ex['weight'])
            if progress and prescribed is not None and progress.current_weight is not None and prescribed!=decimal(progress.current_weight):
                matches=False
            suggested=progress.suggested_weight if progress and matches else None
            suggestions.append({'name':ex['name'],'day_label':day['day_label'],'sets':ex['sets'],'reps':ex['reps'],
                'current_weight':ex['weight'],'next_weight':float(suggested) if suggested is not None else None,
                'reason':progress.reason if progress and matches else 'Dados comparáveis insuficientes para esta prescrição.',
                'progress_possible':bool(suggested),'automatic':False})
    return {'suggestions':suggestions,'plan_id':document['plan_id'],'plan_name':document['name']}
