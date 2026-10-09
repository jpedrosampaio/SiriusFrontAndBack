from datetime import date
from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from db.models.identity import User
from db.models.health import Meal, MealItem
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.nutrition_intelligence import NutritionEngine, normalize
from services.nutrition_evidence import number
from nutrition_contracts import NutritionState, MealScenario, MealAlternatives, NutritionPreferences, RepeatMeal
from services.nutrition_plan_dto import ConfirmPlan

router = APIRouter(prefix='/nutrition/intelligence')


@router.post('/templates/{kind}/{identity}/record')
async def record_source(request: Request, kind: str, identity: UUID, body: RepeatMeal):
    if kind=='meal':return await repeat(request,identity,body)
    if kind not in ('planned','recipe'):raise HTTPException(404,'Tipo de template desconhecido.')
    user=await account(request)
    if not request.headers.get('Idempotency-Key'):raise HTTPException(400,'Registro exige chave de idempotência.')
    async def apply(session,owner):
        from db.models.health import PlannedMeal,PlannedFood,NutritionPlan,NutritionPlanDay,Recipe
        from services.nutrition_evidence import MACROS
        if kind=='planned':
            source=await session.scalar(select(PlannedMeal).join(NutritionPlanDay,
                (NutritionPlanDay.id==PlannedMeal.day_id)&(NutritionPlanDay.user_id==PlannedMeal.user_id)).join(NutritionPlan,
                (NutritionPlan.id==NutritionPlanDay.plan_id)&(NutritionPlan.user_id==NutritionPlanDay.user_id)).where(
                    PlannedMeal.user_id==owner.id,PlannedMeal.id==identity,NutritionPlan.archived_at.is_(None),NutritionPlan.active.is_(True)))
            if source is None:raise HTTPException(404,'Refeição planejada própria não encontrada.')
            items=(await session.scalars(select(PlannedFood).where(PlannedFood.user_id==owner.id,PlannedFood.meal_id==identity).order_by(PlannedFood.position).limit(301))).all()
            if len(items)>300:raise HTTPException(409,'Limite de alimentos excedido.')
            data=[{'name':f.name,'quantity':float(body.portions),'unit':(f.quantity+' '+f.unit).strip() or 'porcao',
                **{k:getattr(f,k) for k in MACROS},'nutrition_evidence':f.nutrition_evidence or {'source':'estimated','known_macros':[k for k in MACROS if getattr(f,k)>0],'basis':'per_unit','portion_label':f.quantity}} for f in items]
            meal_type=body.meal_type or source.meal_type
        else:
            source=await session.scalar(select(Recipe).where(Recipe.user_id==owner.id,Recipe.id==identity))
            if source is None:raise HTTPException(404,'Receita própria não encontrada.')
            if body.meal_type is None:raise HTTPException(422,'Escolha o tipo da refeição para registrar a receita.')
            meal_type=body.meal_type
            data=[{'name':source.name,'quantity':float(body.portions),'unit':'porcao',**{k:getattr(source,k+'_per_serving') for k in MACROS},
                'nutrition_evidence':{'source':'estimated','known_macros':[k for k in MACROS if getattr(source,k+'_per_serving')>0],
                    'basis':'per_unit','portion_label':'Uma porção da receita'} if source.ai_generated else None}]
        if not data:raise HTTPException(409,'Template sem alimentos; revise antes de registrar.')
        row=Meal(user_id=owner.id,name=source.name,meal_type=meal_type,date=body.date,source_reference={
            'planned_meal_id' if kind=='planned' else 'recipe_id':str(identity),'portions':str(body.portions)})
        row.items=[MealItem(user_id=owner.id,position=i,**food) for i,food in enumerate(data)]
        session.add(row);await session.flush()
        from services.nutrition import meal_json
        return meal_json(row)
    return await run_activity(UUID(user['user_id']),request.headers['Idempotency-Key'],['nutrition-template-record',kind,str(identity),body.model_dump(mode='json')],apply)


@router.post('/confirm-plan')
async def confirm_plan(request: Request, body: ConfirmPlan):
    from services.nutrition_plans import save_plan
    user=await account(request)
    if not request.headers.get('Idempotency-Key'):
        raise HTTPException(400,'Confirmação exige chave de idempotência.')
    return await save_plan(user['user_id'],body.plan,'imported',request.headers['Idempotency-Key'],
        ['nutrition-confirm-import',body.model_dump(mode='json')],preview_id=body.preview_id)


@router.get('/state', response_model=NutritionState)
async def state(request: Request, date: date | None = None):
    user = await account(request)
    return await NutritionEngine().get_state(user['user_id'], date)


@router.post('/alternatives', response_model=MealAlternatives)
async def alternatives(request: Request, body: MealScenario):
    user = await account(request)
    return await NutritionEngine().alternatives(user['user_id'], body)


@router.put('/preferences', response_model=NutritionPreferences)
async def configure(request: Request, body: NutritionPreferences):
    user = await account(request)
    async def apply(session, owner):
        if body.favorite_meals:
            found = (await session.scalars(select(Meal.id).where(Meal.user_id == owner.id, Meal.id.in_(body.favorite_meals)))).all()
            if set(found) != set(body.favorite_meals):
                raise HTTPException(404, 'Favorita própria não encontrada.')
        keys = [(normalize(p.food), normalize(p.unit)) for p in body.prices]
        if len(keys) != len(set(keys)):
            raise HTTPException(422, 'Informe somente um preço por alimento/unidade.')
        owner.preferences = {**(owner.preferences or {}), 'nutrition_intelligence': body.model_dump(mode='json')}
        return body.model_dump(mode='json')
    return await run_activity(UUID(user['user_id']), request.headers.get('Idempotency-Key'), ['nutrition-preferences', body.model_dump(mode='json')], apply)


@router.post('/templates/{meal_id}/record')
async def repeat(request: Request, meal_id: UUID, body: RepeatMeal):
    user = await account(request)
    if not request.headers.get('Idempotency-Key'):
        raise HTTPException(400, 'Registro rápido exige chave de idempotência.')
    async def apply(session, owner):
        original = await session.scalar(select(Meal).where(Meal.user_id == owner.id, Meal.id == meal_id))
        if original is None:
            raise HTTPException(404, 'Refeição própria não encontrada.')
        items = (await session.scalars(select(MealItem).where(MealItem.user_id == owner.id, MealItem.meal_id == original.id)
            .order_by(MealItem.position).limit(301))).all()
        if not items or len(items) > 300:
            raise HTTPException(409, 'Template sem alimentos reutilizáveis ou acima do limite.')
        row = Meal(user_id=owner.id, name=original.name, meal_type=original.meal_type, date=body.date, notes=original.notes,
            source_reference={'template_meal_id': str(original.id), 'portions': str(body.portions)})
        row.items = [MealItem(user_id=owner.id, position=i, name=f.name, quantity=float(number(f.quantity) * body.portions),
            unit=f.unit, nutrition_evidence=f.nutrition_evidence,
            **{k: getattr(f, k) for k in ('calories', 'protein', 'carbs', 'fat')}) for i, f in enumerate(items)]
        for k in ('calories', 'protein', 'carbs', 'fat'):
            value = getattr(original, 'reported_' + k)
            setattr(row, 'reported_' + k, float(number(value) * body.portions) if value is not None else None)
        session.add(row); await session.flush()
        from services.nutrition import meal_json
        return meal_json(row)
    return await run_activity(UUID(user['user_id']), request.headers['Idempotency-Key'], ['nutrition-repeat', str(meal_id), body.model_dump(mode='json')], apply)
