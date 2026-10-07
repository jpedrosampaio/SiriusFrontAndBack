"""Saved recipes with normalized ingredients and owner-scoped SQL access."""
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field,ValidationError,field_validator
from sqlalchemy import select,delete
from sqlalchemy.orm import selectinload
from db.models.health import Recipe,RecipeIngredient,NutritionGoal
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account
from services.nutrition import Nonnegative,goal_json

router=APIRouter(prefix='/nutrition/recipes')

class IngredientBody(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    quantity: str=Field(default='',max_length=300)
    unit: str=Field(default='',max_length=100)
    @field_validator('quantity',mode='before')
    @classmethod
    def quantity_text(cls,value):return str(value) if isinstance(value,(int,float)) else value

class RecipeBody(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    description: str=Field(default='',max_length=20000)
    ingredients: list[IngredientBody]=Field(min_length=1,max_length=300)
    instructions: list[str]=Field(min_length=1,max_length=300)
    prep_time_minutes: int=Field(default=0,ge=0)
    cook_time_minutes: int=Field(default=0,ge=0)
    servings: int=Field(default=1,gt=0)
    calories_per_serving: Nonnegative=0
    protein_per_serving: Nonnegative=0
    carbs_per_serving: Nonnegative=0
    fat_per_serving: Nonnegative=0
    tags: list[str]=Field(default_factory=list,max_length=100)
    tips: str=Field(default='',max_length=20000)


def recipe_json(row):
    values={key:getattr(row,key) for key in RecipeBody.model_fields if key!='ingredients'}
    values['ingredients']=[{key:getattr(item,key) for key in IngredientBody.model_fields} for item in row.ingredients]
    return jsonable_encoder({'recipe_id':row.id,'user_id':row.user_id,'created_at':row.created_at,'ai_generated':row.ai_generated,**values})


async def nutrition_goals(uid):
    async with unit_of_work() as session:
        return goal_json(await session.scalar(select(NutritionGoal).where(NutritionGoal.user_id==UUID(uid))))


async def save_recipe(uid,data,key,preferences):
    try:body=RecipeBody.model_validate(data)
    except ValidationError:raise HTTPException(502,'A IA retornou uma receita inválida. Tente novamente.')
    async def apply(session,owner):
        row=Recipe(user_id=owner.id,**body.model_dump(exclude={'ingredients'}))
        row.ingredients=[RecipeIngredient(user_id=owner.id,position=i,**item.model_dump()) for i,item in enumerate(body.ingredients)]
        session.add(row);await session.flush();return recipe_json(row)
    return await run_activity(UUID(uid),key,['recipe-suggestion',preferences],apply)


@router.get('')
async def recipes(request: Request):
    user=await account(request)
    async with unit_of_work() as session:
        rows=(await session.scalars(select(Recipe).options(selectinload(Recipe.ingredients)).where(Recipe.user_id==UUID(user['user_id']))
            .order_by(Recipe.created_at.desc()).limit(100))).all()
        return [recipe_json(row) for row in rows]


@router.get('/{recipe_id}')
async def detail(request: Request,recipe_id: UUID):
    user=await account(request)
    async with unit_of_work() as session:
        row=await session.scalar(select(Recipe).options(selectinload(Recipe.ingredients)).where(Recipe.user_id==UUID(user['user_id']),Recipe.id==recipe_id))
        if row is None:raise HTTPException(404,'Recipe not found')
        return recipe_json(row)


@router.delete('/{recipe_id}')
async def remove(request: Request,recipe_id: UUID):
    user=await account(request)
    async with unit_of_work() as session:
        result=await session.execute(delete(Recipe).where(Recipe.user_id==UUID(user['user_id']),Recipe.id==recipe_id))
        if not result.rowcount:raise HTTPException(404,'Recipe not found')
    return {'message':'Recipe deleted'}
