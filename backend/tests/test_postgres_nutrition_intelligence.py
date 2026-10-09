import os
import asyncio
import unittest
from uuid import UUID,uuid4
from datetime import timedelta,datetime,time
from zoneinfo import ZoneInfo
from unittest.mock import patch
from sqlalchemy import select,func
from db.models.health import Meal,MealItem,NutritionGoal,NutritionPlan,Recipe,RecipeIngredient,WorkoutLog
from db.models.planning import CalendarEvent
from db.models.finance import Budget,FinancialTransaction
from decimal import Decimal
from db.models.identity import User,ActivityReceipt
from db.session import unit_of_work
from services.time import local_today
from ai.core import Core
import test_postgres_runtime_nutrition as fixtures


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class NutritionIntelligence(unittest.IsolatedAsyncioTestCase):
    ok=fixtures.RuntimeNutrition.ok
    asyncTearDown=fixtures.RuntimeNutrition.asyncTearDown

    async def asyncSetUp(self):
        await fixtures.RuntimeNutrition.asyncSetUp(self)
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        p=patch('services.nutrition_intelligence_routes.account',account);p.start();self.patches.append(p)

    async def add(self,**changes):
        return self.ok(await self.http.post('/api/nutrition/meals',json={'name':'Lunch','meal_type':'lunch','date':str(self.today),
            'foods':[{'name':'Arroz','unit':'porcao','quantity':1,'calories':100,'protein':2,'carbs':20,'fat':0,'estimated':True}],**changes}))

    async def state(self,**kwargs):return self.ok(await self.http.get('/api/nutrition/intelligence/state',**kwargs))

    async def preview(self,body):
        from services.nutrition_plan_dto import PlanBody
        from services.nutrition_previews import create_preview
        result=await create_preview(str(self.uid),PlanBody.model_validate(body),uuid4().hex+uuid4().hex)
        return {'preview_id':result['preview_id'],'plan':result['preview']}

    async def counts(self):
        async with unit_of_work() as session:
            return [await session.scalar(select(func.count()).select_from(m).where(m.user_id==self.uid)) for m in (Meal,MealItem,NutritionGoal)] + [(await session.get(User,self.uid)).xp]

    async def test_state_readonly_provenance_targets_ownership_and_agent(self):
        await self.add();before=await self.counts();data=await self.state()
        self.assertIsNone(data['goals']);self.assertIsNone(data['remaining']['calories'])
        self.assertEqual(data['consumed']['calories']['estimated'],'100.000')
        self.assertEqual(data['consumed']['fat']['total'],'0.000')
        self.assertEqual((await self.state(headers={'Authorization':'Bearer bob'}))['meals'],[])
        facts=await Core().read('get_nutrition_state',str(self.uid));self.assertEqual(facts['consumed'],data['consumed'])
        self.assertEqual(await self.counts(),before)
        self.ok(await self.http.put('/api/nutrition/goals',json={'daily_calories':200}))
        data=await self.state();self.assertEqual(data['remaining']['calories'],'100.000');self.assertIsNone(data['remaining']['protein'])

    async def test_unknown_fields_and_historical_provenance_are_preserved(self):
        await self.add(foods=[{'name':'Unknown','quantity':1}])
        self.assertIsNone((await self.state())['consumed']['calories']['total'])
        async with unit_of_work() as session:
            row=await session.scalar(select(MealItem).where(MealItem.user_id==self.uid));row.nutrition_evidence=None;row.calories=88
            session.add(NutritionGoal(user_id=self.uid,daily_calories=2300))
        data=await self.state();self.assertEqual(data['consumed']['calories']['legacy_unverified'],'88.000')
        self.assertIsNone(data['remaining']['calories']);self.assertEqual(data['goals']['origin'],'legacy_unconfirmed')
        self.assertEqual(data['goals']['stored_unconfirmed']['daily_calories'],2300)

    async def test_repeat_concurrency_replay_and_favorite_deletion(self):
        original=await self.add();mid=original['meal_id']
        prefs={'favorite_meals':[mid],'budget':'20'}
        self.ok(await self.http.put('/api/nutrition/intelligence/preferences',json=prefs))
        body={'date':str(self.today),'portions':'1.5'};path=f'/api/nutrition/intelligence/templates/meal/{mid}/record'
        results=await asyncio.gather(*(self.http.post(path,json=body,headers={'Idempotency-Key':'repeat-once'}) for _ in range(5)))
        self.assertEqual(len({self.ok(r)['meal_id'] for r in results}),1)
        self.assertEqual((await self.counts())[0],2)
        self.assertEqual((await self.state())['consumed']['calories']['total'],'250.000')
        self.assertEqual((await self.http.post(path,json=body,headers={'Authorization':'Bearer bob','Idempotency-Key':'foreign-repeat'})).status_code,404)
        self.ok(await self.http.delete('/api/nutrition/meals/'+mid))
        self.assertEqual((await self.state())['preferences']['favorite_meals'],[])
        self.assertEqual((await self.counts())[0],1)

    async def test_previews_budget_unknowns_and_user_preferences_namespace(self):
        original=await self.add()
        async with unit_of_work() as session:(await session.get(User,self.uid)).preferences={'unrelated':'preserved'}
        body={'available_foods':['Arroz'],'budget':'10','prices':[{'food':'Arroz','unit':'porcao','amount':'2.10','source':'estimated'}]}
        self.ok(await self.http.put('/api/nutrition/intelligence/preferences',json=body))
        before=await self.counts()
        data=self.ok(await self.http.post('/api/nutrition/intelligence/alternatives',json={'days':7,'within_budget':True,'available_only':True}))
        self.assertEqual(len(data['organization']),4);self.assertFalse(data['automatic']);self.assertEqual(data['candidates'][0]['cost_source'],'estimated')
        self.assertEqual(await self.counts(),before)
        async with unit_of_work() as session:self.assertEqual((await session.get(User,self.uid)).preferences['unrelated'],'preserved')
        foreign={'favorite_meals':[original['meal_id']]}
        self.assertEqual((await self.http.put('/api/nutrition/intelligence/preferences',json=foreign,headers={'Authorization':'Bearer bob'})).status_code,404)

    async def test_confirm_plan_does_not_record_consumption_or_configure_goals(self):
        body=await self.preview({'name':'Reviewed','daily_calories':2200,'days':[{'meals':[{'name':'Arroz','meal_type':'lunch','foods':[{'name':'Arroz','quantity':'100','unit':'g','calories':100,'protein':2,'carbs':20,'fat':0}]}]}]})
        results=[self.ok(await self.http.post('/api/nutrition/intelligence/confirm-plan',json=body,headers={'Idempotency-Key':'review-once'})) for _ in range(2)]
        self.assertEqual(results[0]['plan']['plan_id'],results[1]['plan']['plan_id'])
        self.assertEqual((await self.counts())[:3],[0,0,0])
        options=self.ok(await self.http.post('/api/nutrition/intelligence/alternatives',json={}))
        candidate=options['candidates'][0];self.assertEqual(candidate['template_kind'],'planned')
        response=self.ok(await self.http.post('/api/nutrition/intelligence/templates/planned/'+candidate['template_id']+'/record',json={'date':str(self.today)},headers={'Idempotency-Key':'eat-plan'}))
        self.assertEqual(response['foods'][0]['quantity'],1)
        state=await self.state();self.assertEqual(state['consumed']['calories']['estimated'],'100.000')
        self.assertEqual(state['consumed']['fat']['total'],'0.000')
        self.assertEqual(state['planned'][0]['status'],'recorded')

    async def test_same_key_different_provenance_is_conflict(self):
        payload={'name':'Meal','meal_type':'lunch','date':str(self.today),'foods':[{'name':'A'}]}
        self.ok(await self.http.post('/api/nutrition/meals',json=payload,headers={'Idempotency-Key':'macro-source'}))
        payload['foods'][0]['protein']=0
        self.assertEqual((await self.http.post('/api/nutrition/meals',json=payload,headers={'Idempotency-Key':'macro-source'})).status_code,409)

    async def test_invalid_scenarios_price_duplicates_and_absent_idempotency(self):
        original=await self.add()
        self.assertEqual((await self.http.post('/api/nutrition/intelligence/templates/'+original['meal_id']+'/record',json={'date':str(self.today)})).status_code,400)
        self.assertEqual((await self.http.post('/api/nutrition/intelligence/alternatives',json={'days':True})).status_code,422)
        duplicate={'prices':[{'food':'Arroz branco','unit':'porcao','amount':'2','source':'known'},{'food':'arroz  branco','unit':'porcao','amount':'3','source':'known'}]}
        self.assertEqual((await self.http.put('/api/nutrition/intelligence/preferences',json=duplicate)).status_code,422)

    async def test_finance_budget_is_owned_month_bound_and_readonly(self):
        await self.add()
        async with unit_of_work() as session:
            budget=Budget(user_id=self.uid,category='food',month=self.today.replace(day=1),limit=Decimal('10'))
            expense=FinancialTransaction(user_id=self.uid,type='expense',category='food',date=self.today,amount=Decimal('3'))
            session.add_all([budget,expense]);await session.flush();bid=str(budget.id)
        self.ok(await self.http.put('/api/nutrition/intelligence/preferences',json={'prices':[{'food':'Arroz','unit':'porcao','amount':'2','source':'known'}]}))
        before=await self.counts()
        data=self.ok(await self.http.post('/api/nutrition/intelligence/alternatives',json={'finance_budget_id':bid,'within_budget':True}))
        self.assertEqual(Decimal(data['budget']['amount']),Decimal('7'))
        self.assertEqual(data['budget']['source'],'FinanceEngine')
        self.assertEqual((await self.http.post('/api/nutrition/intelligence/alternatives',json={'finance_budget_id':bid},headers={'Authorization':'Bearer bob'})).status_code,404)
        next_month=(self.today.replace(day=28)+timedelta(days=4)).replace(day=1)
        self.assertEqual((await self.http.post('/api/nutrition/intelligence/alternatives',json={'finance_budget_id':bid,'date':str(next_month)})).status_code,409)
        self.assertEqual(await self.counts(),before)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.user_id==self.uid)),1)

    async def test_recipe_ownership_exclusions_and_confirmed_meal_type(self):
        async with unit_of_work() as session:
            recipe=Recipe(user_id=self.uid,name='Own recipe',calories_per_serving=250,protein_per_serving=12)
            session.add(recipe);await session.flush();rid=str(recipe.id)
            session.add(RecipeIngredient(user_id=self.uid,recipe_id=recipe.id,position=0,name='Amendoim',quantity='20',unit='g'))
        self.ok(await self.http.put('/api/nutrition/intelligence/preferences',json={'excluded_foods':['amendoim']}))
        self.assertEqual(self.ok(await self.http.post('/api/nutrition/intelligence/alternatives',json={}))['candidates'],[])
        self.ok(await self.http.put('/api/nutrition/intelligence/preferences',json={}))
        candidate=self.ok(await self.http.post('/api/nutrition/intelligence/alternatives',json={}))['candidates'][0]
        self.assertIsNone(candidate['meal_type']);self.assertIsNone(candidate['macros']['fat']['total'])
        path='/api/nutrition/intelligence/templates/recipe/'+rid+'/record'
        body={'date':str(self.today)};headers={'Idempotency-Key':'recipe-once'}
        self.assertEqual((await self.http.post(path,json=body,headers=headers)).status_code,422)
        body['meal_type']='snack'
        self.assertEqual((await self.http.post(path,json=body,headers={**headers,'Authorization':'Bearer bob'})).status_code,404)
        rows=[self.ok(await self.http.post(path,json=body,headers=headers)) for _ in range(2)]
        self.assertEqual(rows[0]['meal_id'],rows[1]['meal_id'])
        self.assertEqual((await self.state())['consumed']['calories']['estimated'],'250.000')
        self.assertEqual((await self.counts())[0],1)

    async def test_routine_training_and_dated_plan_are_context_without_mutations(self):
        start=datetime.combine(self.today,time(12),ZoneInfo('America/Sao_Paulo'))
        async with unit_of_work() as session:
            event=CalendarEvent(user_id=self.uid,title='Fixed appointment',start_at=start,end_at=start+timedelta(hours=1))
            session.add_all([event,WorkoutLog(user_id=self.uid,name='Recorded workout',activity_type='strength',duration_minutes=40,date=self.today),
                CalendarEvent(user_id=self.bob,title='Foreign appointment',start_at=start,end_at=start+timedelta(hours=1))])
            await session.flush();eid=event.id
        plan={'name':'Dated plan','start_date':str(self.today),'days':[{'meals':[{'name':'Own lunch','meal_type':'lunch','foods':[{'name':'Arroz','quantity':'100','unit':'g','calories':100}]}]}]}
        self.ok(await self.http.post('/api/nutrition/intelligence/confirm-plan',json=await self.preview(plan),headers={'Idempotency-Key':'dated-plan'}))
        before=await self.counts();data=await self.state()
        self.assertEqual([e['title'] for e in data['routine_context']],['Fixed appointment'])
        self.assertTrue(data['routine_context'][0]['fixed']);self.assertEqual(data['training_context'][0]['recorded_minutes'],40)
        self.assertNotIn('expenditure',data);self.assertIsNone(data['goals'])
        from services.life_adapters import nutrition
        async with unit_of_work() as session:
            projection=await nutrition(session,self.uid,self.today,'America/Sao_Paulo')
            self.assertEqual(len(projection.candidates),1)
            event=await session.get(CalendarEvent,eid);self.assertEqual(event.start_at,start)
        self.assertEqual(await self.counts(),before)

    async def test_preview_receipt_ownership_structure_expiry_and_one_reward(self):
        raw={'name':'Preview','days':[{'meals':[{'name':'Food','foods':[{'name':'Arroz','calories':100,'fat':0}]}]}]}
        path='/api/nutrition/intelligence/confirm-plan';body=await self.preview(raw)
        self.assertEqual((await self.http.post(path,json=raw,headers={'Idempotency-Key':'unbound-body'})).status_code,422)
        self.assertEqual((await self.http.post(path,json=body,headers={'Authorization':'Bearer bob','Idempotency-Key':'foreign-preview'})).status_code,404)
        results=await asyncio.gather(*(self.http.post(path,json=body,headers={'Idempotency-Key':f'confirm-preview-{i}'}) for i in range(5)))
        self.assertEqual(len({self.ok(r)['plan']['plan_id'] for r in results}),1)
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User,self.uid)).xp,10)
            self.assertEqual(await session.scalar(select(func.count()).select_from(NutritionPlan).where(NutritionPlan.user_id==self.uid)),1)
        body['plan']['name']='Changed after confirmation'
        self.assertEqual((await self.http.post(path,json=body,headers={'Idempotency-Key':'changed-preview'})).status_code,409)
        fresh=await self.preview(raw)
        fresh['plan']['days'][0]['meals'][0]['foods'].append({'name':'Injected food'})
        self.assertEqual((await self.http.post(path,json=fresh,headers={'Idempotency-Key':'injected-preview'})).status_code,409)
        expired=await self.preview(raw)
        async with unit_of_work() as session:
            receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==self.uid,ActivityReceipt.request_key==expired['preview_id']))
            receipt.result={**receipt.result,'expires_at':'2020-01-01T00:00:00+00:00'}
        self.assertEqual((await self.http.post(path,json=expired,headers={'Idempotency-Key':'expired-preview'})).status_code,409)
        retry=await self.preview(raw)
        with patch('services.nutrition_plans.plan_json',side_effect=RuntimeError('after plan flush')):
            with self.assertRaises(RuntimeError):
                await self.http.post(path,json=retry,headers={'Idempotency-Key':'rollback-preview'})
        async with unit_of_work() as session:
            receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==self.uid,ActivityReceipt.request_key==retry['preview_id']))
            self.assertNotIn('consumed_digest',receipt.result)
            self.assertEqual((await session.get(User,self.uid)).xp,10)
        self.ok(await self.http.post(path,json=retry,headers={'Idempotency-Key':'rollback-preview'}))

    async def test_expired_upload_renewal_and_full_digest_collision_guard(self):
        from services.nutrition_plan_dto import PlanBody
        from services.nutrition_previews import create_preview,existing_preview
        raw=PlanBody.model_validate({'name':'Upload','days':[{'meals':[{'name':'Food','foods':[{'name':'Arroz','calories':100}]}]}]})
        upload_digest='a'*64
        preview=await create_preview(str(self.uid),raw,upload_digest)
        async with unit_of_work() as session:
            receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==self.uid,ActivityReceipt.request_key==preview['preview_id']))
            receipt.result={**receipt.result,'expires_at':'2020-01-01T00:00:00+00:00'}
        self.assertIsNone(await existing_preview(str(self.uid),upload_digest))
        renewed=await create_preview(str(self.uid),raw,upload_digest)
        self.assertEqual(renewed['preview_id'],preview['preview_id']);self.assertNotEqual(renewed['expires_at'],'2020-01-01T00:00:00+00:00')
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:await create_preview(str(self.uid),raw,'a'*32+'b'*32)
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual((await self.counts())[:3],[0,0,0])
