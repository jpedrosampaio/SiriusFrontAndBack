"""Shared writer for generated/imported workout plans, XP and activity receipts."""
from uuid import UUID
from pydantic import ValidationError
from fastapi import HTTPException
from db.activity import run_activity
from db.repositories.health import HealthRepository
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
        row=await repo.create_plan(user.id,**body.model_dump(),generated_by_ai=document.get('generated_by_ai',True),
            objective=document.get('objective'),level=document.get('level'),generation_parameters={k:document[k] for k in PARAMETERS if k in document})
        apply_xp(user,xp)
        return {'success':True,'plan':plan_json(await repo.plan(user.id,row.id)),'xp_earned':xp,'new_xp':user.xp,'new_rank':user.rank}
    return await run_activity(UUID(uid),key,fingerprint,apply)
