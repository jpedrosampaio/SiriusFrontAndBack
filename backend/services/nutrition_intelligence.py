"""Deterministic nutrition projections over existing owned records. Previews never write."""
from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, func, text
from db.models.identity import User
from db.models.health import Meal, MealItem, WaterLog, NutritionGoal, NutritionPlan, NutritionPlanDay, PlannedMeal, PlannedFood, Recipe, RecipeIngredient, WorkoutLog, WorkoutSession
from db.models.planning import CalendarEvent
from db.session import unit_of_work
from services.time import local_today
from services.nutrition_evidence import MACROS, number, wire, project
from nutrition_contracts import NutritionState, NutritionPreferences, MealAlternatives

LIMIT = 200


def normalize(value):
    return ' '.join(str(value).casefold().split())


def preferences(owner):
    try:
        return NutritionPreferences.model_validate((owner.preferences or {}).get('nutrition_intelligence', {}))
    except ValidationError:
        # Do not silently discard configured exclusions/budget on corrupt legacy input.
        raise HTTPException(409, 'Preferências nutricionais inválidas; revise a configuração.')


def food_json(row):
    return {k: getattr(row, k) for k in ('name', 'quantity', 'unit', 'calories', 'protein', 'carbs', 'fat', 'nutrition_evidence')}


async def load_meals(session, uid, day):
    rows = (await session.scalars(select(Meal).where(Meal.user_id == uid, Meal.date <= day)
        .order_by(Meal.date.desc(), Meal.created_at.desc(), Meal.id).limit(LIMIT + 1))).all()
    truncated = len(rows) > LIMIT
    rows = rows[:LIMIT]
    ids = [r.id for r in rows]
    foods = (await session.scalars(select(MealItem).where(MealItem.user_id == uid, MealItem.meal_id.in_(ids))
        .order_by(MealItem.meal_id, MealItem.position).limit(5001))).all() if ids else []
    if len(foods) > 5000:
        raise HTTPException(409, 'Histórico detalhado excede o limite seguro; sugestões suspensas.')
    by = {r.id: [] for r in rows}
    for food in foods:
        by[food.meal_id].append(food_json(food))
    return rows, by, truncated


async def load_templates(session, owner, day):
    meals, by, truncated = await load_meals(session, owner.id, day)
    favorites=preferences(owner).favorite_meals
    existing={r.id for r in meals}
    extra=(await session.scalars(select(Meal).where(Meal.user_id==owner.id,Meal.id.in_(favorites),Meal.date<=day))).all() if favorites else []
    extra=[r for r in extra if r.id not in existing]
    if extra:
        items=(await session.scalars(select(MealItem).where(MealItem.user_id==owner.id,MealItem.meal_id.in_([r.id for r in extra])).order_by(MealItem.meal_id,MealItem.position).limit(5001))).all()
        if len(items)>5000:raise HTTPException(409,'Favoritas excedem o limite de detalhes.')
        by.update({r.id:[] for r in extra})
        for f in items:by[f.meal_id].append(food_json(f))
        meals+=extra
    templates=[SimpleNamespace(id=r.id,name=r.name,meal_type=r.meal_type,template_kind='meal') for r in meals]
    planned=(await session.execute(select(PlannedMeal,NutritionPlan.kind).join(NutritionPlanDay,
        (NutritionPlanDay.id==PlannedMeal.day_id)&(NutritionPlanDay.user_id==PlannedMeal.user_id)).join(NutritionPlan,
        (NutritionPlan.id==NutritionPlanDay.plan_id)&(NutritionPlan.user_id==NutritionPlanDay.user_id)).where(PlannedMeal.user_id==owner.id,
        NutritionPlan.archived_at.is_(None),NutritionPlan.active.is_(True)).order_by(PlannedMeal.id).limit(101))).all()
    planned_foods=(await session.scalars(select(PlannedFood).where(PlannedFood.user_id==owner.id,PlannedFood.meal_id.in_([m.id for m,_ in planned[:100]]))
        .order_by(PlannedFood.meal_id,PlannedFood.position).limit(2001))).all() if planned else []
    if len(planned_foods)>2000:raise HTTPException(409,'Planos excedem o limite de detalhes.')
    for meal,kind in planned[:100]:
        template=SimpleNamespace(id=meal.id,name=meal.name,meal_type=meal.meal_type,template_kind='planned')
        templates.append(template)
        # Old positive composition is a stored estimate; old zero cannot prove a known zero.
        by[meal.id]=[{'name':f.name,'quantity':1,'unit':(f.quantity+' '+f.unit).strip() or 'porcao',
            **{k:getattr(f,k) for k in MACROS},'nutrition_evidence':f.nutrition_evidence or {'source':'estimated',
                'known_macros':[k for k in MACROS if getattr(f,k)>0],'basis':'per_unit','portion_label':f.quantity}} for f in planned_foods if f.meal_id==meal.id]
    recipes=(await session.scalars(select(Recipe).where(Recipe.user_id==owner.id).order_by(Recipe.created_at.desc(),Recipe.id).limit(101))).all()
    ingredients=(await session.scalars(select(RecipeIngredient).where(RecipeIngredient.user_id==owner.id,RecipeIngredient.recipe_id.in_([r.id for r in recipes[:100]])).limit(2001))).all() if recipes else []
    if len(ingredients)>2000:raise HTTPException(409,'Receitas excedem o limite de detalhes.')
    for recipe in recipes[:100]:
        templates.append(SimpleNamespace(id=recipe.id,name=recipe.name,meal_type=None,template_kind='recipe',
            ingredient_names=[i.name for i in ingredients if i.recipe_id==recipe.id]))
        by[recipe.id]=[{'name':recipe.name,'quantity':1,'unit':'porcao',**{k:getattr(recipe,k+'_per_serving') for k in MACROS},
            'nutrition_evidence':{'source':'estimated','known_macros':[k for k in MACROS if getattr(recipe,k+'_per_serving')>0],
                'basis':'per_unit','portion_label':'Uma porção da receita'} if recipe.ai_generated else None}]
    return templates,by,truncated or len(planned)>100 or len(recipes)>100


