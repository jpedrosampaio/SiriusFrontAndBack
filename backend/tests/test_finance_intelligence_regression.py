import sys
import unittest
from pathlib import Path
from datetime import date
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from finance_contracts import DebtScenario,FinanceScenario,Obligation
from services.finance_debt import compare_debts
from services.finance_intelligence import build_forecast


class FinanceRules(unittest.TestCase):
    def test_unknown_rates_never_claim_payoff_or_zero_interest(self):
        body=DebtScenario(debts=[{'id':'a','title':'A','principal':'100.00'},
            {'id':'b','title':'B','principal':'50.00','monthly_rate_percent':'2'}],monthly_payment='25.00',custom_order=['a','b'])
        results=compare_debts(body)['results']
        self.assertEqual(results[0]['order'],['b','a']);self.assertIsNone(results[1]['order'])
        self.assertTrue(all(r['payoff_months'] is None and r['total_interest'] is None for r in results))

    def test_exact_amortization_minimums_priority_and_totals(self):
        body=DebtScenario(debts=[{'id':'a','title':'A','principal':'100.00','monthly_rate_percent':'10','minimum_payment':'5'},
            {'id':'b','title':'B','principal':'50.00','monthly_rate_percent':'0','minimum_payment':'5'}],monthly_payment='30.00',custom_order=['b','a'])
        results=compare_debts(body)['results'];snow,avalanche,custom=results
        self.assertEqual(snow['order'],['b','a']);self.assertEqual(avalanche['order'],['a','b']);self.assertEqual(custom['order'],['b','a'])
        self.assertLessEqual(avalanche['total_interest'],snow['total_interest'])
        for r in results:
            self.assertEqual(r['status'],'paid_in_model');self.assertEqual(r['remaining'],Decimal('0.00'))
            self.assertEqual(r['total_paid'],Decimal('150.00')+r['total_interest'])
            self.assertEqual(r['total_interest'],sum((m['interest'] for m in r['timeline']),Decimal('0.00')))
            self.assertTrue(all(m['payment']<=Decimal('30.00') for m in r['timeline']))

    def test_infeasible_and_growing_debt_are_bounded_not_repaid(self):
        body=DebtScenario(debts=[{'id':'a','title':'A','principal':'100','monthly_rate_percent':'5','minimum_payment':'50'}],monthly_payment='20')
        self.assertTrue(all(r['status']=='minimums_exceed_envelope' and r['payoff_months'] is None for r in compare_debts(body)['results']))
        body=DebtScenario(debts=[{'id':'a','title':'A','principal':'1000000000','monthly_rate_percent':'100'}],monthly_payment='0.01',months=360)
        for r in compare_debts(body)['results']:
            self.assertEqual(r['status'],'horizon_reached');self.assertIsNone(r['payoff_months']);self.assertEqual(len(r['timeline']),360)

    def test_typed_invalid_scenarios_and_decimal_subcents(self):
        for value in ({'monthly_expense':'0.001'},{'monthly_income':'NaN'},{'months':True},{'user_id':'bob'},
            {'months':1,'additions_start_offset':1},{'prepayments':[{'source_id':'a','date':'2026-10-09'}]*2}):
            with self.assertRaises(ValueError):FinanceScenario.model_validate(value)
        with self.assertRaises(ValueError):DebtScenario(debts=[{'id':'a','title':'A','principal':'10'}],monthly_payment='1',custom_order=['b'])

    def test_cashflow_only_known_income_and_prepayment_preserves_total(self):
        day=date(2026,10,8);future={date(2026,11,1):{'income':Decimal('55.55')}}
        item=Obligation(source_id='projection:owned',source_type='projection',title='Installment',category='x',amount='100.01',month=date(2026,11,1),reason='Recorded projection')
        baseline=build_forecast(day,3,future,[item]);self.assertEqual(baseline.months[0].recorded_future_income,Decimal('0.00'))
        scenario=FinanceScenario(months=3,opening_balance='500',monthly_expense='0.10',prepayments=[{'source_id':item.source_id,'date':day}])
        changed=build_forecast(day,3,future,[item],scenario)
        self.assertEqual(changed.months[0].scenario_expense,Decimal('100.11'))
        self.assertEqual(changed.months[1].estimated_expense,Decimal('0.00'))
        self.assertEqual(changed.months[-1].cumulative_change,baseline.months[-1].cumulative_change-Decimal('0.30'))
        self.assertEqual(changed.months[-1].scenario_balance,Decimal('500')+changed.months[-1].cumulative_change)
