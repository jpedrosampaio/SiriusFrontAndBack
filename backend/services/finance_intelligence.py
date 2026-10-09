"""Owned, coherent financial facts and pure scenarios over existing ledgers."""
import hashlib
import json
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DecimalException
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, func, text, tuple_, cast, Date as SQLDate
from db.session import unit_of_work
from db.models.identity import User
from db.models.finance import FinancialTransaction, Budget, CreditCard, CardPurchase, Invoice, Projection, MonthlyBill
from db.models.planning import Goal
from finance_contracts import (FinanceState, Forecast, ForecastMonth, Obligation, BudgetState, GoalState,
    DebtState, Insight, FinanceScenario)
from services.finance import shift_month
from services.finance_debt import cents

ZERO=Decimal('0.00')
LIMIT=1000


def exact_wire(value):
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,(date,datetime)):return value.isoformat()
    if isinstance(value,dict):return {str(k):exact_wire(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [exact_wire(v) for v in value]
    return value


def budget_policy(row,preferences,income):
    policies=(preferences or {}).get('finance_budget_policies',{})
    raw=policies.get(str(row.id),{}) if isinstance(policies,dict) else {}
    if not isinstance(raw,dict) or raw.get('budget_type')!='percentage':return row.limit,'fixed',None,'Limite fixo registrado.'
    try:
        percent=Decimal(str(raw.get('percentage')))
        if not percent.is_finite() or not 0<percent<=100:raise ValueError()
    except (ValueError,DecimalException):return None,'percentage',None,'Percentual inválido; configure novamente.'
    return (cents(income*percent/100) if income>0 else None),'percentage',percent,'Percentual da renda registrada no próprio mês até a data local da consulta; sem renda registrada, limite indeterminado.'


def build_forecast(day,months,future,obligations,scenario=None):
    scenario=scenario or FinanceScenario(months=months)
    first=day.replace(day=1);end=shift_month(first,months)
    moved={p.source_id:p.date for p in scenario.prepayments}
    available={o.source_id:o for o in obligations}
    if not set(moved).issubset(available):raise HTTPException(404,'Obrigação indisponível nesta conta/horizonte.')
    if any(not day<=d<end for d in moved.values()):raise HTTPException(422,'Data de cenário fora do horizonte.')
    estimates={};hypothetical={}
    for o in obligations:
        month=max(first,o.month)
        if o.source_id in moved:
            month=moved[o.source_id].replace(day=1)
            hypothetical[month]=hypothetical.get(month,ZERO)+o.amount
        else:estimates[month]=estimates.get(month,ZERO)+o.amount
    rows=[];cumulative=ZERO
    for offset in range(months):
        month=shift_month(first,offset);known=future.get(month,{})
        income=known.get('income',ZERO);expense=known.get('expense',ZERO);estimate=estimates.get(month,ZERO)
        additional_income=scenario.monthly_income if offset>=scenario.additions_start_offset else ZERO
        additional_expense=(scenario.monthly_expense if offset>=scenario.additions_start_offset else ZERO)+hypothetical.get(month,ZERO)
        change=income-expense-estimate+additional_income-additional_expense;cumulative+=change
        rows.append(ForecastMonth(month=month,recorded_future_income=income,recorded_future_expense=expense,
            estimated_expense=estimate,scenario_income=additional_income,scenario_expense=additional_expense,
            net_change=change,cumulative_change=cumulative,
            scenario_balance=scenario.opening_balance+cumulative if scenario.opening_balance is not None else None))
    return Forecast(as_of=day,end=end-timedelta(days=1),months=rows,assumptions=[
        'Fluxos futuros após a data local da consulta; saldo bancário não foi informado nem inferido.',
        'Receitas futuras só vêm de lançamentos futuros registrados; salário passado não é repetido.',
        'Contas, parcelas e projeções pendentes são estimativas deduplicadas por vínculos explícitos.',
        'Contas sem dia de vencimento ficam no mês; pendências de meses passados entram no mês atual.',
        'Acréscimos mensais são hipóteses em cada mês a partir do offset escolhido, inclusive o mês inicial.',
        'Antecipação de cenário usa o valor integral registrado, sem desconto, tarifa ou juros presumidos.'])


class FinanceEngine:
    async def get_state(self,user_id,*,months=6,now=None):
        if type(months) is not int or not 1<=months<=12:raise HTTPException(422,'Horizonte entre 1 e 12 meses.')
        async with unit_of_work() as s:
            await s.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
            user=await s.get(User,UUID(str(user_id)))
            if user is None:raise HTTPException(404,'Conta não encontrada.')
            instant=now or datetime.now(timezone.utc)
            if instant.tzinfo is None:raise ValueError('Aware instant required')
            day=instant.astimezone(ZoneInfo(user.timezone)).date();first=day.replace(day=1);end=shift_month(first,months)
            totals=dict((await s.execute(select(FinancialTransaction.type,func.sum(FinancialTransaction.amount)).where(
                FinancialTransaction.user_id==user.id,FinancialTransaction.date.between(first,day)).group_by(FinancialTransaction.type))).all())
            income=totals.get('income',ZERO);expense=totals.get('expense',ZERO)
            bucket=func.date_trunc('month',FinancialTransaction.date)
            future={}
            for month,kind,amount in (await s.execute(select(bucket,FinancialTransaction.type,func.sum(FinancialTransaction.amount)).where(
                FinancialTransaction.user_id==user.id,FinancialTransaction.date>day,FinancialTransaction.date<end).group_by(bucket,FinancialTransaction.type))).all():
                future.setdefault(month.date(),{})[kind]=amount
            imported=select(MonthlyBill.id).where(MonthlyBill.user_id==user.id,MonthlyBill.projection_id==Projection.id).exists()
            paid_invoice=select(Invoice.id).where(Invoice.user_id==user.id,Invoice.card_id==Projection.card_id,
                Invoice.month==Projection.month,Invoice.paid.is_(True)).exists()
            projections=list((await s.scalars(select(Projection).where(Projection.user_id==user.id,Projection.month<end,
                (Projection.month>=first)|(~imported & ~paid_invoice))
                .order_by(Projection.month,Projection.id).limit(LIMIT+1))).all())
            bills=list((await s.scalars(select(MonthlyBill).where(MonthlyBill.user_id==user.id,
                MonthlyBill.month<end,(MonthlyBill.month>=first)|MonthlyBill.paid.is_(False))
                .order_by(MonthlyBill.month,MonthlyBill.id).limit(LIMIT+1))).all())
            pending_invoice_bill=select(MonthlyBill.id).where(MonthlyBill.user_id==user.id,MonthlyBill.card_id==Invoice.card_id,
                MonthlyBill.month==Invoice.month,MonthlyBill.paid.is_(False)).exists()
            invoices=list((await s.scalars(select(Invoice).where(Invoice.user_id==user.id,Invoice.month<end,
                (Invoice.month>=first)|Invoice.paid.is_(False)|pending_invoice_bill)
                .order_by(Invoice.month,Invoice.id).limit(LIMIT+1))).all())
            cards=list((await s.scalars(select(CreditCard).where(CreditCard.user_id==user.id).order_by(CreditCard.id).limit(201))).all())
            budgets=list((await s.scalars(select(Budget).where(Budget.user_id==user.id,Budget.month==first).order_by(Budget.id).limit(201))).all())
            goals=list((await s.scalars(select(Goal).where(Goal.user_id==user.id,Goal.archived_at.is_(None))
                .order_by(Goal.target_date,Goal.id).limit(101))).all())
            complete=all(len(rows)<=cap for rows,cap in ((projections,LIMIT),(bills,LIMIT),(invoices,LIMIT),(cards,200),(budgets,200),(goals,100)))
            projections=projections[:LIMIT];bills=bills[:LIMIT];invoices=invoices[:LIMIT];cards=cards[:200];budgets=budgets[:200];goals=goals[:100]
            paid_bill_ids=set((await s.scalars(select(FinancialTransaction.bill_id).where(FinancialTransaction.user_id==user.id,
                FinancialTransaction.type=='expense',FinancialTransaction.bill_id.in_([b.id for b in bills])))).all())
            represented={}
            invoice_keys=[(i.card_id,i.month) for i in invoices]
            # Posted card charges are already ledger expenses, not another future invoice expense.
            for card,month,amount in (await s.execute(select(CardPurchase.card_id,bucket,func.sum(FinancialTransaction.amount))
                .join(CardPurchase,(CardPurchase.id==FinancialTransaction.purchase_id)&(CardPurchase.user_id==FinancialTransaction.user_id))
                .where(FinancialTransaction.user_id==user.id,FinancialTransaction.type=='expense',FinancialTransaction.bill_id.is_(None),
                    tuple_(CardPurchase.card_id,cast(bucket,SQLDate)).in_(invoice_keys),
                    FinancialTransaction.date<end).group_by(CardPurchase.card_id,bucket))).all():represented[(card,month.date())]=amount
            # Closed old bills do not need history hydration; they still cover their invoice aggregate.
            for card,month,amount in (await s.execute(select(MonthlyBill.card_id,MonthlyBill.month,func.sum(MonthlyBill.amount)).where(
                MonthlyBill.user_id==user.id,MonthlyBill.month<first,MonthlyBill.paid.is_(True),MonthlyBill.card_id.is_not(None))
                .where(tuple_(MonthlyBill.card_id,MonthlyBill.month).in_(invoice_keys))
                .group_by(MonthlyBill.card_id,MonthlyBill.month))).all():represented[(card,month)]=represented.get((card,month),ZERO)+amount
            invoice_by={(i.card_id,i.month):i for i in invoices};card_by={c.id:c for c in cards};by_projection={b.projection_id:b for b in bills if b.projection_id}
            projection_by={p.id:p for p in projections}
            obligations=[];warnings=['Saldo dos registros não é saldo bancário. Taxas externas e valores financeiros de metas não estão cadastrados.']
            def add(row,kind):
                invoice=invoice_by.get((row.card_id,row.month)) if row.card_id else None
                paid=isinstance(row,MonthlyBill) and (row.paid or row.id in paid_bill_ids)
                if row.card_id:
                    key=(row.card_id,row.month);represented[key]=represented.get(key,ZERO)+row.amount
                if isinstance(row,MonthlyBill) and row.source=='deleted':return
                if paid:
                    if not row.paid:warnings.append('Conta com despesa vinculada foi deduplicada, embora a flag de pagamento esteja divergente.')
                    return
                if invoice and invoice.paid:
                    warnings.append('Fatura marcada paga suprime estimativas do cartão; flags de contas/projeções podem divergir do lançamento.')
                    return
                card=card_by.get(row.card_id);due=date(row.month.year,row.month.month,min(card.due_day,monthrange(row.month.year,row.month.month)[1])) if card else None
                obligations.append(Obligation(source_id=f'{kind}:{row.id}',source_type=kind,title=row.description[:200],category=row.category,
                    amount=row.amount,month=row.month,due_date=due,due_source='card_configuration' if card else 'month_only',
                    card_id=str(row.card_id) if row.card_id else None,
                    recurring=row.is_fixed if isinstance(row,Projection) else bool(row.projection_id in projection_by and projection_by[row.projection_id].is_fixed),
                    reason='Conta pendente registrada.' if kind=='bill' else 'Projeção materializada; não é pagamento confirmado.'))
            for b in bills:add(b,'bill')
            for p in projections:
                if p.id not in by_projection:add(p,'projection')
            for i in invoices:
                residual=max(ZERO,i.amount-represented.get((i.card_id,i.month),ZERO))
                if not i.paid and residual:
                    card=card_by.get(i.card_id);due=date(i.month.year,i.month.month,min(card.due_day,monthrange(i.month.year,i.month.month)[1])) if card else None
                    obligations.append(Obligation(source_id='invoice:'+str(i.id),source_type='invoice',title='Residual da fatura: '+(card.name if card else 'cartão'),
                        category='cartão',amount=residual,month=i.month,due_date=due,due_source='card_configuration' if card else 'month_only',card_id=str(i.card_id),
                        reason='Parcela do agregado da fatura ainda não representada por contas, projeções ou despesas vinculadas.'))
            prior=shift_month(first,-1);prior_last=date(prior.year,prior.month,min(day.day,monthrange(prior.year,prior.month)[1]))
            grouped=(await s.execute(select(FinancialTransaction.category,
                func.sum(FinancialTransaction.amount).filter(FinancialTransaction.date>=first),
                func.sum(FinancialTransaction.amount).filter(FinancialTransaction.date<=prior_last)).where(
                FinancialTransaction.user_id==user.id,FinancialTransaction.type=='expense',
                ((FinancialTransaction.date>=first)&(FinancialTransaction.date<=day))|
                ((FinancialTransaction.date>=prior)&(FinancialTransaction.date<=prior_last)))
                .group_by(FinancialTransaction.category).order_by(FinancialTransaction.category).limit(201))).all()
            if len(grouped)>200:complete=False
            spent=dict((await s.execute(select(FinancialTransaction.category,func.sum(FinancialTransaction.amount)).where(
                FinancialTransaction.user_id==user.id,FinancialTransaction.type=='expense',FinancialTransaction.date.between(first,day),
                FinancialTransaction.category.in_([b.category for b in budgets])).group_by(FinancialTransaction.category))).all())
            insights=[];budget_states=[]
            for b in budgets:
                limit,kind,percent,basis=budget_policy(b,user.preferences,income)
                budget_states.append(BudgetState(budget_id=str(b.id),category=b.category,spent=spent.get(b.category,ZERO),
                    effective_limit=limit,budget_type=kind,percentage=percent,basis=basis))
                if limit is not None and spent.get(b.category,ZERO)>limit:
                    insights.append(Insight(kind='budget_overrun',title='Orçamento excedido: '+b.category,
                        facts={'spent':spent[b.category],'limit':limit,'excess':spent[b.category]-limit,'budget_id':str(b.id)},method=basis))
            for category,current,previous in grouped[:200]:
                current=current or ZERO;previous=previous or ZERO
                if previous>0 and current>previous:
                    ratio=cents((current-previous)*100/previous)
                    insights.append(Insight(kind='unusual_increase' if current>=2*previous else 'category_growth',title='Aumento registrado: '+category,
                        facts={'current':current,'previous':previous,'increase_percent':ratio,'current_start':str(first),'current_end':str(day),
                            'previous_start':str(prior),'previous_end':str(prior_last)},method='Mesmo trecho calendário; aumento incomum significa pelo menos o dobro, não fraude ou previsão.'))
            recurring=[o for o in obligations if o.recurring]
            if recurring:insights.append(Insight(kind='recurring_commitment',title='Compromissos fixos materializados',
                facts={'count':len(recurring),'total_in_horizon':sum((o.amount for o in recurring),ZERO)},method='is_fixed registrado; sem prolongar além dos meses materializados.'))
            debt_amounts={}
            for o in obligations:
                if o.card_id:debt_amounts[o.card_id]=debt_amounts.get(o.card_id,ZERO)+o.amount
            if not complete:warnings.append('Limite de detalhes atingido; cenário e projeção suspensos para não omitir obrigações.')
            payload=FinanceState(as_of=day,timezone=user.timezone,month=first,income=income,expense=expense,recorded_net=income-expense,
                upcoming_bills=obligations,budgets=budget_states,recurring_commitments=recurring,
                debts=[DebtState(card_id=identity,title=card_by[UUID(identity)].name if UUID(identity) in card_by else 'Cartão',known_obligations=amount) for identity,amount in sorted(debt_amounts.items())],
                goals=[GoalState(goal_id=str(g.id),title=g.title[:200],target_date=g.target_date,progress_percent=Decimal(str(g.progress))) for g in goals],
                forecast=build_forecast(day,months,future,obligations) if complete else None,insights=insights[:200],complete=complete,fingerprint='0'*64,
                warnings=list(dict.fromkeys(warnings)))
            digest=hashlib.sha256(json.dumps({'owner':str(user.id),'state':payload.model_dump(mode='json')},sort_keys=True).encode()).hexdigest()
            payload.fingerprint=digest
            return payload

    async def simulate(self,user_id,scenario:FinanceScenario):
        state=await self.get_state(user_id,months=scenario.months)
        if not state.complete:raise HTTPException(409,'Dados parciais; cenário suspenso.')
        if scenario.fingerprint and scenario.fingerprint!=state.fingerprint:raise HTTPException(409,'Dados mudaram; atualize antes de simular.')
        future={m.month:{'income':m.recorded_future_income,'expense':m.recorded_future_expense} for m in state.forecast.months}
        simulated=build_forecast(state.as_of,scenario.months,future,state.upcoming_bills,scenario)
        return {'state':state.model_dump(mode='json'),'baseline':state.forecast.model_dump(mode='json'),
            'scenario':simulated.model_dump(mode='json'),'read_only':True,'fingerprint':state.fingerprint}


def agent_context(state):
    raw=state.model_dump(mode='json') if isinstance(state,FinanceState) else state
    return {k:raw[k] for k in ('version','as_of','timezone','income','expense','recorded_net','bank_balance','complete','warnings')}|{
        'upcoming_bills':raw['upcoming_bills'][:10],'budgets':raw['budgets'][:10],'debts':raw['debts'][:10],
        'goals':raw['goals'][:10],'forecast':raw['forecast'],'insights':raw['insights'][:10],
        'display_limited':any(len(raw[k])>10 for k in ('upcoming_bills','budgets','debts','goals','insights'))}