async def load_state(session, owner, day, *, include_context=True):
    uid = owner.id
    today = (await session.scalars(select(Meal).where(Meal.user_id == uid, Meal.date == day)
        .order_by(Meal.created_at, Meal.id).limit(LIMIT + 1))).all()
    if len(today) > LIMIT:
        raise HTTPException(409, 'Registros do dia excedem o limite seguro; totais e sugestões suspensos.')
    items = (await session.scalars(select(MealItem).where(MealItem.user_id == uid,
        MealItem.meal_id.in_([r.id for r in today])).order_by(MealItem.meal_id, MealItem.position)
        .limit(5001))).all() if today else []
    if len(items) > 5000:
        raise HTTPException(409, 'Registros do dia excedem o limite de detalhes seguro.')
    foods = {r.id: [] for r in today}
    for item in items:
        foods[item.meal_id].append(food_json(item))
    all_foods = []
    # Imported historical meal-level totals have no item-level provenance.
    projected_foods={}
    for row in today:
        if any(getattr(row, 'reported_' + k) is not None for k in MACROS):
            projected_foods[row.id]=[{'quantity':1,'nutrition_evidence':None,**{k:getattr(row,'reported_'+k) or 0 for k in MACROS}}]
        else:
            projected_foods[row.id]=foods[row.id] or [{'quantity':1,'nutrition_evidence':{'source':'unknown','known_macros':[]},**{k:0 for k in MACROS}}]
        all_foods.extend(projected_foods[row.id])
    consumed = project(all_foods)
    target = await session.scalar(select(NutritionGoal).where(NutritionGoal.user_id == uid))
    from services.nutrition_data import goal_json
    goals = goal_json(target) if target else None
    confirmed = set((goals or {}).get('confirmed_fields', []))
    remaining = {k: wire(max(Decimal(0), number(goals['daily_' + k]) - number(consumed[k]['total'])))
        if 'daily_' + k in confirmed and consumed[k]['total'] is not None else None for k in MACROS}
    water = await session.scalar(select(func.coalesce(func.sum(WaterLog.amount_ml), 0)).where(WaterLog.user_id == uid, WaterLog.date == day))
    start = day - timedelta(days=27)
    grouped = (await session.execute(select(Meal.date, func.count()).where(Meal.user_id == uid, Meal.date.between(start, day)).group_by(Meal.date))).all()
    planned_rows = (await session.execute(select(PlannedMeal, NutritionPlanDay, NutritionPlan)
        .join(NutritionPlanDay, (NutritionPlanDay.id == PlannedMeal.day_id) & (NutritionPlanDay.user_id == PlannedMeal.user_id))
        .join(NutritionPlan, (NutritionPlan.id == NutritionPlanDay.plan_id) & (NutritionPlan.user_id == NutritionPlanDay.user_id))
        .where(PlannedMeal.user_id == uid, NutritionPlan.active.is_(True), NutritionPlan.archived_at.is_(None))
        .order_by(NutritionPlan.id, NutritionPlanDay.position, PlannedMeal.position).limit(LIMIT + 1))).all()
    planned = []
    for meal, plan_day, plan in planned_rows[:LIMIT]:
        if plan.kind=='diet' and plan.start_date and day<plan.start_date:
            continue
        due = (day if plan.kind=='diet' else plan.start_date + timedelta(days=plan_day.position)) if plan.start_date else None
        if due != day and due is not None:
            continue
        if plan.end_date and day > plan.end_date:
            continue
        logged = any((r.source_reference or {}).get('planned_meal_id') == str(meal.id) for r in today)
        planned.append({'planned_meal_id': str(meal.id), 'plan_id': str(plan.id), 'name': meal.name, 'meal_type': meal.meal_type,
            'date': due.isoformat() if due else None, 'time_label': meal.time, 'date_confirmed': due is not None,
            'status': 'recorded' if logged else 'planned', 'composition_source': 'estimated_or_unverified',
            'macros': {k: wire(number(getattr(meal, k))) for k in MACROS}})
    workouts = (await session.execute(select(WorkoutLog.id, WorkoutLog.name, WorkoutLog.date, WorkoutLog.duration_minutes)
        .where(WorkoutLog.user_id == uid, WorkoutLog.completed.is_(True), WorkoutLog.date.between(day, day + timedelta(days=6)))
        .order_by(WorkoutLog.date, WorkoutLog.id).limit(21))).all() if include_context else []
    active = await session.scalar(select(WorkoutSession).where(WorkoutSession.user_id == uid, WorkoutSession.status == 'active').limit(1)) if include_context else None
    training = [{'log_id': str(r.id), 'name': r.name, 'date': str(r.date), 'recorded_minutes': r.duration_minutes} for r in workouts[:20]]
    if active:
        training.append({'session_id': str(active.id), 'name': active.plan_name, 'status': 'active'})
    zone=ZoneInfo(owner.timezone)
    events=(await session.scalars(select(CalendarEvent).where(CalendarEvent.user_id==uid,
        CalendarEvent.start_at < datetime.combine(day+timedelta(days=7),time.min,zone),
        CalendarEvent.end_at > datetime.combine(day,time.min,zone)).order_by(CalendarEvent.start_at,CalendarEvent.id).limit(51))).all() if include_context else []
    routine=[{'event_id':str(e.id),'title':e.title,'start_at':e.start_at.isoformat(),'end_at':e.end_at.isoformat(),
        'fixed':True} for e in events[:50]]
    limitations = ['Macros por unidade de quantidade declarada; nenhuma conversão implícita de g/ml/porção.',
        'Consistência mede dias com registros, não consumo efetivo nem adesão a uma prescrição.',
        'Metas atuais confirmadas; valores antigos não comprovam metas historicamente configuradas.',
        'Estimativas e origem antiga incerta não são dados nutricionais verificados.',
        'Planos sem data ficam sem data; não implicam refeição consumida nem agendamento.',
        'Treinos não permitem inferir gasto calórico ou necessidades nutricionais.']
    partial = len(planned_rows) > LIMIT or len(workouts) > 20 or len(events)>50
    if partial:
        limitations.append('Limite de detalhes atingido; cobertura parcial explicitamente indicada.')
    return NutritionState(date=day, timezone=owner.timezone, consumed=consumed, goals=goals, remaining=remaining,
        meals=[{'meal_id': str(r.id), 'name': r.name, 'meal_type': r.meal_type, 'foods': foods[r.id],
            'macros': project(projected_foods[r.id]), 'source_reference': r.source_reference} for r in today], water_ml=water,
        routine_context=routine,consistency={'start': str(start), 'end': str(day), 'recorded_days': len(grouped), 'days': 28,
            'meals': sum(n for _, n in grouped)}, planned=planned, training_context=training,
        preferences=preferences(owner).model_dump(mode='json'), limitations=limitations, truncated=partial)


