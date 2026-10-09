"""Shared SQL nutrition aggregates, independent from HTTP/auth imports."""
from typing import Annotated
from pydantic import BaseModel,Field
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,func,cast,Numeric
from db.models.health import Meal,MealItem,WaterLog,NutritionGoal
Nonnegative=Annotated[float,Field(ge=0,le=1000000000,allow_inf_nan=False)]
MACROS=('calories','protein','carbs','fat')


class GoalBody(BaseModel):
    daily_calories: int=Field(default=2000,gt=0,le=1000000000)
    daily_protein: Nonnegative=150
    daily_carbs: Nonnegative=250
    daily_fat: Nonnegative=65
    water_goal_ml: int=Field(default=2000,gt=0,le=1000000000)

def goal_json(row):
    if row is None:return {'goal_id':None,'configured':False,'confirmed_fields':[],'origin':'missing',**{key:None for key in GoalBody.model_fields}}
    return jsonable_encoder({'goal_id':row.id,'user_id':row.user_id,'created_at':row.created_at,'updated_at':row.updated_at,
        'configured':bool(row.confirmed_fields),'confirmed_fields':row.confirmed_fields or [],'origin':'configured' if row.confirmed_fields else 'legacy_unconfirmed',
        'stored_unconfirmed':{key:getattr(row,key) for key in GoalBody.model_fields if key not in (row.confirmed_fields or [])},
        **{key:getattr(row,key) if key in (row.confirmed_fields or []) else None for key in GoalBody.model_fields}})

async def period(session,uid,start,end):
    # Decimal casts before multiplication; round only for display, not per meal.
    expressions=[]
    for key in MACROS:
        value=func.coalesce(cast(getattr(Meal,'reported_'+key),Numeric),func.sum(cast(getattr(MealItem,key),Numeric)*cast(MealItem.quantity,Numeric)),0)
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
