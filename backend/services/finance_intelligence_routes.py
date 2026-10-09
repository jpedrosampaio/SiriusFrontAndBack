from uuid import UUID
from fastapi import APIRouter, Request, Query
from services.auth_routes import account
from services.finance_routes import DecimalRoute
from services.finance_intelligence import FinanceEngine, exact_wire
from services.finance_debt import compare_debts
from finance_contracts import FinanceState, FinanceScenario, DebtScenario,FinanceSimulation,DebtComparison

router=APIRouter(prefix='/finance/intelligence',route_class=DecimalRoute)
engine=FinanceEngine()


@router.get('/state',response_model=FinanceState)
async def state(request:Request,months:int=Query(default=6,ge=1,le=12)):
    user=await account(request)
    return (await engine.get_state(UUID(user['user_id']),months=months)).model_dump(mode='json')


@router.post('/simulate',response_model=FinanceSimulation)
async def simulate(request:Request,body:FinanceScenario):
    user=await account(request)
    return await engine.simulate(UUID(user['user_id']),body)


@router.post('/compare-debts',response_model=DebtComparison)
async def compare(request:Request,body:DebtScenario):
    await account(request)
    return exact_wire(compare_debts(body))