class NutritionEngine:
    async def get_state(self, user_id, day=None, *, include_context=True):
        async with unit_of_work() as session:
            await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            owner = await session.get(User, UUID(str(user_id)))
            if owner is None:
                raise HTTPException(404, 'Usuário não encontrado.')
            return await load_state(session, owner, day or local_today(owner.timezone), include_context=include_context)

    async def alternatives(self, user_id, scenario):
        budget = None
        if scenario.finance_budget_id:
            from services.finance_intelligence import FinanceEngine
            finance = await FinanceEngine().get_state(user_id)
            matching = next((b for b in finance.budgets if b.budget_id == str(scenario.finance_budget_id)), None)
            if not finance.complete or matching is None:
                raise HTTPException(404, 'Orçamento financeiro próprio e completo não encontrado.')
            if matching.effective_limit is None:
                raise HTTPException(409, 'Orçamento percentual sem base registrada suficiente.')
            budget = {'amount': max(Decimal(0), matching.effective_limit - matching.spent), 'period': 'month',
                'source': 'FinanceEngine', 'month': finance.month, 'budget_id': matching.budget_id}
        async with unit_of_work() as session:
            await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            owner = await session.get(User, UUID(str(user_id)))
            if owner is None:
                raise HTTPException(404, 'Usuário não encontrado.')
            day = scenario.date or local_today(owner.timezone)
            state = await load_state(session, owner, day)
            prefs = preferences(owner)
            rows, foods, truncated = await load_templates(session, owner, day)
            if scenario.template_id and not any(r.id == scenario.template_id and r.template_kind==scenario.template_kind for r in rows):
                raise HTTPException(404, 'Refeição própria não encontrada na janela de templates.')
            if budget and (day.replace(day=1) != budget['month'] or (day + timedelta(days=scenario.days - 1)).replace(day=1) != budget['month']):
                raise HTTPException(409, 'O orçamento financeiro consultado pertence a outro mês.')
            if budget is None and prefs.budget is not None:
                budget = {'amount': prefs.budget, 'period': prefs.budget_period, 'source': 'user_configured'}
            return build_alternatives(state, rows, foods, prefs, scenario, budget, truncated)


