"""Read-only training projections; missing evidence stays unknown."""
from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TrainingAlert(Contract):
    code: str
    reason: str
    evidence_dates: list[date] = Field(default_factory=list)


class TrainingRecord(Contract):
    kind: Literal['max_load', 'max_volume', 'load_at_reps']
    value: str
    date: date
    log_id: UUID
    reps: int | None = None
    scope: str = 'analysis_window'


class Progression(Contract):
    action: Literal['insufficient_data', 'maintain', 'review_increase']
    reason: str
    current_weight: str | None = None
    suggested_weight: str | None = None
    evidence_dates: list[date] = Field(default_factory=list)
    automatic: Literal[False] = False


class ExecutionHistory(Contract):
    date: date
    log_id: UUID
    plan_id: UUID | None
    prescribed_sets: int
    target_reps: str
    recorded_sets: int
    legacy_sets_without_details: int
    known_volume: str
    volume: str | None
    max_load: str | None
    average_rpe: float | None


class TrainingWeek(Contract):
    week_start: date
    workouts: int
    training_days: int


class MuscleVolume(Contract):
    name: str
    recorded_sets: int
    known_volume: str
    volume: str | None


class ExerciseState(Contract):
    key: str
    name: str
    muscle_group: str | None
    executions: int
    recorded_sets: int
    prescribed_sets: int
    known_volume: str
    volume: str | None
    rpe_samples: int
    average_rpe: float | None
    records: list[TrainingRecord]
    progression: Progression
    alerts: list[TrainingAlert]
    history: list[ExecutionHistory]


class TrainingState(Contract):
    version: Literal[1] = 1
    as_of: date
    start: date
    timezone: str
    truncated: bool
    completed_workouts: int
    analyzed_workouts: int
    training_days: int
    recorded_minutes: int
    weekly_frequency: list[TrainingWeek]
    set_adherence: float | None
    scheduled_adherence: None = None
    exercises: list[ExerciseState]
    muscle_groups: list[MuscleVolume]
    alerts: list[TrainingAlert]
    limitations: list[str]


class SubstitutionArgs(Contract):
    plan_id: UUID
    day_index: int = Field(ge=0, le=1000, strict=True)
    exercise_index: int = Field(ge=0, le=499, strict=True)


class Substitution(Contract):
    name: str
    muscle_group: str
    objective: str
    movement: str | None
    movement_confirmed: bool
    source_plan_id: UUID
    reason: str


class SubstitutionResult(Contract):
    exercise: str
    objective: str | None
    movement: str | None
    suggestions: list[Substitution]
    limitations: list[str]
    truncated: bool = False
    automatic: Literal[False] = False
