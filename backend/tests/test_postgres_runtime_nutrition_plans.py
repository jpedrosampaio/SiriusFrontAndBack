import os
import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from sqlalchemy import select,func
from db.models.health import NutritionPlan,NutritionPlanDay,PlannedMeal,PlannedFood,Meal,MealItem,ShoppingList,ShoppingItem
from db.models.identity import User
from db.session import unit_of_work
import test_postgres_runtime_recipes as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeNutritionPlans(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeRecipes.ok
    asyncTearDown=setup.RuntimeRecipes.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeRecipes.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        async def authenticate(authorization=None,**kwargs):return SimpleNamespace(user_id=str(self.bob if authorization=='Bearer bob' else self.uid))
        self.plan_ai=AsyncMock(return_value=SimpleNamespace(text=json.dumps(self.generated())))
        extra=[patch('services.nutrition_plans.account',account),patch('services.nutrition_shopping.account',account),
            patch('services.nutrition_generation_routes.get_current_user',authenticate),
            patch('services.nutrition_generation_routes.get_user_api_key',AsyncMock(return_value='configured')),
            patch('services.nutrition_generation_routes.request_gemini',self.plan_ai)]
        for p in extra:p.start()
        self.patches.extend(extra)

    def planned_meal(self):
        return {'name':'Lunch','meal_type':'lunch','time':'12:00','total_calories':350,'protein':25,'carbs':40,'fat':10,
            'foods':[{'name':'Rice','quantity':'100g','calories':200},{'name':'Eggs','quantity':'2 units','calories':150}],
            'preparation':'Cook everything'}

    def generated(self):
        return {'name':'Weekly','calories_total':700,'macros':{'protein_g':50},
            'days':[{'day_name':str(i),'day_label':str(i),'calories':700,'meals':[self.planned_meal(),self.planned_meal()]} for i in range(7)],
            'shopping_list':[{'name':'Rice','quantity':'1 kg','category':'cereals'}],'tips':['Drink water']}

    async def generate(self):
        return self.ok(await self.http.post('/api/nutrition/meal-plan/generate',json={'duration':'semana','meals_per_day':2},headers={'Idempotency-Key':'meal-plan-week-001'}))

    async def test_weekly_plan_count_replay_validation_and_diet(self):
        row=await self.generate();again=await self.generate();pid=row['plan']['plan_id']
        self.assertEqual(again['plan']['plan_id'],pid);self.assertEqual(len(row['plan']['days']),7)
        async with unit_of_work() as session:
            for model,count in ((NutritionPlan,1),(NutritionPlanDay,7),(PlannedMeal,14),(PlannedFood,28)):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),count)
            self.assertEqual((await session.get(User,self.uid)).xp,5)
        self.plan_ai.return_value=SimpleNamespace(text=json.dumps({**self.generated(),'days':self.generated()['days'][:2]}))
        self.assertEqual((await self.http.post('/api/nutrition/meal-plan/generate',json={'duration':'semana','meals_per_day':2})).status_code,502)
        diet=self.ok(await self.http.post('/api/nutrition/diets',json={'name':'Diet','diet_type':'balanced','start_date':self.today.isoformat(),'meals_plan':[self.planned_meal()]}))
        self.assertEqual(len(diet['meals_plan']),1)
        self.assertEqual(len(self.ok(await self.http.get('/api/nutrition/diets'))),1)
        self.ok(await self.http.delete('/api/nutrition/diets/'+diet['diet_id']))
        self.assertEqual(self.ok(await self.http.get('/api/nutrition/diets')),[])

    async def test_shopping_uses_saved_recipes_ownership_toggle_and_archive(self):
        plan=(await self.generate())['plan']
        recipe=self.ok(await self.http.post('/api/nutrition/recipes/suggest',json={}))
        body={'plan_id':plan['plan_id'],'recipe_ids':[recipe['recipe_id']]}
        row=self.ok(await self.http.post('/api/nutrition/shopping-list/generate',json=body,headers={'Idempotency-Key':'shopping-list-001'}))['shopping_list']
        self.assertEqual(len(row['items']),1);self.assertIn('cups',row['items'][0]['quantity']);self.assertIn('1 kg',row['items'][0]['quantity'])
        foreign={'Authorization':'Bearer bob'}
        self.assertEqual((await self.http.post('/api/nutrition/shopping-list/generate',json=body,headers=foreign)).status_code,404)
        path='/api/nutrition/shopping-lists/'+row['list_id']+'/toggle/0'
        self.assertEqual((await self.http.patch(path,headers=foreign)).status_code,404)
        values=[self.ok(r) for r in await asyncio.gather(*(self.http.patch(path,headers={'Idempotency-Key':'shopping-toggle-001'}) for _ in range(5)))]
        self.assertTrue(all(r['items'][0]['checked'] for r in values))
        self.assertEqual((await self.http.patch(path[:-1]+'-1')).status_code,422)
        self.ok(await self.http.delete('/api/nutrition/meal-plans/'+plan['plan_id']))
        self.assertEqual(self.ok(await self.http.get('/api/nutrition/meal-plans')),[])
        self.assertEqual(len(self.ok(await self.http.get('/api/nutrition/shopping-lists'))),1)
        self.assertEqual((await self.http.post('/api/nutrition/shopping-list/generate',json=body)).status_code,404)

    async def test_import_updates_correct_goals_and_meal_totals_once_and_cleans_file(self):
        self.plan_ai.return_value=SimpleNamespace(text=json.dumps({'plan_name':'Imported','daily_calories':2200,'daily_protein':130,
            'meals':[self.planned_meal()]}))
        paths=[]
        async def upload(path,uid):paths.append(path);return SimpleNamespace(uri='test://file')
        with patch('services.study_material_routes._upload',upload),patch('services.study_material_routes._part',return_value={}):
            rows=[self.ok(await self.http.post('/api/nutrition/import-plan',files={'file':('plan.pdf',b'%PDF fake','application/pdf')},headers={'Idempotency-Key':'import-nutrition-001'})) for _ in range(2)]
        self.assertEqual(rows[0]['plan']['plan_id'],rows[1]['plan']['plan_id']);self.assertEqual(rows[0]['meals_created'],1)
        self.assertTrue(paths);self.assertTrue(all(not Path(path).exists() for path in paths))
        goals=self.ok(await self.http.get('/api/nutrition/goals'));self.assertEqual(goals['daily_calories'],2200);self.assertEqual(goals['daily_protein'],130)
        meals=self.ok(await self.http.get('/api/nutrition/meals'));self.assertEqual(len(meals),1);self.assertEqual(meals[0]['total_protein'],25)
        stats=self.ok(await self.http.get('/api/nutrition/stats'));self.assertEqual(stats['consumed']['calories'],350);self.assertEqual(stats['consumed']['protein'],25)
        async with unit_of_work() as session:self.assertEqual((await session.get(User,self.uid)).xp,10)

    async def test_import_failure_rolls_back_all_sql_and_xp(self):
        self.plan_ai.return_value=SimpleNamespace(text=json.dumps({'plan_name':'Imported','daily_calories':2200,'meals':[self.planned_meal()]}))
        with patch('services.study_material_routes.upload_part',AsyncMock(return_value={})),             patch('services.nutrition_generation_routes.upload_part',AsyncMock(return_value={})),             patch('services.nutrition_plans.plan_json',side_effect=RuntimeError('after flush')):
            with self.assertRaises(RuntimeError):await self.http.post('/api/nutrition/import-plan',files={'file':('plan.pdf',b'%PDF fake','application/pdf')})
        async with unit_of_work() as session:
            for model in (NutritionPlan,PlannedMeal,PlannedFood,Meal,MealItem):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)
        self.assertEqual(self.ok(await self.http.get('/api/nutrition/goals'))['daily_calories'],2000)
