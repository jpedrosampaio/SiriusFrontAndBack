"""Deterministic hypothetical amortization; no DB, providers or inferred rates."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
from finance_contracts import DebtScenario

ZERO=Decimal('0.00')


def cents(value):
    return value.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)


def compare_debts(scenario:DebtScenario):
    with localcontext() as context:
        context.prec=160  # Bounded 360-month model, including rapidly growing debt.
        return _compare_debts(scenario)


def _compare_debts(scenario:DebtScenario):
    debts={d.id:d for d in scenario.debts}
    known=all(d.monthly_rate_percent is not None for d in debts.values())
    results=[]
    for strategy in ('snowball','avalanche','custom'):
        if strategy=='custom' and not scenario.custom_order:continue
        balances={k:d.principal for k,d in debts.items()}
        def order():
            if strategy=='custom':return [k for k in scenario.custom_order if balances[k]>0]
            if strategy=='avalanche':return sorted((k for k in debts if balances[k]>0),key=lambda k:(-debts[k].monthly_rate_percent,balances[k],k))
            return sorted((k for k in debts if balances[k]>0),key=lambda k:(balances[k],k))
        if not known:
            results.append({'strategy':strategy,'order':None if strategy=='avalanche' else order(),
                'payoff_months':None,'total_interest':None,'total_paid':None,'remaining':sum(balances.values(),ZERO),
                'timeline':[],'status':'unknown_rates'})
            continue
        timeline=[];interest_total=ZERO;paid_total=ZERO;status='horizon_reached';payoff=None
        first_order=order()
        for index in range(1,scenario.months+1):
            interest=sum((cents(balances[k]*debts[k].monthly_rate_percent/100) for k in balances if balances[k]>0),ZERO)
            for k in balances:
                if balances[k]>0:balances[k]+=cents(balances[k]*debts[k].monthly_rate_percent/100)
            interest_total+=interest
            minimums={k:min(balances[k],debts[k].minimum_payment) for k in balances if balances[k]>0}
            if sum(minimums.values(),ZERO)>scenario.monthly_payment:
                timeline.append({'month_number':index,'payment':ZERO,'interest':interest,'remaining':sum(balances.values(),ZERO)})
                status='minimums_exceed_envelope';break
            budget=scenario.monthly_payment;paid=ZERO
            for k,amount in minimums.items():balances[k]-=amount;budget-=amount;paid+=amount
            for k in order():
                amount=min(balances[k],budget);balances[k]-=amount;budget-=amount;paid+=amount
            paid_total+=paid;remaining=sum(balances.values(),ZERO)
            timeline.append({'month_number':index,'payment':paid,'interest':interest,'remaining':remaining})
            if remaining==0:status='paid_in_model';payoff=index;break
        results.append({'strategy':strategy,'order':first_order,'payoff_months':payoff,'total_interest':interest_total,
            'total_paid':paid_total,'remaining':sum(balances.values(),ZERO),'timeline':timeline,'status':status})
    return {'version':'debt-model/1','read_only':True,'results':results,
        'assumptions':['Taxas mensais e mínimos são hipóteses declaradas, não dados de um credor.',
            'Juros sobre o principal no início de cada mês, arredondados a centavos; mínimos antes do pagamento extra.',
            'Sem tarifas, novos empréstimos, multas ou descontos presumidos. Prazo máximo explícito.']}
