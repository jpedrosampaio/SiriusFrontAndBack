"""Versioned module boundary. No persistence or cross-domain imports."""
from datetime import date as CivilDate
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

Domain = Literal['preparation', 'finance', 'training', 'nutrition', 'tasks', 'calendar', 'habits', 'goals']


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Window(Contract):
    start_minute: int = Field(ge=0, lt=1440, strict=True)
    end_minute: int = Field(gt=0, le=1440, strict=True)

    @model_validator(mode='after')
    def ordered(self):
        if self.end_minute <= self.start_minute:
            raise ValueError('Window end must follow start')
        return self


class Availability(Contract):
    # Python weekday: Monday=0. Empty means no declared availability.
    weekdays: list[list[Window]] = Field(default_factory=lambda: [[] for _ in range(7)], min_length=7, max_length=7)
    duration_estimates: dict[Domain, StrictInt] = Field(default_factory=dict, max_length=8)
    training_plan_id: UUID | None = None
    training_weekdays: list[StrictInt] = Field(default_factory=list, max_length=7)

    @model_validator(mode='after')
    def bounded(self):
        for windows in self.weekdays:
            if len(windows) > 4:
                raise ValueError('At most four windows per day')
            ordered = sorted(windows, key=lambda w: w.start_minute)
            if any(a.end_minute > b.start_minute for a, b in zip(ordered, ordered[1:])):
                raise ValueError('Availability windows cannot overlap')
        if any(type(v) is not int or not 5 <= v <= 720 for v in self.duration_estimates.values()):
            raise ValueError('Estimates must be integer minutes from 5 to 720')
        if any(not 0<=v<=6 for v in self.training_weekdays) or len(set(self.training_weekdays))!=len(self.training_weekdays):
            raise ValueError('Training weekdays must be unique values from 0 to 6')
        return self


class Candidate(Contract):
    id: str = Field(min_length=1, max_length=160)
    domain: Domain
    source_id: str = Field(max_length=80)
    scope_id: str | None = Field(default=None, max_length=80)
    action_type: str = Field(max_length=40)
    title: str = Field(max_length=300)
    duration_minutes: int | None = Field(default=None, gt=0, le=1440, strict=True)
    duration_origin: Literal['recorded', 'user_estimate', 'unknown'] = 'unknown'
    earliest: CivilDate
    latest: CivilDate
    priority: Literal['low', 'medium', 'high'] = 'medium'
    date_locked: bool = False
    reasons: list[str] = Field(default_factory=list, max_length=8)
    link: str = Field(max_length=250)


class Constraint(Window):
    id: str = Field(max_length=160)
    title: str = Field(max_length=300)
    domain: Domain
    scope_id: str | None = Field(default=None, max_length=80)
    reason: str = Field(max_length=300)


class DomainState(Contract):
    domain: Domain
    # Bounded, documented facts from canonical aggregates; no copied histories.
    facts: dict = Field(default_factory=dict)
    candidates: list[Candidate] = Field(default_factory=list, max_length=200)
    constraints: list[Constraint] = Field(default_factory=list, max_length=1000)
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list, max_length=20)


class LifeState(Contract):
    version: str = 'life-state/1'
    date: CivilDate
    timezone: str
    availability: Availability
    domains: list[DomainState]
    fingerprint: str
    planning_safe: bool
    warnings: list[str]


class Scenario(Contract):
    date: CivilDate | None = None
    windows: list[Window] | None = Field(default=None, max_length=4)
    capacity_minutes: int | None = Field(default=None, ge=0, le=1440, strict=True)
    exclude: list[str] = Field(default_factory=list, max_length=200)
    durations: dict[str, StrictInt] = Field(default_factory=dict, max_length=200)

    @model_validator(mode='after')
    def validate_scenario(self):
        if self.windows is not None:
            Availability(weekdays=[self.windows] + [[] for _ in range(6)])
        if any(type(v) is not int or not 5 <= v <= 720 for v in self.durations.values()):
            raise ValueError('Duration overrides require 5-720 integer minutes')
        return self


class Allocation(Window):
    task_id: str = Field(max_length=160)
    candidate_id: str = Field(max_length=160)
    source_id: UUID
    domain: Domain
    title: str = Field(max_length=300)
    kind: Literal['flexible_task']
    duration_minutes: int = Field(gt=0, le=1440, strict=True)
    duration_estimated: bool
    duration_origin: Literal['recorded', 'user_estimate']
    date_locked: bool
    link: str = Field(max_length=250)
    reasons: list[str] = Field(max_length=8)
    reason: str = Field(max_length=500)
