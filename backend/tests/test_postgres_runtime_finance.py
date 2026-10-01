import asyncio
import os
import sys
import unittest
from datetime import date
from decimal import Decimal
from uuid import uuid4, UUID
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from db.engine import dispose_engine
from db.session import unit_of_work
from db.repositories.identity import IdentityRepository
from db.models.finance import FinancialTransaction, CardPurchase, Projection, MonthlyBill, Invoice
from services.finance import shift_month

if sys.platform=='win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class RuntimeFinance(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch.dict(os.environ,{'MONGO_URL':'mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=10','DB_NAME':'unavailable'}):
            import server
        self.http=AsyncClient(transport=ASGITransport(server.app),base_url='https://sirius.test')
        async with unit_of_work() as session:
            repo=IdentityRepository(session)
            self.uid=(await repo.create(email=f'{uuid4()}@example.test',name='Finance',password_hash='test-only')).id
            self.bob=(await repo.create(email=f'{uuid4()}@example.test',name='Bob',password_hash='test-only')).id
        async def account(request):
            return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),
                'timezone':'America/Sao_Paulo','name':'Finance'}
        self.patches=[patch('services.finance_routes.account',account),patch('services.finance_export.account',account),
            patch('services.finance_routes.local_today',return_value=date(2026,12,31)),
            patch('services.finance.local_today',return_value=date(2026,12,31))]
        for p in self.patches: p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches): p.stop()
        await self.http.aclose(); await dispose_engine()

    def ok(self,response):
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    async def count(self,model):
        async with unit_of_work() as session:
            return await session.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid))

    async def card(self):
        return self.ok(await self.http.post('/api/credit-cards',json={'name':'Card','limit':'1000.00','closing_day':10,'due_day':20}))['card_id']

    async def test_decimal_transactions_replay_stats_budgets_and_trend(self):
        payload={'type':'expense','amount':'0.10','category':'outros','date':'2026-12-31'}
        responses=await asyncio.gather(*(self.http.post('/api/transactions',json=payload,headers={'Idempotency-Key':'expense-replay-001'}) for _ in range(8)))
        for response in responses: self.ok(response)
        self.assertEqual(await self.count(FinancialTransaction),1)
        self.ok(await self.http.post('/api/transactions',content='{"type":"expense","amount":0.20,"category":"outros","date":"2026-12-31"}',headers={'Content-Type':'application/json'}))
        async with unit_of_work() as session:
            total=await session.scalar(select(func.sum(FinancialTransaction.amount)).where(FinancialTransaction.user_id==self.uid))
            self.assertEqual(total,Decimal('0.30'))
        stats=self.ok(await self.http.get('/api/finance/stats'))
        self.assertEqual(stats['total_expense'],0.3)
        self.ok(await self.http.post('/api/budgets',json={'category':'outros','month':'2026-12','limit':'10.00'}))
        self.assertEqual(self.ok(await self.http.get('/api/budgets'))[0]['spent'],0.3)
        trend=self.ok(await self.http.get('/api/finance/trend'))
        self.assertEqual(len({row['month_key'] for row in trend['trend']}),6)
        self.assertEqual(trend['trend'][-1]['month_key'],'2026-12')
        rows=self.ok(await self.http.get('/api/transactions',params={'month':'2026-12'}))
        self.assertEqual(len(rows),2)
        self.assertEqual(self.ok(await self.http.get('/api/transactions',params={'month':'2026-11'})),[])

    async def test_installments_sum_exactly_and_charge_is_atomic_replay(self):
        card=await self.card()
        body={'amount':'100.00','description':'Purchase','category':'outros','payment_type':'parcelado','installments':3,'start_month':'current'}
        results=await asyncio.gather(*(self.http.post(f'/api/credit-cards/{card}/charge',json=body,headers={'Idempotency-Key':'charge-replay-001'}) for _ in range(8)))
        for response in results: self.ok(response)
        self.assertEqual(await self.count(CardPurchase),1)
        self.assertEqual(await self.count(FinancialTransaction),1)
        self.assertEqual(await self.count(Projection),2)
        async with unit_of_work() as session:
            first=await session.scalar(select(FinancialTransaction.amount).where(FinancialTransaction.user_id==self.uid))
            future=await session.scalar(select(func.sum(Projection.amount)).where(Projection.user_id==self.uid))
            self.assertEqual(first+future,Decimal('100.00'))
        invoices=self.ok(await self.http.get(f'/api/credit-cards/{card}/invoices'))
        self.assertEqual([r['month'] for r in invoices],['2026-12','2027-01','2027-02'])
        self.assertEqual([r['amount'] for r in invoices],[33.34,33.33,33.33])
        rows=self.ok(await self.http.get('/api/transactions'))
        self.assertEqual(rows[0]['card_id'],card)
        self.assertEqual(rows[0]['total_amount'],100)
        self.ok(await self.http.delete('/api/transactions/'+rows[0]['transaction_id']))
        self.assertEqual(await self.count(Projection),0)
        self.assertTrue(all(row['amount']==0 for row in self.ok(await self.http.get(f'/api/credit-cards/{card}/invoices'))))

    async def test_next_month_charge_and_import_bills_are_not_duplicated(self):
        card=await self.card()
        self.ok(await self.http.post(f'/api/credit-cards/{card}/charge',json={'amount':'48.00','start_month':'next','payment_type':'vista'}))
        self.assertEqual(await self.count(FinancialTransaction),0)
        self.assertEqual(self.ok(await self.http.get('/api/projections'))[0]['month'],'2027-01')
        results=await asyncio.gather(*(self.http.get('/api/finance/monthly-bills',params={'month':'2027-01'}) for _ in range(8)))
        for response in results: self.assertEqual(self.ok(response)['count'],1)
        self.assertEqual(await self.count(MonthlyBill),1)

    async def test_bill_paid_undo_replay_and_rollback(self):
        bill=self.ok(await self.http.post('/api/finance/monthly-bills',json={'amount':'48.00','description':'Internet'}))
        path=f"/api/finance/monthly-bills/{bill['bill_id']}/toggle"
        for response in await asyncio.gather(*(self.http.patch(path,params={'paid':True},headers={'Idempotency-Key':'bill-payment-001'}) for _ in range(8))): self.ok(response)
        self.assertEqual(await self.count(FinancialTransaction),1)
        self.ok(await self.http.patch(path,params={'paid':False}))
        self.assertEqual(await self.count(FinancialTransaction),0)
        self.assertTrue(self.ok(await self.http.patch(path,params={'paid':True},headers={'Idempotency-Key':'bill-payment-001'}))['replayed'])
        self.assertEqual(await self.count(FinancialTransaction),0)
        from services.finance import toggle_bill
        async def fail(*args,**kwargs):
            await toggle_bill(*args,**kwargs)
            raise RuntimeError('after finance write')
        with patch('services.finance_routes.toggle_bill',fail):
            with self.assertRaises(Exception): await self.http.patch(path,params={'paid':True})
        self.assertEqual(await self.count(FinancialTransaction),0)
        self.assertEqual(self.ok(await self.http.get('/api/finance/monthly-bills'))['total_paid'],0)

    async def test_projection_repeats_summary_update_and_delete(self):
        first=self.ok(await self.http.post('/api/projections',json={'month':'2026-12','amount':'25.00','repeat_count':3,'category':'outros'}))
        self.assertEqual(await self.count(Projection),3)
        self.assertEqual(self.ok(await self.http.get('/api/projections/summary',params={'month':'2027-01'}))['total_projected_expenses'],25)
        path='/api/projections/'+first['projection_id']
        self.ok(await self.http.patch(path,params={'amount':'30.01','description':'Updated'}))
        bills=self.ok(await self.http.get('/api/finance/monthly-bills'))
        self.assertEqual(bills['total'],30.01)
        self.ok(await self.http.delete(path))
        self.assertEqual(self.ok(await self.http.get('/api/finance/monthly-bills'))['count'],1)

    async def test_categories_and_cross_user_writes_and_reads(self):
        self.ok(await self.http.post('/api/finance/categories',json={'name':'Custom','icon':'x','color':'#123456'}))
        categories=self.ok(await self.http.get('/api/finance/categories'))['categories']
        self.assertEqual(next(c for c in categories if c['name']=='custom')['color'],'#123456')
        self.assertEqual((await self.http.delete('/api/finance/categories/custom',headers={'Authorization':'Bearer bob'})).status_code,404)
        self.ok(await self.http.delete('/api/finance/categories/custom'))
        card=await self.card(); headers={'Authorization':'Bearer bob'}
        self.assertEqual((await self.http.post(f'/api/credit-cards/{card}/charge',json={'amount':'48.00'},headers=headers)).status_code,404)
        self.assertEqual((await self.http.get(f'/api/credit-cards/{card}/invoices',headers=headers)).status_code,404)
        transaction=self.ok(await self.http.post('/api/transactions',json={'type':'income','amount':'48.00','date':'2026-12-31'}))
        self.assertEqual((await self.http.delete('/api/transactions/'+transaction['transaction_id'],headers=headers)).status_code,404)
        self.assertEqual(self.ok(await self.http.get('/api/transactions',headers=headers)),[])

    async def test_empty_states_validation_and_exports(self):
        for path in ('/api/finance/stats','/api/finance/trend','/api/projections/summary','/api/finance/monthly-bills','/api/budgets','/api/credit-cards'):
            self.ok(await self.http.get(path))
        for amount in ('0','-1','0.001','NaN','Infinity'):
            response=await self.http.post('/api/transactions',json={'type':'expense','amount':amount,'date':'2026-12-31'})
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual((await self.http.get('/api/finance/stats',params={'month':'2026-13'})).status_code,422)
        self.assertEqual((await self.http.post('/api/credit-cards',json={'name':'Bad','limit':100,'closing_day':32,'due_day':1})).status_code,422)
        for extension,magic in (('excel',b'PK'),('pdf',b'%PDF')):
            response=await self.http.get('/api/export/finance/'+extension,params={'start':'2026-12-01','end':'2026-12-31'})
            self.assertEqual(response.status_code,200,response.text[:100] if response.status_code!=200 else '')
            self.assertTrue(response.content.startswith(magic))
