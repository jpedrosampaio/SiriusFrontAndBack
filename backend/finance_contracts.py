"""Typed financial analysis boundary. Money stays Decimal until JSON strings."""
from datetime import date as CivilDate
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Money=Annotated[Decimal,Field(ge=0,le=1000000000,max_digits=12,decimal_places=2)]
SignedMoney=Annotated[Decimal,Field(ge=-1000000000,le=1000000000,max_digits=12,decimal_places=2)]


class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


class Obligation(Contract):
    source_id:str
    source_type:Literal['bill','projection','invoice']
    title:str
    category:str
    amount:Decimal
    month:CivilDate
    due_date:CivilDate|None=None
    due_source:Literal['card_configuration','month_only']='month_only'
    card_id:str|None=None
    recurring:bool=False
    estimated:bool=True
    reason:str


class ForecastMonth(Contract):
    month:CivilDate
    recorded_future_income:Decimal
    recorded_future_expense:Decimal
    estimated_expense:Decimal
    scenario_income:Decimal=Decimal('0.00')
    scenario_expense:Decimal=Decimal('0.00')
    net_change:Decimal
    cumulative_change:Decimal
    scenario_balance:Decimal|None=None


class Forecast(Contract):
    version:str='finance-forecast/1'
    as_of:CivilDate
    end:CivilDate
    months:list[ForecastMonth]
    assumptions:list[str]
    read_only:bool=True


class BudgetState(Contract):
    budget_id:str
    category:str
    spent:Decimal
    effective_limit:Decimal|None
    budget_type:Literal['fixed','percentage']
    percentage:Decimal|None=None
    basis:str


class GoalState(Contract):
    goal_id:str
    title:str
    target_date:CivilDate
    progress_percent:Decimal
    monetary_target:Decimal|None=None


class DebtState(Contract):
    card_id:str
    title:str
    known_obligations:Decimal
    monthly_interest_rate:Decimal|None=None
    basis:str='Materialized unpaid obligations in this forecast horizon; not a lender balance.'


class Insight(Contract):
    kind:Literal['category_growth','unusual_increase','budget_overrun','recurring_commitment']
    title:str
    facts:dict
    method:str


class FinanceState(Contract):
    version:str='finance-state/1'
    as_of:CivilDate
    timezone:str
    month:CivilDate
    income:Decimal
    expense:Decimal
    recorded_net:Decimal
    bank_balance:Decimal|None=None
    upcoming_bills:list[Obligation]
    budgets:list[BudgetState]
    recurring_commitments:list[Obligation]
    debts:list[DebtState]
    goals:list[GoalState]
    forecast:Forecast|None
    insights:list[Insight]
    complete:bool
    fingerprint:str
    warnings:list[str]


class PaymentMove(Contract):
    source_id:str=Field(min_length=1,max_length=100)
    date:CivilDate


class FinanceScenario(Contract):
    months:int=Field(default=6,ge=1,le=12,strict=True)
    opening_balance:SignedMoney|None=None
    monthly_income:Money=Decimal('0.00')
    monthly_expense:Money=Decimal('0.00')
    additions_start_offset:int=Field(default=0,ge=0,le=11,strict=True)
    prepayments:list[PaymentMove]=Field(default_factory=list,max_length=50)
    fingerprint:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def unique(self):
        ids=[p.source_id for p in self.prepayments]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate payment source')
        if self.additions_start_offset>=self.months:raise ValueError('Additions start outside horizon')
        return self


class DeclaredDebt(Contract):
    id:str=Field(min_length=1,max_length=80)
    title:str=Field(min_length=1,max_length=120)
    principal:Money
    monthly_rate_percent:Annotated[Decimal,Field(ge=0,le=100,decimal_places=4)]|None=None
    minimum_payment:Money=Decimal('0.00')

    @model_validator(mode='after')
    def positive(self):
        if self.principal<=0:raise ValueError('Positive principal required')
        return self


class DebtScenario(Contract):
    debts:list[DeclaredDebt]=Field(min_length=1,max_length=20)
    monthly_payment:Money
    months:int=Field(default=120,ge=1,le=360,strict=True)
    custom_order:list[str]=Field(default_factory=list,max_length=20)

    @model_validator(mode='after')
    def valid(self):
        ids=[d.id for d in self.debts]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate debt identity')
        if self.monthly_payment<=0:raise ValueError('Positive monthly payment required')
        if self.custom_order and (len(self.custom_order)!=len(ids) or set(self.custom_order)!=set(ids)):
            raise ValueError('Custom order must contain every debt exactly once')
        return self


class DebtMonth(Contract):
    month_number:int=Field(ge=1,le=360)
    payment:Decimal
    interest:Decimal
    remaining:Decimal


class DebtResult(Contract):
    strategy:Literal['snowball','avalanche','custom']
    order:list[str]|None
    payoff_months:int|None=Field(ge=1,le=360)
    total_interest:Decimal|None
    total_paid:Decimal|None
    remaining:Decimal
    timeline:list[DebtMonth]=Field(max_length=360)
    status:Literal['unknown_rates','minimums_exceed_envelope','horizon_reached','paid_in_model']


class DebtComparison(Contract):
    version:str='debt-model/1'
    read_only:Literal[True]=True
    results:list[DebtResult]=Field(min_length=2,max_length=3)
    assumptions:list[str]


class FinanceSimulation(Contract):
    state:FinanceState
    baseline:Forecast
    scenario:Forecast
    read_only:Literal[True]=True
    fingerprint:str
