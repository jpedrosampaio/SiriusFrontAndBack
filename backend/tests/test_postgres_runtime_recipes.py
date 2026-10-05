import os
import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.models.health import Recipe,RecipeIngredient
from db.session import unit_of_work
import test_postgres_runtime_nutrition as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeRecipes(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeNutrition.ok
    asyncTearDown=setup.RuntimeNutrition.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeNutrition.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        async def authenticate(authorization=None,**kwargs):return SimpleNamespace(user_id=str(self.bob if authorization=='Bearer bob' else self.uid))
        self.data={'name':'Rice','description':'Lunch','ingredients':[{'name':'Rice','quantity':'2','unit':'cups'}],
            'instructions':['Cook'],'servings':2,'calories_per_serving':300,'tips':'Wash first'}
        self.ai=AsyncMock(return_value=SimpleNamespace(text=json.dumps(self.data)))
        extra=[patch('services.recipe_routes.account',account),patch('services.recipe_generation_routes.get_current_user',authenticate),
            patch('services.recipe_generation_routes.get_user_api_key',AsyncMock(return_value='configured')),
            patch('services.recipe_generation_routes.request_gemini',self.ai)]
        for p in extra:p.start()
        self.patches.extend(extra)

    async def test_generation_replay_persists_tips_and_owner_scoped_children(self):
        self.ok(await self.http.put('/api/nutrition/goals',json={'daily_calories':2400}))
        rows=[self.ok(r) for r in await asyncio.gather(*(self.http.post('/api/nutrition/recipes/suggest',json={},headers={'Idempotency-Key':'recipe-generate-001'}) for _ in range(5)))]
        self.assertEqual(len({r['recipe_id'] for r in rows}),1)
        self.assertIn('2400',self.ai.call_args.kwargs['contents'])
        path='/api/nutrition/recipes/'+rows[0]['recipe_id']
        saved=self.ok(await self.http.get(path));self.assertEqual(saved['tips'],'Wash first');self.assertEqual(saved['ingredients'][0]['unit'],'cups')
        foreign={'Authorization':'Bearer bob'}
        self.assertEqual(self.ok(await self.http.get('/api/nutrition/recipes',headers=foreign)),[])
        self.assertEqual((await self.http.get(path,headers=foreign)).status_code,404)
        self.assertEqual((await self.http.delete(path,headers=foreign)).status_code,404)
        self.ok(await self.http.delete(path))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(RecipeIngredient).where(RecipeIngredient.user_id==self.uid)),0)

    async def test_invalid_ai_and_failed_save_leave_no_recipe(self):
        for change in ({'servings':0},{'ingredients':[]},{'calories_per_serving':float('nan')}):
            self.ai.return_value=SimpleNamespace(text=json.dumps({**self.data,**change}))
            self.assertEqual((await self.http.post('/api/nutrition/recipes/suggest',json={})).status_code,502)
        self.ai.return_value=SimpleNamespace(text=json.dumps(self.data))
        with patch('services.recipe_routes.recipe_json',side_effect=RuntimeError('after flush')):
            self.assertEqual((await self.http.post('/api/nutrition/recipes/suggest',json={})).status_code,500)
        self.assertEqual(self.ok(await self.http.get('/api/nutrition/recipes')),[])
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(RecipeIngredient).where(RecipeIngredient.user_id==self.uid)),0)
