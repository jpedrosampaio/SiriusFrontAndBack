"""Owned, normalized nutrition plans with atomic import and XP."""
from datetime import datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.models.health import NutritionPlan,NutritionPlanDay,PlannedMeal,PlannedFood,PlanShoppingItem,Meal,MealItem,NutritionGoal
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.nutrition_plan_dto import PlanBody,DietBody,PlannedMealBody,PlannedFoodBody,ShoppingEntry
from services.nutrition import MACROS
from services.planning import apply_xp
from services.time import local_today

router=APIRouter(prefix='/nutrition')


def plan_options():
    return (selectinload(NutritionPlan.days).selectinload(NutritionPlanDay.meals).selectinload(PlannedMeal.foods),selectinload(NutritionPlan.shopping_items))


def meal_json(row):
    values={key:getattr(row,key) for key in PlannedMealBody.model_fields if key!='foods'}
    values['total_calories']=row.calories
    values['foods']=[{key:getattr(food,key) for key in PlannedFoodBody.model_fields} for food in row.foods]
    return values


def plan_json(row):
    days=[{'day_name':day.day_name,'day_label':day.day_label,'calories':day.calories,'meals':[meal_json(m) for m in day.meals]} for day in row.days]
    base={'user_id':row.user_id,'name':row.name,'description':row.description,'created_at':row.created_at}
    if row.kind=='diet':
        return jsonable_encoder({**base,'diet_id':row.id,'diet_type':row.diet_type,'active':row.active,'start_date':row.start_date,'end_date':row.end_date,
            'meals_plan':[meal for day in days for meal in day['meals']]})
    return jsonable_encoder({**base,'plan_id':row.id,'type':'meal_plan','objective':row.objective,'goal':row.objective,
        'source':row.kind,'source_filename':row.source_filename,'restrictions':row.restrictions,'tips':row.tips,
        'daily_calories':row.daily_calories,'daily_protein':row.daily_protein,'daily_carbs':row.daily_carbs,'daily_fat':row.daily_fat,
        'calories_total':row.daily_calories,'macros':{'protein_g':row.daily_protein,'carbs_g':row.daily_carbs,'fat_g':row.daily_fat,'fiber_g':row.daily_fiber},
        'days':days,'meals':[meal for day in days for meal in day['meals']],
        'shopping_list':[{key:getattr(item,key) for key in ShoppingEntry.model_fields} for item in row.shopping_items]})


async def save_plan(uid,body,kind,key,fingerprint):
    async def apply(session,owner):
        row=NutritionPlan(user_id=owner.id,kind=kind,**body.model_dump(exclude={'days','shopping_items'}))
        row.days=[]
        for position,day in enumerate(body.days):
            day_row=NutritionPlanDay(user_id=owner.id,position=position,**day.model_dump(exclude={'meals'}));day_row.meals=[]
            for index,meal in enumerate(day.meals):
                meal_row=PlannedMeal(user_id=owner.id,position=index,**meal.model_dump(exclude={'foods'}))
                meal_row.foods=[PlannedFood(user_id=owner.id,position=i,**food.model_dump()) for i,food in enumerate(meal.foods)]
                day_row.meals.append(meal_row)
            row.days.append(day_row)
        row.shopping_items=[PlanShoppingItem(user_id=owner.id,position=i,**item.model_dump()) for i,item in enumerate(body.shopping_items)]
        session.add(row)
        created=0
        if kind=='imported':
            for day in body.days:
                for meal in day.meals:
                    recorded=Meal(user_id=owner.id,name=meal.name,meal_type=meal.meal_type,date=local_today(owner.timezone),notes=meal.notes,
                        **{'reported_'+key:getattr(meal,key) for key in MACROS})
                    # Imported macros describe the stated portion (e.g. 3 eggs), not a per-unit multiplier.
                    recorded.items=[MealItem(user_id=owner.id,position=i,name=f.name,quantity=1,unit=(f.quantity+' '+f.unit).strip(),
                        **{key:getattr(f,key) for key in MACROS}) for i,f in enumerate(meal.foods)]
                    session.add(recorded);created+=1
            if body.daily_calories>0:
                goals=await session.scalar(select(NutritionGoal).where(NutritionGoal.user_id==owner.id))
                if goals is None:goals=NutritionGoal(user_id=owner.id);session.add(goals)
                goals.daily_calories=round(body.daily_calories)
                for key in ('protein','carbs','fat'):setattr(goals,'daily_'+key,getattr(body,'daily_'+key))
        xp=10 if kind=='imported' else 5 if kind=='generated' else 0
        apply_xp(owner,xp);await session.flush()
        if kind=='diet':return plan_json(row)
        result={'success':True,'plan':plan_json(row),'xp_earned':xp}
        if kind=='imported':result.update(meals_created=created,goals_updated=body.daily_calories>0)
        return result
    return await run_activity(UUID(uid),key,fingerprint,apply)


