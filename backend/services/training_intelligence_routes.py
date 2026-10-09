from uuid import UUID
from fastapi import APIRouter, Request, Query
from services.auth_routes import account
from services.training_intelligence import TrainingEngine, substitutions
from training_contracts import TrainingState, SubstitutionArgs, SubstitutionResult

router = APIRouter(prefix='/workouts/intelligence')


@router.get('/state', response_model=TrainingState)
async def state(request: Request, days: int = Query(default=90, ge=7, le=365)):
    user = await account(request)
    return await TrainingEngine().get_state(UUID(user['user_id']), days)


@router.post('/substitutions', response_model=SubstitutionResult)
async def alternatives(request: Request, body: SubstitutionArgs):
    user = await account(request)
    return await substitutions(UUID(user['user_id']), body)
