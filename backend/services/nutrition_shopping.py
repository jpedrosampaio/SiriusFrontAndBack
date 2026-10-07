"""Shopping lists derived from owned plan and recipe ingredients."""
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.models.health import NutritionPlan,Recipe,ShoppingList,ShoppingItem
from db.session import unit_of_work
from db.activity import run_activity
from services.auth_routes import account

router=APIRouter(prefix='/nutrition')

class ShoppingBody(BaseModel):
    plan_id: UUID | None=None
    recipe_ids: list[UUID]=Field(default_factory=list,max_length=100)


def items_json(row):
    return [{'name':item.name,'quantity':item.quantity,'category':item.category,'checked':item.checked} for item in row.items]


def shopping_json(row):
    return jsonable_encoder({'list_id':row.id,'user_id':row.user_id,'plan_id':row.plan_id,'created_at':row.created_at,'items':items_json(row)})


@router.post('/shopping-list/generate')
async def generate(request: Request,body: ShoppingBody):
    user=await account(request)
    async def apply(session,owner):
        items={}
        def add(name,quantity,category):
            key=name.strip().casefold()
            if key in items:
                if quantity:items[key]['quantity']+=' + '+quantity
            else:items[key]={'name':name,'quantity':quantity,'category':category}
        if body.plan_id:
            plan=await session.scalar(select(NutritionPlan).options(selectinload(NutritionPlan.shopping_items)).where(
                NutritionPlan.user_id==owner.id,NutritionPlan.id==body.plan_id,NutritionPlan.archived_at.is_(None),NutritionPlan.kind!='diet'))
            if plan is None:raise HTTPException(404,'Plano não encontrado')
            for item in plan.shopping_items:add(item.name,item.quantity,item.category)
        if body.recipe_ids:
            ids=list(dict.fromkeys(body.recipe_ids))
            recipes=(await session.scalars(select(Recipe).options(selectinload(Recipe.ingredients)).where(Recipe.user_id==owner.id,Recipe.id.in_(ids)))).all()
            if len(recipes)!=len(ids):raise HTTPException(404,'Receita não encontrada')
            by_id={recipe.id:recipe for recipe in recipes}
            for identity in ids:
                for ingredient in by_id[identity].ingredients:add(ingredient.name,(ingredient.quantity+' '+ingredient.unit).strip(),'ingredientes')
        row=ShoppingList(user_id=owner.id,plan_id=body.plan_id)
        row.items=[ShoppingItem(user_id=owner.id,position=i,**item) for i,item in enumerate(items.values())]
        session.add(row);await session.flush()
        return {'success':True,'shopping_list':shopping_json(row)}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['shopping-list',body.model_dump(mode='json')],apply)


@router.get('/shopping-lists')
async def lists(request: Request):
    user=await account(request)
    async with unit_of_work() as session:
        rows=(await session.scalars(select(ShoppingList).options(selectinload(ShoppingList.items)).where(ShoppingList.user_id==UUID(user['user_id']))
            .order_by(ShoppingList.created_at.desc()).limit(10))).all()
        return [shopping_json(row) for row in rows]


@router.patch('/shopping-lists/{list_id}/toggle/{item_idx}')
async def toggle(request: Request,list_id: UUID,item_idx: int):
    user=await account(request)
    async def apply(session,owner):
        row=await session.scalar(select(ShoppingList).options(selectinload(ShoppingList.items)).where(ShoppingList.user_id==owner.id,ShoppingList.id==list_id))
        if row is None:raise HTTPException(404,'Lista não encontrada')
        if not 0<=item_idx<len(row.items):raise HTTPException(422,'Item inválido')
        row.items[item_idx].checked=not row.items[item_idx].checked
        return {'success':True,'items':items_json(row)}
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),['shopping-toggle',str(list_id),item_idx],apply)
