"""Command Center projections; evidence is data, never model reasoning."""
from typing import Literal
from uuid import UUID
from datetime import date
from pydantic import Field, StrictBool, field_validator
from life_contracts import Contract, Scenario, Domain
from finance_contracts import FinanceScenario


class Why(Contract):
    evidence: list[str] = Field(default_factory=list, max_length=12)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    limitations: list[str] = Field(default_factory=list, max_length=12)
    source: str = Field(max_length=100)


class DayEntry(Contract):
    id: str
    title: str = Field(max_length=300)
    domain: Domain
    link: str = Field(max_length=250)
    start_minute: int = Field(ge=0,le=1440)
    end_minute: int = Field(ge=0,le=1440)
    confirmed: bool
    ambiguous: bool = False
    why: Why


class Attention(Contract):
    id: str
    title: str = Field(max_length=300)
    link: str = Field(max_length=250)
    subtitle: str | None = None
    why: Why


class Area(Contract):
    domain: Domain
    link: str
    facts: dict
    candidate_count: int = Field(ge=0)
    truncated: bool


class CommandHome(Contract):
    version: Literal['command-center/1']
    date: date
    timezone: str
    next_action: DayEntry | None
    today: list[DayEntry] = Field(max_length=12)
    today_count: int = Field(ge=0)
    attention: list[Attention] = Field(max_length=8)
    attention_count: int = Field(ge=0)
    areas: list[Area] = Field(max_length=8)
    planning_safe: bool
    warnings: list[str]
    unscheduled_count: int = Field(ge=0)
    simulation_only: Literal[True]


class Undo(Contract):
    confirmed: StrictBool

    @field_validator('confirmed')
    @classmethod
    def explicit(cls,value):
        if value is not True:raise ValueError('Explicit confirmation required')
        return value


class GlobalScenario(Contract):
    routine: Scenario = Field(default_factory=Scenario)
    finance: FinanceScenario | None = None


class MemoryChange(Contract):
    category: Literal['fact', 'preference', 'decision', 'rule', 'goal', 'context']
    content: str = Field(min_length=1, max_length=1000)
    scope: Literal['global', 'preparation', 'finance', 'training', 'nutrition', 'tasks', 'calendar', 'habits', 'goals'] = 'global'
    expected_version: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class SearchItem(Contract):
    id: UUID
    type: str
    domain: str
    title: str
    subtitle: str
    link: str


class SearchGroup(Contract):
    domain: str
    results: list[SearchItem]
    next_cursor: UUID | None = None


class SearchResults(Contract):
    results: list[SearchItem]
    groups: list[SearchGroup]
    query: str
