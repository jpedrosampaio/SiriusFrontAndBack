import os
import unittest
from datetime import datetime,date,timedelta,timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from uuid import UUID
from unittest.mock import patch
from sqlalchemy import select,func,event
from db.session import unit_of_work
from db.engine import get_engine
from db.models.identity import User,ActivityReceipt
from db.models.finance import FinancialTransaction,Budget,Projection,MonthlyBill,Invoice,CreditCard
from db.models.planning import Goal,CalendarEvent,XPEntry
from services.finance import shift_month
from services.finance_intelligence import FinanceEngine
import test_postgres_runtime_finance as fixtures


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class FinanceIntelligence(unittest.IsolatedAsyncioTestCase):
    ok=fixtures.RuntimeFinance.ok
    card=fixtures.RuntimeFinance.card

    async def asyncSetUp(self):
        await fixtures.RuntimeFinance.asyncSetUp(self)
        self.day=datetime.now(ZoneInfo('America/Sao_Paulo')).date();self.first=self.day.replace(day=1);self.next=shift_month(self.first,1)
        self.local_day=patch('services.finance_routes.local_today',return_value=self.day);self.local_day.start()
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        self.auth_intel=patch('services.finance_intelligence_routes.account',account);self.auth_intel.start()
        self.card_id=UUID(await self.card())
        async with unit_of_work() as s:
            s.add_all([FinancialTransaction(user_id=self.uid,type='income',amount=Decimal('1000.00'),category='salary',date=self.day),
                FinancialTransaction(user_id=self.uid,type='expense',amount=Decimal('100.10'),category='food',date=self.day),
                FinancialTransaction(user_id=self.uid,type='income',amount=Decimal('55.55'),category='future',date=self.next+timedelta(days=4)),
                FinancialTransaction(user_id=self.bob,type='income',amount=Decimal('9999.99'),category='private',date=self.day)])
            prior=shift_month(self.first,-1);s.add(FinancialTransaction(user_id=self.uid,type='expense',amount=Decimal('40.00'),category='food',date=prior))
            self.projection=Projection(user_id=self.uid,month=self.next,description='Known recurring installment',amount=Decimal('200.00'),category='food',card_id=self.card_id,is_fixed=True)
            s.add(self.projection);await s.flush()
            self.bill=MonthlyBill(user_id=self.uid,month=self.next,description='Imported actual source',amount=Decimal('200.00'),category='food',card_id=self.card_id,projection_id=self.projection.id)
            s.add_all([self.bill,Invoice(user_id=self.uid,card_id=self.card_id,month=self.next,amount=Decimal('300.00')),
                Budget(user_id=self.uid,category='food',month=self.first,limit=Decimal('50.00')),
                Goal(user_id=self.uid,title='Personal actual goal',target_date=self.next,progress=25)])
            await s.flush()

    async def asyncTearDown(self):
        self.auth_intel.stop();self.local_day.stop();await fixtures.RuntimeFinance.asyncTearDown(self)

    async def state(self,**params):return self.ok(await self.http.get('/api/finance/intelligence/state',params=params))

    async def counts(self):
        async with unit_of_work() as s:
            return tuple([await s.scalar(select(func.count()).select_from(m).where(m.user_id==self.uid)) for m in
                (FinancialTransaction,Projection,MonthlyBill,Invoice,CalendarEvent,XPEntry,ActivityReceipt)])

    async def test_owned_decimal_state_deduplication_known_income_and_sources(self):
        before=await self.counts();state=await self.state();self.assertEqual(before,await self.counts())
        self.assertEqual(state['income'],'1000.00');self.assertEqual(state['expense'],'100.10');self.assertEqual(state['recorded_net'],'899.90');self.assertIsNone(state['bank_balance'])
        self.assertEqual(sum((Decimal(b['amount']) for b in state['upcoming_bills']),Decimal('0')),Decimal('300.00'))
        self.assertTrue(any(o['source_id']=='bill:'+str(self.bill.id) for o in state['recurring_commitments']))
        self.assertFalse(any(o['source_type']=='projection' for o in state['upcoming_bills']))
        next_month=state['forecast']['months'][1];self.assertEqual(next_month['recorded_future_income'],'55.55');self.assertEqual(next_month['estimated_expense'],'300.00')
        self.assertEqual(state['forecast']['months'][2]['recorded_future_income'],'0.00')
        self.assertTrue(any(i['kind']=='budget_overrun' for i in state['insights']));self.assertTrue(any(i['kind']=='unusual_increase' for i in state['insights']))
        self.assertIsNone(state['goals'][0]['monetary_target']);self.assertIsNone(state['debts'][0]['monthly_interest_rate'])
        bob=self.ok(await self.http.get('/api/finance/intelligence/state',headers={'Authorization':'Bearer bob'}))
        self.assertNotIn('Imported actual source',str(bob));self.assertNotEqual(state['fingerprint'],bob['fingerprint'])

    async def test_readonly_scenarios_exact_cents_stale_and_foreign_sources(self):
        before=await self.counts();state=await self.state()
        result=self.ok(await self.http.post('/api/finance/intelligence/simulate',json={'monthly_expense':'500.00','opening_balance':'1000.00','fingerprint':state['fingerprint']}))
        for a,b in zip(result['baseline']['months'],result['scenario']['months']):self.assertEqual(Decimal(b['net_change']),Decimal(a['net_change'])-Decimal('500.00'))
        self.assertEqual(before,await self.counts());self.assertTrue(result['read_only'])
        self.assertEqual((await self.http.post('/api/finance/intelligence/simulate',json={'prepayments':[{'source_id':'bill:foreign','date':str(self.day)}]})).status_code,404)
        async with unit_of_work() as s:s.add(FinancialTransaction(user_id=self.uid,type='expense',amount=Decimal('0.01'),category='food',date=self.day))
        self.assertEqual((await self.http.post('/api/finance/intelligence/simulate',json={'fingerprint':state['fingerprint']})).status_code,409)
        self.assertEqual((await self.http.post('/api/finance/intelligence/simulate',json={'monthly_expense':'0.001'})).status_code,422)

    async def test_paid_sources_and_paid_invoice_do_not_recreate_expense(self):
        async with unit_of_work() as s:
            bill=await s.get(MonthlyBill,self.bill.id);bill.paid=True
            s.add(FinancialTransaction(user_id=self.uid,type='expense',amount=bill.amount,category='food',date=self.day,bill_id=bill.id))
        state=await self.state();self.assertEqual(state['forecast']['months'][1]['estimated_expense'],'100.00')
        async with unit_of_work() as s:
            invoice=await s.scalar(select(Invoice).where(Invoice.user_id==self.uid,Invoice.card_id==self.card_id));invoice.paid=True
        state=await self.state();self.assertFalse(state['upcoming_bills']);self.assertEqual(state['forecast']['months'][1]['estimated_expense'],'0.00')

    async def test_percentage_budget_configuration_and_missing_income(self):
        body={'category':'other','month':str(self.first)[:7],'limit':'0.00','budget_type':'percentage','percentage':'10.00'}
        first=self.ok(await self.http.post('/api/budgets',json=body,headers={'Idempotency-Key':'percentage-budget'}))
        second=self.ok(await self.http.post('/api/budgets',json=body,headers={'Idempotency-Key':'percentage-budget'}));self.assertEqual(first['budget_id'],second['budget_id'])
        rows=self.ok(await self.http.get('/api/budgets',params={'month':str(self.first)[:7]}));row=next(b for b in rows if b['category']=='other')
        self.assertEqual(row['limit'],100);self.assertEqual(row['budget_type'],'percentage')
        state=await self.state();actual=next(b for b in state['budgets'] if b['category']=='other');self.assertEqual(actual['effective_limit'],'100.00')
        future={**body,'month':str(self.next)[:7],'category':'future-unknown'}
        self.ok(await self.http.post('/api/budgets',json=future))
        rows=self.ok(await self.http.get('/api/budgets',params={'month':str(self.next)[:7]}));self.assertIsNone(rows[0]['limit'])
        empty={**body,'month':str(shift_month(self.first,2))[:7],'category':'empty-base'};self.ok(await self.http.post('/api/budgets',json=empty))
        self.assertIsNone(self.ok(await self.http.get('/api/budgets',params={'month':empty['month']}))[0]['limit'])
        self.assertEqual((await self.http.post('/api/budgets',json=body|{'category':'invalid','percentage':'100.01'})).status_code,422)

    async def test_legacy_summary_uses_requested_month_not_past_salary(self):
        month=str(shift_month(self.first,2))[:7]
        result=self.ok(await self.http.get('/api/projections/summary',params={'month':month}))
        self.assertEqual(result['estimated_income'],0)

    async def test_future_ledger_entries_do_not_change_current_budget_basis(self):
        from ai.core import Core
        # Pin all readers to the same account-local date, including at month end.
        day=self.first+timedelta(days=5)
        async with unit_of_work() as s:
            rows=(await s.scalars(select(FinancialTransaction).where(FinancialTransaction.user_id==self.uid,
                FinancialTransaction.date==self.day))).all()
            for row in rows:row.date=day
            s.add_all([FinancialTransaction(user_id=self.uid,type='income',amount=Decimal('2000.00'),category='salary',date=day+timedelta(days=1)),
                FinancialTransaction(user_id=self.uid,type='expense',amount=Decimal('300.00'),category='food',date=day+timedelta(days=1))])
            budget=await s.scalar(select(Budget).where(Budget.user_id==self.uid,Budget.category=='food'))
            user=await s.get(User,self.uid);user.preferences={'finance_budget_policies':{str(budget.id):{'budget_type':'percentage','percentage':'10.00'}}}
        at=datetime.combine(day,datetime.min.time(),tzinfo=ZoneInfo('America/Sao_Paulo'))+timedelta(hours=12)
        with patch('services.finance_routes.local_today',return_value=day),patch('services.agent_reads.local_today',return_value=day):
            legacy=self.ok(await self.http.get('/api/budgets',params={'month':str(self.first)[:7]}))[0]
            agent=(await Core().read('get_budget_status',str(self.uid)))[0]
        state=await FinanceEngine().get_state(self.uid,now=at)
        self.assertEqual(Decimal(str(legacy['limit'])),Decimal('100.00'));self.assertEqual(Decimal(str(legacy['spent'])),Decimal('100.10'))
        self.assertEqual(agent['limit'],Decimal('100.00'));self.assertEqual(agent['spent'],Decimal('100.10'))
        self.assertEqual(state.budgets[0].effective_limit,Decimal('100.00'));self.assertEqual(state.budgets[0].spent,Decimal('100.10'))
        self.assertEqual(state.forecast.months[0].recorded_future_income,Decimal('2000.00'))

    async def test_card_due_day_clamps_and_truncation_disables_forecast(self):
        async with unit_of_work() as s:
            card=await s.get(CreditCard,self.card_id);card.due_day=31
            s.add(MonthlyBill(user_id=self.uid,month=date(2027,2,1),description='February',amount=Decimal('1.00'),category='x',card_id=self.card_id))
        state=await FinanceEngine().get_state(self.uid,now=datetime(2027,1,1,12,tzinfo=timezone.utc))
        feb=next(o for o in state.upcoming_bills if o.title=='February');self.assertEqual(feb.due_date,date(2027,2,28))
        async with unit_of_work() as s:s.add_all([Projection(user_id=self.uid,month=self.next,description='Bounded'+str(i),amount=Decimal('0.01'),category='x') for i in range(1001)])
        state=await self.state();self.assertFalse(state['complete']);self.assertIsNone(state['forecast'])
        self.assertEqual((await self.http.post('/api/finance/intelligence/simulate',json={})).status_code,409)

    async def test_query_count_does_not_grow_with_ledger_history(self):
        counter=[]
        def capture(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('SELECT'):counter.append(1)
        engine=get_engine().sync_engine;event.listen(engine,'before_cursor_execute',capture)
        try:
            await self.state();initial=len(counter);counter.clear()
            async with unit_of_work() as s:s.add_all([FinancialTransaction(user_id=self.uid,type='expense',amount=Decimal('0.01'),category='food',date=self.day) for _ in range(500)])
            counter.clear();await self.state();self.assertEqual(len(counter),initial);self.assertLessEqual(initial,20)
        finally:event.remove(engine,'before_cursor_execute',capture)

    async def test_agent_reads_same_engine_and_manual_debts_do_not_write(self):
        from ai.core import Core
        before=await self.counts();facts=await Core().read('get_finance_state',str(self.uid));self.assertEqual(facts['recorded_net'],'899.90')
        result=self.ok(await self.http.post('/api/finance/intelligence/compare-debts',json={'monthly_payment':'10','debts':[{'id':'scenario','title':'Declared','principal':'100.10'}]}))
        self.assertTrue(all(r['total_interest'] is None for r in result['results']));self.assertEqual(before,await self.counts())

    async def test_actual_card_charge_and_imported_bill_keep_one_obligation(self):
        with patch('services.finance.local_today',return_value=self.day):
            self.ok(await self.http.post('/api/credit-cards/'+str(self.card_id)+'/charge',json={
                'amount':'100.01','description':'Real cents split','category':'x','payment_type':'parcelado',
                'installments':3,'start_month':'current'},headers={'Idempotency-Key':'intelligence-charge-real'}))
        state=await self.state();total=sum((Decimal(o['amount']) for o in state['upcoming_bills']),Decimal('0'))
        self.assertEqual(total,Decimal('366.67'))
        self.assertFalse(any(o['source_type']=='invoice' and o['month']==str(self.first) for o in state['upcoming_bills']))
        month=str(shift_month(self.first,2))[:7]
        self.ok(await self.http.get('/api/finance/monthly-bills',params={'month':month}))
        after=await self.state();self.assertEqual(sum((Decimal(o['amount']) for o in after['upcoming_bills']),Decimal('0')),total)
        self.assertEqual(after['expense'],'133.44')

    async def test_degraded_financial_agent_reuses_context_without_provider_or_writes(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from ai.core import Core
        from ai.agent import SiriusAgent
        from ai.actions import Preferences
        router=SimpleNamespace(settings=SimpleNamespace(rag=False),generate=AsyncMock(side_effect=AssertionError('No real provider')))
        agent=SiriusAgent(Core(),router,SimpleNamespace(get=AsyncMock(return_value={})),
            SimpleNamespace(preferences=AsyncMock(return_value=Preferences())),
            SimpleNamespace(list=AsyncMock(return_value=[])),SimpleNamespace())
        before=await self.counts()
        with patch.object(FinanceEngine,'get_state',new_callable=AsyncMock,wraps=FinanceEngine().get_state) as collected:
            result=await agent.respond(str(self.uid),SimpleNamespace(message='Como estão minhas finanças?',page='/finance',
                page_context={},conversation_id='primary',request_id='finance-context-once'),json.dumps({'history':[]}))
            self.assertEqual(collected.await_count,1)
        self.assertEqual(result['facts']['get_finance_state']['recorded_net'],'899.90')
        self.assertFalse(result['actions']);self.assertEqual(before,await self.counts());router.generate.assert_not_called()