def validate_ai_plan(data,kind,options,filename=None):
    try:
        if not isinstance(data,dict):raise ValueError('Plan must be an object')
        if kind=='generated':
            macros=data.get('macros',{})
            body=PlanBody.model_validate({'name':data.get('name'),'description':data.get('description'),'objective':options.get('objective','saude'),
                'restrictions':options.get('restrictions',[]),'tips':data.get('tips',[]),'days':data.get('days',[]),
                'daily_calories':data.get('calories_total',0),'daily_protein':macros.get('protein_g',0),'daily_carbs':macros.get('carbs_g',0),
                'daily_fat':macros.get('fat_g',0),'daily_fiber':macros.get('fiber_g',0),'shopping_items':data.get('shopping_list',[])})
            expected=1 if options.get('duration','dia')=='dia' else 7
            if len(body.days)!=expected or any(len(day.meals)!=options.get('meals_per_day',5) for day in body.days):raise ValueError('Incomplete plan')
        else:
            body=PlanBody.model_validate({'name':data.get('plan_name','Plano Importado'),'objective':data.get('goal',''),'source_filename':filename,
                'restrictions':data.get('restrictions',[]),'tips':data.get('tips',[]),
                **{'daily_'+key:data.get('daily_'+key,0) for key in MACROS},
                'days':[{'meals':data.get('meals',[])}]})
        return body
    except (ValidationError,ValueError,TypeError,AttributeError):raise HTTPException(502,'Plano alimentar incompleto ou inválido retornado pela IA.')


async def list_plans(request,kind):
    user=await account(request)
    async with unit_of_work() as session:
        kinds=['diet'] if kind=='diet' else ['generated','imported']
        rows=(await session.scalars(select(NutritionPlan).options(*plan_options()).where(NutritionPlan.user_id==UUID(user['user_id']),
            NutritionPlan.kind.in_(kinds),NutritionPlan.archived_at.is_(None)).order_by(NutritionPlan.created_at.desc()).limit(100 if kind=='diet' else 20))).all()
        return [plan_json(row) for row in rows]


@router.get('/diets')
async def diets(request: Request):return await list_plans(request,'diet')


@router.get('/meal-plans')
async def plans(request: Request):return await list_plans(request,'plan')


@router.post('/diets')
async def create_diet(request: Request,body: DietBody):
    user=await account(request)
    data=PlanBody(**body.model_dump(exclude={'meals_plan'}),days=[{'meals':body.meals_plan}] if body.meals_plan else [])
    return await save_plan(user['user_id'],data,'diet',request.headers.get('Idempotency-Key'),['diet',body.model_dump(mode='json')])


async def archive(request,identity,kind):
    user=await account(request)
    async with unit_of_work() as session:
        kinds=['diet'] if kind=='diet' else ['generated','imported']
        row=await session.scalar(select(NutritionPlan).where(NutritionPlan.user_id==UUID(user['user_id']),NutritionPlan.id==identity,
            NutritionPlan.kind.in_(kinds),NutritionPlan.archived_at.is_(None)).with_for_update())
        if row is None:raise HTTPException(404,'Plano não encontrado')
        row.archived_at=datetime.now(timezone.utc)
    return {'message':'Diet deleted'} if kind=='diet' else {'success':True}


@router.delete('/diets/{diet_id}')
async def remove_diet(request: Request,diet_id: UUID):return await archive(request,diet_id,'diet')


@router.delete('/meal-plans/{plan_id}')
async def remove_plan(request: Request,plan_id: UUID):return await archive(request,plan_id,'plan')
