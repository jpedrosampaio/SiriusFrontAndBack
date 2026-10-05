"""Shared writer for generated/imported workout plans, XP and activity receipts."""
from uuid import UUID
from pydantic import ValidationError
from fastapi import HTTPException
from db.activity import run_activity
from db.repositories.health import HealthRepository
from db.models.health import WorkoutSession,WorkoutLog
from db.session import unit_of_work
from sqlalchemy import select,func
from services.workout_plan_routes import PlanBody,plan_json
from services.planning import apply_xp

PARAMETERS=('weekly_progression','workout_type','generation_mode','split_type','split_config','training_days_per_week',
    'cycle_weeks','include_cardio','cardio_type','cardio_mode','health_condition','source','source_filename')


async def save(uid,key,fingerprint,document,xp):
    try:
        fields={key:document[key] for key in PlanBody.model_fields if key in document}
        if fields.get('days'): fields['exercises']=[]
        body=PlanBody.model_validate(fields)
    except ValidationError:
        raise HTTPException(502,'A IA retornou exercícios ou estrutura de treino inválidos.')
    if not body.exercises and not any(d.exercises for d in body.days or []): raise HTTPException(502,'A IA não retornou exercícios.')
    async def apply(session,user):
        repo=HealthRepository(session)
        parent=UUID(document['improved_from']) if document.get('improved_from') else None
        if parent and await repo.plan(user.id,parent) is None: raise HTTPException(404,'Plano original não encontrado.')
        row=await repo.create_plan(user.id,**body.model_dump(),generated_by_ai=document.get('generated_by_ai',True),
            improved_from=parent,improvements_summary=document.get('improvements_summary'),
            objective=document.get('objective'),level=document.get('level'),generation_parameters={k:document[k] for k in PARAMETERS if k in document})
        apply_xp(user,xp)
        return {'success':True,'plan':plan_json(await repo.plan(user.id,row.id)),'xp_earned':xp,'new_xp':user.xp,'new_rank':user.rank}
    return await run_activity(UUID(uid),key,fingerprint,apply)


async def improvement_context(uid,plan_id):
    try: uid,pid=UUID(uid),UUID(plan_id)
    except ValueError: raise HTTPException(422,'Identificador de plano inválido.')
    async with unit_of_work() as session:
        plan=await HealthRepository(session).plan(uid,pid)
        if plan is None: raise HTTPException(404,'Plano não encontrado.')
        total,completed,seconds=(await session.execute(select(func.count(),func.count().filter(WorkoutSession.status=='completed'),
            func.avg(WorkoutSession.total_duration_seconds).filter(WorkoutSession.status=='completed')).where(
                WorkoutSession.user_id==uid,WorkoutSession.plan_id==pid))).one()
        days=await session.scalar(select(func.count(func.distinct(WorkoutLog.date))).where(
            WorkoutLog.user_id==uid,WorkoutLog.plan_id==pid,WorkoutLog.completed.is_(True)))
        summary=f'Total de sessões: {total}, Completadas: {completed}, Duração média: {float(seconds or 0)/60:.0f} min, Dias concluídos: {days}'
        return plan_json(plan),summary
