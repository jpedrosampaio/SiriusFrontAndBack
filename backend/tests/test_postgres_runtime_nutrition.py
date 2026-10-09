import os
import asyncio
import unittest
from datetime import timedelta
from unittest.mock import patch
from sqlalchemy import select,func
from db.models.health import Meal,MealItem,WaterLog,NutritionGoal
from db.session import unit_of_work
from services.time import local_today
import test_postgres_runtime_workout_logs as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeNutrition(unittest.IsolatedAsyncioTestCase):
    ok=setup.RuntimeWorkoutLogs.ok
    asyncTearDown=setup.RuntimeWorkoutLogs.asyncTearDown

    async def asyncSetUp(self):
        await setup.RuntimeWorkoutLogs.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        p=patch('services.nutrition.account',account);p.start();self.patches.append(p)
        self.today=local_today('America/Sao_Paulo')

    def meal(self,day=None):
        return {'name':'Lunch','meal_type':'lunch','date':(day or self.today).isoformat(),
            'foods':[{'name':'Rice','quantity':2.5,'calories':100.5,'protein':10,'carbs':20,'fat':1}]}

    async def test_meals_replay_ownership_totals_and_delete_cascade(self):
        values=[self.ok(r) for r in await asyncio.gather(*(self.http.post('/api/nutrition/meals',json=self.meal(),headers={'Idempotency-Key':'nutrition-meal-001'}) for _ in range(6)))]
        self.assertEqual(len({v['meal_id'] for v in values}),1)
        row=values[0];self.assertEqual(row['total_calories'],251.25);self.assertEqual(row['total_protein'],25)
        stats=self.ok(await self.http.get('/api/nutrition/stats'))
        self.assertEqual(stats['consumed']['calories'],251.25);self.assertEqual(stats['meals_count'],1)
        foreign={'Authorization':'Bearer bob'}
        self.assertEqual(self.ok(await self.http.get('/api/nutrition/meals',headers=foreign)),[])
        self.assertEqual((await self.http.delete('/api/nutrition/meals/'+row['meal_id'],headers=foreign)).status_code,404)
        self.ok(await self.http.delete('/api/nutrition/meals/'+row['meal_id']))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(MealItem).where(MealItem.user_id==self.uid)),0)
        with patch('services.nutrition.meal_json',side_effect=RuntimeError('after flush')):
            with self.assertRaises(RuntimeError):await self.http.post('/api/nutrition/meals',json=self.meal())
        self.assertEqual(self.ok(await self.http.get('/api/nutrition/meals')),[])

    async def test_goals_reads_never_create_defaults_and_explicit_update(self):
        stats=self.ok(await self.http.get('/api/nutrition/stats'));self.assertIsNone(stats['remaining']['water_ml'])
        self.assertEqual(stats['meals_count'],0)
        rows=[self.ok(r) for r in await asyncio.gather(*(self.http.get('/api/nutrition/goals') for _ in range(5)))]
        self.assertTrue(all(r['goal_id'] is None for r in rows))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(NutritionGoal).where(NutritionGoal.user_id==self.uid)),0)
        row=self.ok(await self.http.put('/api/nutrition/goals',json={'daily_calories':2400,'water_goal_ml':3000}))
        self.assertEqual(row['daily_calories'],2400)
        self.assertEqual((await self.http.put('/api/nutrition/goals',json={'water_goal_ml':0})).status_code,422)
        self.assertIsNone(self.ok(await self.http.get('/api/nutrition/goals',headers={'Authorization':'Bearer bob'}))['daily_calories'])
        trend=self.ok(await self.http.get('/api/nutrition/weekly-trend'));self.assertEqual(len(trend['daily']),7)
        self.assertEqual(trend['averages']['dias_registrados'],0)

    async def test_water_total_exceeds_page_limit_and_weekly_period(self):
        rows=[self.ok(r) for r in await asyncio.gather(*(self.http.post('/api/nutrition/water',params={'amount_ml':250},headers={'Idempotency-Key':'nutrition-water-001'}) for _ in range(5)))]
        self.assertEqual(len({r['log_id'] for r in rows}),1)
        async with unit_of_work() as session:
            session.add_all([WaterLog(user_id=self.uid,date=self.today,amount_ml=10) for _ in range(105)])
        data=self.ok(await self.http.get('/api/nutrition/water'));self.assertEqual(len(data['logs']),100);self.assertEqual(data['total_ml'],1300)
        self.assertEqual(self.ok(await self.http.get('/api/nutrition/water',headers={'Authorization':'Bearer bob'}))['total_ml'],0)
        self.assertEqual((await self.http.post('/api/nutrition/water',params={'amount_ml':-1})).status_code,422)
        for offset in (0,6,7,-1):self.ok(await self.http.post('/api/nutrition/meals',json=self.meal(self.today-timedelta(days=offset))))
        self.ok(await self.http.post('/api/nutrition/meals',json={**self.meal(),'foods':[]}))
        trend=self.ok(await self.http.get('/api/nutrition/weekly-trend'))
        self.assertEqual(trend['averages']['dias_registrados'],2);self.assertEqual(sum(d['calorias'] for d in trend['daily']),502)
        self.assertEqual(trend['daily'][-1]['refeicoes'],2);self.assertEqual(trend['daily'][-1]['agua_ml'],1300)
        self.assertEqual(trend['averages']['proteina'],25)
