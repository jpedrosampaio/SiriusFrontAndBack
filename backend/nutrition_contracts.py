"""Owned nutrition projections and declared scenario inputs; no clinical inference."""
from datetime import date as Date
from decimal import Decimal
from typing import Literal, Annotated
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class MacroValue(Contract):
    registered: str
    estimated: str
    legacy_unverified: str
    known_total: str
    total: str | None
    unknown_items: int
    unit: Literal['kcal', 'g']


class NutritionState(Contract):
    date: Date
    timezone: str
    consumed: dict[str, MacroValue]
    goals: dict | None
    remaining: dict[str, str | None]
    meals: list[dict]
    water_ml: int
    consistency: dict
    planned: list[dict]
    training_context: list[dict]
    routine_context: list[dict]
    preferences: dict
    limitations: list[str]
    truncated: bool


class Price(Contract):
    food: str = Field(min_length=1, max_length=300)
    unit: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(ge=0, le=1000000, decimal_places=2, allow_inf_nan=False)
    source: Literal['known', 'estimated']
    currency: Literal['BRL'] = 'BRL'


class NutritionPreferences(Contract):
    favorite_meals: list[UUID] = Field(default_factory=list, max_length=50)
    available_foods: list[Annotated[str, Field(min_length=1, max_length=300)]] | None = Field(default=None, max_length=100)
    excluded_foods: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(default_factory=list, max_length=100)
    budget: Decimal | None = Field(default=None, gt=0, le=1000000, decimal_places=2, allow_inf_nan=False)
    budget_period: Literal['daily', 'weekly'] = 'weekly'
    prices: list[Price] = Field(default_factory=list, max_length=100)


class MealScenario(Contract):
    template_kind: Literal['meal', 'planned', 'recipe'] = 'meal'
    finance_budget_id: UUID | None = None
    date: Date | None = None
    days: int = Field(default=1, ge=1, le=7, strict=True)
    portions: Decimal = Field(default=Decimal('1'), ge=Decimal('0.25'), le=4, decimal_places=2, allow_inf_nan=False)
    within_budget: bool = False
    available_only: bool = False
    meal_type: Literal['breakfast', 'lunch', 'dinner', 'snack'] | None = None
    template_id: UUID | None = None


class RepeatMeal(Contract):
    meal_type: Literal['breakfast', 'lunch', 'dinner', 'snack'] | None = None
    date: Date
    portions: Decimal = Field(default=Decimal('1'), ge=Decimal('0.25'), le=4, decimal_places=2, allow_inf_nan=False)


class MealAlternatives(Contract):
    date: Date
    candidates: list[dict]
    organization: list[dict]
    budget: dict | None
    limitations: list[str]
    automatic: Literal[False] = False
    truncated: bool
