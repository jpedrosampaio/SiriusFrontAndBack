"""Normalized meals, hydration and nutrition targets; SQL period aggregates."""
from datetime import date as Date,timedelta,datetime,timezone
from typing import Annotated,Literal
from uuid import UUID
from fastapi import APIRouter,Request,Query,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field
from sqlalchemy import select,delete,func,cast,Numeric
from sqlalchemy.orm import selectinload
from db.models.health import Meal,MealItem,WaterLog,NutritionGoal
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.time import local_today

router=APIRouter(prefix='/nutrition')
from services.nutrition_data import Nonnegative,MACROS,GoalBody,goal_json,period

class Food(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    quantity: Nonnegative=1
    unit: str=Field(default='porcao',max_length=100)
    calories: Nonnegative=0
    protein: Nonnegative=0
    carbs: Nonnegative=0
    fat: Nonnegative=0
    estimated: bool=False
    portion_label: str=Field(default='',max_length=300)
    known_macros: list[Literal['calories','protein','carbs','fat']] | None=Field(default=None,max_length=4)

class MealBody(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    meal_type: str=Field(max_length=100)
    foods: list[Food]=Field(default_factory=list,max_length=300)
    date: Date
    notes: str | None=Field(default=None,max_length=20000)





def meal_json(row):
    from services.nutrition_evidence import number
    foods=[{**{key:getattr(item,key) for key in Food.model_fields if key not in ('estimated','portion_label','known_macros')},
        'estimated':(item.nutrition_evidence or {}).get('source')=='estimated',
        'portion_label':(item.nutrition_evidence or {}).get('portion_label',''),
        'nutrition_evidence':item.nutrition_evidence} for item in row.items]
    totals={key:number(getattr(row,'reported_'+key)) if getattr(row,'reported_'+key) is not None else sum((number(food[key])*number(food['quantity']) for food in foods),number(0)) for key in MACROS}
    return jsonable_encoder({'meal_id':row.id,'user_id':row.user_id,'name':row.name,'meal_type':row.meal_type,
        'date':row.date,'notes':row.notes,'created_at':row.created_at,'foods':foods,
        **{'total_'+key:float(round(value,3)) for key,value in totals.items()}})


def water_json(row):
    return jsonable_encoder({'log_id':row.id,'user_id':row.user_id,'amount_ml':row.amount_ml,'date':row.date,'created_at':row.created_at})


@router.get('/meals')
async def meals(request: Request,date: Date | None=None):
    user=await account(request)
    async with unit_of_work() as session:
        query=select(Meal).options(selectinload(Meal.items)).where(Meal.user_id==UUID(user['user_id']))
        if date:query=query.where(Meal.date==date)
        rows=(await session.scalars(query.order_by(Meal.date.desc(),Meal.created_at.desc()).limit(1000))).all()
        return [meal_json(row) for row in rows]


@router.post('/meals')
async def create_meal(request: Request,body: MealBody):
    user=await account(request)
    from services.nutrition_evidence import evidence
    async def apply(session,owner):
        row=Meal(user_id=owner.id,**body.model_dump(exclude={'foods'}))
        row.items=[MealItem(user_id=owner.id,position=i,nutrition_evidence=evidence(food),**food.model_dump(exclude={'estimated','portion_label','known_macros'})) for i,food in enumerate(body.foods)]
        session.add(row);await session.flush();return meal_json(row)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['meal',body.model_dump(mode='json'),[evidence(f) for f in body.foods]],apply)


@router.delete('/meals/{meal_id}')
async def delete_meal(request: Request,meal_id: UUID):
    user=await account(request)
    async def apply(session,owner):
        result=await session.execute(delete(Meal).where(Meal.user_id==owner.id,Meal.id==meal_id))
        if not result.rowcount:raise HTTPException(404,'Meal not found')
        prefs=(owner.preferences or {}).get('nutrition_intelligence')
        if isinstance(prefs,dict):
            owner.preferences={**owner.preferences,'nutrition_intelligence':{**prefs,
                'favorite_meals':[v for v in prefs.get('favorite_meals',[]) if v!=str(meal_id)]}}
        return {'message':'Meal deleted'}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['nutrition-delete',str(meal_id)],apply)


