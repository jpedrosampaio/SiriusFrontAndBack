import sys
import unittest
from pathlib import Path
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.nutrition_evidence import project
from services.nutrition_intelligence import build_alternatives
from nutrition_contracts import NutritionPreferences, MealScenario
from ai.registry import validate_call


def food(**changes):
    return {'name':'Arroz','unit':'porcao','quantity':1,'calories':100,'protein':2,'carbs':20,'fat':0,
        'nutrition_evidence':{'source':'registered','known_macros':['calories','protein','carbs','fat']},**changes}


class NutritionRegression(unittest.TestCase):
    def test_exact_decimal_units_and_registered_zero(self):
        values=project([food(quantity='0.33',calories='10.1'),food(quantity='0.1',calories='0.1')])
        self.assertEqual(values['calories']['total'],'3.343')
        self.assertEqual(values['fat']['total'],'0.000')
        self.assertEqual(values['calories']['unit'],'kcal');self.assertEqual(values['protein']['unit'],'g')

    def test_unknown_and_legacy_are_not_registered_zero(self):
        legacy=food(nutrition_evidence=None)
        missing=food(nutrition_evidence={'source':'estimated','known_macros':['calories']})
        result=project([legacy,missing])
        self.assertIsNone(result['calories']['total']);self.assertEqual(result['calories']['estimated'],'100.000')
        self.assertEqual(result['calories']['legacy_unverified'],'100.000')
        self.assertEqual(result['protein']['unknown_items'],2)

    def test_empty_day_has_recorded_zero_without_creating_targets(self):
        self.assertEqual(project([])['calories']['total'],'0.000')

    def test_large_legacy_values_and_nonfinite_composition_remain_unknown(self):
        legacy=project([food(quantity='1e30',nutrition_evidence=None)])
        self.assertIsNone(legacy['calories']['total'])
        self.assertEqual(Decimal(legacy['calories']['legacy_unverified']),Decimal('1e32'))
        malformed=project([food(calories='Infinity')])
        self.assertIsNone(malformed['calories']['total']);self.assertEqual(malformed['calories']['unknown_items'],1)

    def test_goal_integer_limits_prevent_database_overflow(self):
        from services.nutrition_data import GoalBody
        from pydantic import ValidationError
        for field in ('daily_calories','water_goal_ml'):
            with self.assertRaises(ValidationError):GoalBody.model_validate({field:10**30})

    def alternatives(self,prefs,scenario,foods=None):
        rows=[SimpleNamespace(id=uuid4(),name='Almoço',meal_type='lunch'),SimpleNamespace(id=uuid4(),name='Jantar',meal_type='dinner')]
        data={rows[0].id:[food()],rows[1].id:[food(name='Feijão')]}
        state=SimpleNamespace(date=date(2026,10,9),remaining={k:None for k in ('calories','protein','carbs','fat')},limitations=[],truncated=False)
        return build_alternatives(state,rows,foods or data,prefs,scenario,
            {'amount':prefs.budget,'period':prefs.budget_period,'source':'user_configured'} if prefs.budget else None)

    def test_daily_budget_cannot_be_borrowed_from_next_day(self):
        prefs=NutritionPreferences(budget='10',budget_period='daily',prices=[
            {'food':name,'unit':'porcao','amount':'8','source':'known'} for name in ('Arroz','Feijão')])
        result=self.alternatives(prefs,MealScenario(days=7,within_budget=True))
        self.assertEqual(len(result.organization),7)
        self.assertEqual(Decimal(result.budget['proposed_known_cost']),Decimal('56'))
        self.assertFalse(result.automatic)

    def test_missing_prices_or_budget_never_claim_affordability(self):
        self.assertEqual(self.alternatives(NutritionPreferences(budget='20'),MealScenario(within_budget=True)).candidates,[])
        self.assertEqual(self.alternatives(NutritionPreferences(),MealScenario(within_budget=True)).candidates,[])

    def test_availability_and_exclusions_are_explicit(self):
        self.assertEqual(self.alternatives(NutritionPreferences(),MealScenario(available_only=True)).candidates,[])
        prefs=NutritionPreferences(available_foods=['Arroz'],excluded_foods=['arroz'])
        self.assertEqual(self.alternatives(prefs,MealScenario(available_only=True)).candidates,[])

    def test_estimated_price_is_retained_and_portions_scale(self):
        prefs=NutritionPreferences(prices=[{'food':'Arroz','unit':'porcao','amount':'2.10','source':'estimated'}])
        result=self.alternatives(prefs,MealScenario(portions='1.5'))
        self.assertEqual(result.candidates[0]['cost'],'3.150')
        self.assertEqual(result.candidates[0]['cost_source'],'estimated')
        self.assertEqual(result.candidates[0]['macros']['calories']['total'],'150.000')

    def test_agent_scenario_contract_is_read_only_and_strict(self):
        self.assertEqual(validate_call('suggest_meals',{'days':7})['days'],7)
        for data in ({'days':True},{'portions':'0'},{'auto_register':True},{'days':8}):
            with self.assertRaises(ValueError):validate_call('suggest_meals',data)

    def test_budget_uses_exact_cost_before_display_rounding(self):
        row=SimpleNamespace(id=uuid4(),name='Arroz',meal_type='lunch')
        state=SimpleNamespace(date=date(2026,10,9),remaining={k:None for k in ('calories','protein','carbs','fat')},limitations=[],truncated=False)
        prefs=NutritionPreferences(budget='1',prices=[{'food':'Arroz','unit':'porcao','amount':'1','source':'known'}])
        result=build_alternatives(state,[row],{row.id:[food(quantity='0.3334')]},prefs,MealScenario(days=3,within_budget=True),
            {'amount':prefs.budget,'period':'weekly','source':'user_configured'})
        self.assertEqual(len(result.organization),2)
        self.assertEqual(Decimal(result.budget['proposed_known_cost']),Decimal('0.6668'))
