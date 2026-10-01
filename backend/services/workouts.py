from datetime import datetime, timezone
from fastapi import HTTPException
from db.activity import run_activity
from db.models.health import SessionExercise
from db.repositories.health import HealthRepository
from services.planning import apply_xp
from services.time import local_today


async def start_session(user_id, plan_id, day_index=0, rest_timer_seconds=60, request_key=None):
    async def apply(session, user):
        repo = HealthRepository(session)
        if await repo.active_session(user.id):
            raise HTTPException(409,'Já existe uma sessão de treino ativa.')
        plan = await repo.plan(user.id,plan_id)
        if plan is None:
            raise HTTPException(404,'Plano de treino não encontrado')
        if type(day_index) is not int or day_index < 0 or day_index >= len(plan.days):
            raise HTTPException(422,'Dia de treino inválido.')
        day = plan.days[day_index]
        row = repo.add_session(user_id=user.id,plan_id=plan.id,plan_name=f'{plan.name} - {day.label}',
            day_index=day_index,started_at=datetime.now(timezone.utc),rest_timer_seconds=rest_timer_seconds)
        await session.flush()
        for ex in day.exercises:
            session.add(SessionExercise(user_id=user.id,session_id=row.id,position=ex.position,
                name=ex.name,sets=ex.sets,reps=ex.reps,weight=ex.weight,rest_seconds=ex.rest_seconds,
                muscle_group=ex.muscle_group,tutorial=ex.tutorial,video_url=ex.video_url,notes=ex.notes))
        await session.flush()
        return {'session_id':str(row.id),'plan_id':str(plan.id),'plan_name':row.plan_name,'status':row.status,
            'day_index':day_index,'started_at':row.started_at.isoformat()}
    return await run_activity(user_id,request_key,['start_session',str(plan_id),day_index,rest_timer_seconds],apply)


async def complete_session(user_id, session_id, body, request_key=None):
    async def apply(session, user):
        repo = HealthRepository(session)
        row = await repo.workout_session(user.id,session_id)
        if row is None or row.status != 'active':
            raise HTTPException(404,'Sessão não encontrada ou já finalizada')
        now = datetime.now(timezone.utc)
        seconds = max(0,int((now-row.started_at).total_seconds()))
        completed_count = sum(ex.completed for ex in row.exercises)
        feedback = {'difficulty':body.get('difficulty',3),'feeling':body.get('feeling',''),'notes':body.get('notes',''),
            'completed_exercises':completed_count,'total_exercises':len(row.exercises)}
        xp = 10+completed_count*2+(seconds//900)*5
        row.status,row.completed_at,row.total_duration_seconds,row.feedback = 'completed',now,seconds,feedback
        minutes = max(1,seconds//60)
        repo.add_log(user_id=user.id,session_id=row.id,plan_id=row.plan_id,activity_type='weightlifting',
            name=row.plan_name,duration_minutes=minutes,calories=minutes*6,notes=feedback['notes'],xp_earned=xp,
            completed=True,date=local_today(user.timezone,now=now))
        apply_xp(user,xp)
        return {'success':True,'session_id':str(row.id),'total_duration_seconds':seconds,'total_duration_minutes':minutes,
            'completed_exercises':completed_count,'total_exercises':len(row.exercises),'xp_earned':xp,
            'new_xp':user.xp,'new_rank':user.rank,'feedback':feedback}
    return await run_activity(user_id,request_key,['complete_session',str(session_id),body],apply)