def build_alternatives(state, rows, foods, prefs, scenario, budget, truncated=False):
    candidates, seen = [], set()
    price_by = {(normalize(p.food), normalize(p.unit)): p for p in prefs.prices}
    excluded = [normalize(s) for s in prefs.excluded_foods if s.strip()]
    available = {normalize(s) for s in prefs.available_foods or []}
    for row in sorted(rows,key=lambda r:r.id not in prefs.favorite_meals):
        if scenario.template_id and (row.id != scenario.template_id or getattr(row,'template_kind','meal')!=scenario.template_kind) or scenario.meal_type and row.meal_type is not None and row.meal_type != scenario.meal_type:
            continue
        items = foods[row.id]
        signature = tuple((normalize(f['name']), str(f['quantity']), f['unit'], *(str(f[k]) for k in MACROS), str(f['nutrition_evidence'])) for f in items)
        if not items or signature in seen:
            continue
        seen.add(signature)
        ingredient_names=getattr(row,'ingredient_names',[f['name'] for f in items])
        if any(ex in normalize(name) for ex in excluded for name in ingredient_names):
            continue
        if scenario.available_only and (prefs.available_foods is None or not ingredient_names or not all(normalize(name) in available for name in ingredient_names)):
            continue
        scaled = [{**f, 'quantity': str(number(f['quantity']) * scenario.portions)} for f in items]
        macros = project(scaled)
        cost = Decimal(0); cost_source = 'known'; missing = []
        for food in scaled:
            price = price_by.get((normalize(food['name']), normalize(food['unit'])))
            if price is None:
                missing.append(food['name'])
            else:
                cost += price.amount * number(food['quantity'])
                if price.source == 'estimated': cost_source = 'estimated'
        if scenario.within_budget and (budget is None or missing or cost > budget['amount']):
            continue
        comparable=[k for k in MACROS if state.remaining[k] is not None]
        fits=all(macros[k]['total'] is not None and number(macros[k]['total'])<=number(state.remaining[k]) for k in comparable) if comparable else None
        candidates.append({'template_id': str(row.id),'template_kind':getattr(row,'template_kind','meal'), 'name': row.name, 'meal_type': row.meal_type or scenario.meal_type,
            'fits_known_remaining':fits,'composition_source':'estimated' if any((f['nutrition_evidence'] or {}).get('source')=='estimated' for f in scaled) else 'registered_or_unverified',
            'favorite': row.id in prefs.favorite_meals, 'portions': str(scenario.portions), 'foods': scaled,
            'macros': macros, 'cost': str(cost) if not missing else None, 'known_cost_subtotal': str(cost),
            'cost_source': cost_source if not missing else 'unknown', 'missing_prices': missing, 'currency': 'BRL',
            'availability': 'declared' if prefs.available_foods is not None and ingredient_names and all(normalize(name) in available for name in ingredient_names) else 'unknown',
            'remaining_after': {k: wire(max(Decimal(0), number(state.remaining[k]) - number(macros[k]['total'])))
                if state.remaining[k] is not None and macros[k]['total'] is not None else None for k in MACROS},
            'reason': 'Fonte própria; favoritas primeiro, depois opções que não ultrapassam o restante conhecido, depois a ordem das fontes. Valores desconhecidos não comprovam compatibilidade. Porção escolhida pela pessoa; não é prescrição.'})
    candidates.sort(key=lambda c: (not c['favorite'],c['fits_known_remaining'] is not True))
    truncated = truncated or len(candidates) > 20
    candidates = candidates[:20]
    chosen = {}; organization = []; used = Decimal(0)
    for candidate in candidates:
        if candidate['meal_type'] is not None:chosen.setdefault(candidate['meal_type'], candidate)
    limit = budget['amount'] if budget else None
    if budget and budget['period'] == 'daily':
        limit *= scenario.days
    for offset in range(scenario.days):
        day_used = Decimal(0)
        for candidate in chosen.values():
            cost = number(candidate['cost']) if candidate['cost'] is not None else None
            if scenario.within_budget and (cost is None or limit is None or used + cost > limit):
                continue
            if scenario.within_budget and budget['period'] == 'daily' and day_used + cost > budget['amount']:
                continue
            if cost is not None: used += cost
            if cost is not None: day_used += cost
            organization.append({'date': str(state.date + timedelta(days=offset)), 'template_id': candidate['template_id'],'template_kind':candidate['template_kind'],
                'name': candidate['name'], 'meal_type': candidate['meal_type'], 'portions': candidate['portions'],
                'cost': candidate['cost'], 'cost_source': candidate['cost_source'], 'status': 'proposal', 'scheduled': False})
    limits = ['Organização é uma proposta sem horários: o Global Planner permanece o único agendador.',
        'Disponibilidade só é confirmada por declaração; histórico de alimentos não comprova estoque.',
        'Preços declarados por unidade não são gastos registrados. Nenhuma compra/transação criada.',
        'Não certifica alergênicos nem substitui avaliação clínica; confira ingredientes e unidades.',
        'Preferências/exclusões usam nomes registrados, sem inferir ingredientes ocultos.']
    if scenario.within_budget and budget is None:
        limits.append('Nenhum orçamento configurado; propostas sob orçamento não comprováveis.')
    if scenario.available_only and prefs.available_foods is None:
        limits.append('Disponibilidade não declarada; opções com estoque confirmado indisponíveis.')
    return MealAlternatives(date=state.date, candidates=candidates, organization=organization,
        budget={**{k: str(v) for k, v in budget.items()}, 'proposed_known_cost': str(used),
            'complete_cost': all(o['cost'] is not None for o in organization), 'currency': 'BRL'} if budget else None,
        limitations=limits+state.limitations, truncated=truncated or state.truncated)


def agent_context(state):
    raw = state.model_dump(mode='json')
    return {**{k: v for k, v in raw.items() if k not in ('meals', 'planned', 'preferences')},
        'meals': [{k: v for k, v in m.items() if k != 'foods'} for m in raw['meals'][:10]],
        'planned': raw['planned'][:20], 'preferences': {k: v for k, v in raw['preferences'].items() if k not in ('prices', 'favorite_meals')},
        'display_limited': len(raw['meals']) > 10 or len(raw['planned']) > 20}
