"""Event/automation boundary. Rules describe facts, never permissions to mutate a domain."""
from datetime import date as CivilDate, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

CATALOG = {
    'task.overdue': ('tasks', 'Tarefa pendente', '/tasks'),
    'task.completed': ('tasks', 'Tarefa concluída', '/tasks'),
    'study.session.completed': ('preparation', 'Sessão de estudo concluída', '/studies'),
    'study.review.overdue': ('preparation', 'Revisão vencida', '/studies'),
    'study.block.missed': ('preparation', 'Bloco de estudo pendente', '/studies'),
    'question.failed': ('preparation', 'Erros recorrentes', '/studies'),
    'exam.approaching': ('preparation', 'Prova se aproximando', '/studies'),
    'edital.updated': ('preparation', 'Atualização de edital registrada', '/studies'),
    'workout.completed': ('training', 'Treino concluído', '/workouts'),
    'expense.created': ('finance', 'Despesa registrada', '/finance'),
    'budget.exceeded': ('finance', 'Orçamento excedido', '/finance'),
    'budget.threshold_reached': ('finance', 'Orçamento próximo do limite', '/finance'),
    'bill.due': ('finance', 'Obrigação próxima do vencimento', '/finance'),
    'goal.off_track': ('goals', 'Prazo da meta vencido', '/goals'),
    'nutrition.target_remaining': ('nutrition', 'Meta alimentar confirmada ainda não atingida', '/nutrition'),
    'brief.daily': ('routine', 'Resumo integrado do dia', '/notifications'),
    'review.night': ('routine', 'Revisão do dia', '/notifications'),
    'coach.weekly': ('routine', 'Revisão semanal', '/notifications'),
}
ALIASES = {'finance.expense.created': 'expense.created'}
TRANSITIONS = frozenset(('task.completed','study.session.completed','workout.completed','expense.created','edital.updated'))


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Rule(Contract):
    enabled: bool = True
    frequency: Literal['daily', 'weekly'] = 'daily'
    priority: Literal['low', 'medium', 'high'] = 'medium'
    channels: list[Literal['in_app', 'telegram']] = Field(default_factory=lambda: ['in_app'], min_length=1, max_length=2)

    @field_validator('channels')
    @classmethod
    def unique_channels(cls, value):
        if len(value) != len(set(value)): raise ValueError('Canais duplicados')
        return value


class AutomationPolicy(Contract):
    routine_popups: bool = Field(default=False,strict=True)
    # None inherits the existing Agent preference; there is one opt-in policy.
    quiet_start: str | None = None
    quiet_end: str | None = None
    morning_time: str = '08:00'
    night_time: str = '21:00'
    weekly_time: str = '18:00'
    weekly_weekday: int = Field(default=6, ge=0, le=6, strict=True)
    rules: dict[str, Rule] = Field(default_factory=dict, max_length=len(CATALOG))

    @field_validator('quiet_start', 'quiet_end', 'morning_time', 'night_time', 'weekly_time')
    @classmethod
    def valid_time(cls, value):
        import re
        if value is not None and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
            raise ValueError('Use HH:MM')
        return value

    @field_validator('rules')
    @classmethod
    def known_rules(cls, value):
        if not set(value).issubset(CATALOG): raise ValueError('Regra desconhecida')
        return value


class PolicyUpdate(Contract):
    enabled: bool
    daily_cap: int = Field(default=3, ge=0, le=10, strict=True)
    policy: AutomationPolicy


class EventCandidate(Contract):
    event_type: str
    entity_type: str = Field(max_length=80)
    entity_id: UUID | None = None
    occurrence: str = Field(min_length=1, max_length=160)
    facts: dict = Field(default_factory=dict)
    reasons: list[str] = Field(min_length=1, max_length=8)

    @field_validator('event_type')
    @classmethod
    def known_type(cls, value):
        if value not in CATALOG: raise ValueError('Evento desconhecido')
        return value


class Briefing(Contract):
    version: str = 'event-briefing/2'
    mode: Literal['morning', 'night', 'weekly']
    date: CivilDate
    timezone: str
    generated_at: datetime
    facts: dict
    proposals: list[dict] = Field(default_factory=list, max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    read_only: bool = True
    confirmation_required: bool = True