async def goals_write(request,body=None):
    user=await account(request)
    if body is None or not body.model_fields_set:raise HTTPException(422,'Informe ao menos uma meta explícita.')
    async def apply(session,owner):
        row=await session.scalar(select(NutritionGoal).where(NutritionGoal.user_id==owner.id))
        if row is None:
            row=NutritionGoal(user_id=owner.id,**(body or GoalBody()).model_dump());session.add(row)
        elif body:
            for key,value in body.model_dump(exclude_unset=True).items():setattr(row,key,value)
        row.confirmed_at=datetime.now(timezone.utc)
        row.confirmed_fields=sorted(set(row.confirmed_fields or []) | set(body.model_fields_set if body else []))
        await session.flush();await session.refresh(row);return goal_json(row)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key') if body else None,
        ['nutrition-goals',body.model_dump(exclude_unset=True) if body else None],apply)


@router.get('/goals')
async def goals(request: Request):
    user=await account(request)
    async with unit_of_work() as session:
        return goal_json(await session.scalar(select(NutritionGoal).where(NutritionGoal.user_id==UUID(user['user_id']))))


@router.put('/goals')
async def update_goals(request: Request,body: GoalBody):return await goals_write(request,body)


@router.get('/water')
async def water(request: Request,date: Date | None=None):
    user=await account(request);day=date or local_today(user['timezone']);uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        filters=(WaterLog.user_id==uid,WaterLog.date==day)
        rows=(await session.scalars(select(WaterLog).where(*filters).order_by(WaterLog.created_at.desc()).limit(100))).all()
        total=await session.scalar(select(func.coalesce(func.sum(WaterLog.amount_ml),0)).where(*filters))
        return {'logs':[water_json(row) for row in rows],'total_ml':total,'date':day.isoformat()}


@router.post('/water')
async def add_water(request: Request,amount_ml: int=Query(gt=0),date: Date | None=None):
    user=await account(request);day=date or local_today(user['timezone'])
    async def apply(session,owner):
        row=WaterLog(user_id=owner.id,date=day,amount_ml=amount_ml);session.add(row);await session.flush();return water_json(row)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['water',day.isoformat(),amount_ml],apply)




@router.get('/stats')
async def stats(request: Request,date: Date | None=None):
    user=await account(request);day=date or local_today(user['timezone'])
    from services.nutrition_intelligence import NutritionEngine
    state=await NutritionEngine().get_state(user['user_id'],day,include_context=False)
    goals=state.goals or goal_json(None)
    consumed={key:float(state.consumed[key].total) if state.consumed[key].total is not None else None for key in MACROS};consumed['water_ml']=state.water_ml
    remaining={key:float(value) if value is not None else None for key,value in state.remaining.items()}
    remaining['water_ml']=max(0,goals['water_goal_ml']-state.water_ml) if 'water_goal_ml' in goals.get('confirmed_fields',[]) else None
    return {'date':day.isoformat(),'consumed':consumed,'consumed_details':{k:v.model_dump() for k,v in state.consumed.items()},'goals':goals,'meals_count':len(state.meals),'remaining':remaining}


@router.get('/weekly-trend')
async def weekly(request: Request):
    user=await account(request);today=local_today(user['timezone']);start=today-timedelta(days=6)
    async with unit_of_work() as session:meals,water,goals=await period(session,UUID(user['user_id']),start,today)
    daily=[]
    for offset in range(7):
        day=start+timedelta(days=offset);values=meals.get(day,{})
        daily.append({'day':day.strftime('%a'),'date':day.isoformat(),'calorias':round(values.get('calories',0)),
            'proteina':round(values.get('protein',0),1),'carboidratos':round(values.get('carbs',0),1),
            'gordura':round(values.get('fat',0),1),'agua_ml':water.get(day,0),'refeicoes':values.get('meals_count',0)})
    recorded=[day for day in daily if day['calorias']>0]
    return {'daily':daily,'goals':goals,'averages':{'calorias':round(sum(day['calorias'] for day in recorded)/max(len(recorded),1)),
        'proteina':round(sum(day['proteina'] for day in recorded)/max(len(recorded),1),1),'dias_registrados':len(recorded)}}
