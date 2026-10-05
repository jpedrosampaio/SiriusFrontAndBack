"""Normalized meals, hydration and nutrition targets; SQL period aggregates."""
from datetime import date as Date,timedelta
from typing import Annotated
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
Nonnegative=Annotated[float,Field(ge=0,allow_inf_nan=False)]
MACROS=('calories','protein','carbs','fat')

class Food(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    quantity: Nonnegative=1
    unit: str=Field(default='porcao',max_length=100)
    calories: Nonnegative=0
    protein: Nonnegative=0
    carbs: Nonnegative=0
    fat: Nonnegative=0

class MealBody(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    meal_type: str=Field(max_length=100)
    foods: list[Food]=Field(default_factory=list,max_length=300)
    date: Date
    notes: str | None=Field(default=None,max_length=20000)

class GoalBody(BaseModel):
    daily_calories: int=Field(default=2000,gt=0)
    daily_protein: Nonnegative=150
    daily_carbs: Nonnegative=250
    daily_fat: Nonnegative=65
    water_goal_ml: int=Field(default=2000,gt=0)


def goal_json(row):
    if row is None:return GoalBody().model_dump()
    return jsonable_encoder({'goal_id':row.id,'user_id':row.user_id,'created_at':row.created_at,'updated_at':row.updated_at,
        **{key:getattr(row,key) for key in GoalBody.model_fields}})


def meal_json(row):
    foods=[{key:getattr(item,key) for key in Food.model_fields} for item in row.items]
    totals={key:getattr(row,'reported_'+key) if getattr(row,'reported_'+key) is not None else sum(food[key]*food['quantity'] for food in foods) for key in MACROS}
    return jsonable_encoder({'meal_id':row.id,'user_id':row.user_id,'name':row.name,'meal_type':row.meal_type,
        'date':row.date,'notes':row.notes,'created_at':row.created_at,'foods':foods,
        **{'total_'+key:int(value) if key=='calories' else round(value,1) for key,value in totals.items()}})


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
    async def apply(session,owner):
        row=Meal(user_id=owner.id,**body.model_dump(exclude={'foods'}))
        row.items=[MealItem(user_id=owner.id,position=i,**food.model_dump()) for i,food in enumerate(body.foods)]
        session.add(row);await session.flush();return meal_json(row)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['meal',body.model_dump(mode='json')],apply)


@router.delete('/meals/{meal_id}')
async def delete_meal(request: Request,meal_id: UUID):
    user=await account(request)
    async with unit_of_work() as session:
        result=await session.execute(delete(Meal).where(Meal.user_id==UUID(user['user_id']),Meal.id==meal_id))
        if not result.rowcount:raise HTTPException(404,'Meal not found')
    return {'message':'Meal deleted'}


async def goals_write(request,body=None):
    user=await account(request)
    async def apply(session,owner):
        row=await session.scalar(select(NutritionGoal).where(NutritionGoal.user_id==owner.id))
        if row is None:
            row=NutritionGoal(user_id=owner.id,**(body or GoalBody()).model_dump());session.add(row)
        elif body:
            for key,value in body.model_dump().items():setattr(row,key,value)
        await session.flush();await session.refresh(row);return goal_json(row)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key') if body else None,
        ['nutrition-goals',body.model_dump() if body else None],apply)


@router.get('/goals')
async def goals(request: Request):return await goals_write(request)


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


async def period(session,uid,start,end):
    # Round per meal before summing, matching the existing meal response contract.
    expressions=[]
    for key in MACROS:
        value=func.coalesce(getattr(Meal,'reported_'+key),func.sum(getattr(MealItem,key)*MealItem.quantity),0)
        value=func.trunc(cast(value,Numeric)) if key=='calories' else func.round(cast(value,Numeric),1)
        expressions.append(value.label(key))
    per_meal=select(Meal.id,Meal.date,*expressions).outerjoin(MealItem,
        (MealItem.meal_id==Meal.id)&(MealItem.user_id==Meal.user_id)).where(Meal.user_id==uid,
        Meal.date>=start,Meal.date<=end).group_by(Meal.id,Meal.date).subquery()
    rows=(await session.execute(select(per_meal.c.date,func.count(),*[func.sum(per_meal.c[key]) for key in MACROS]).group_by(per_meal.c.date))).all()
    meals={day:{'meals_count':count,**{key:float(value) for key,value in zip(MACROS,values)}} for day,count,*values in rows}
    water=dict((await session.execute(select(WaterLog.date,func.sum(WaterLog.amount_ml)).where(
        WaterLog.user_id==uid,WaterLog.date>=start,WaterLog.date<=end).group_by(WaterLog.date))).all())
    goals=goal_json(await session.scalar(select(NutritionGoal).where(NutritionGoal.user_id==uid)))
    return meals,water,goals


@router.get('/stats')
async def stats(request: Request,date: Date | None=None):
    user=await account(request);day=date or local_today(user['timezone'])
    async with unit_of_work() as session:meals,water,goals=await period(session,UUID(user['user_id']),day,day)
    values=meals.get(day,{});consumed={key:round(values.get(key,0),1) for key in MACROS};consumed['water_ml']=water.get(day,0)
    remaining={key:round(goals['daily_'+key]-consumed[key],1) for key in MACROS};remaining['water_ml']=goals['water_goal_ml']-consumed['water_ml']
    return {'date':day.isoformat(),'consumed':consumed,'goals':goals,'meals_count':values.get('meals_count',0),'remaining':remaining}


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
