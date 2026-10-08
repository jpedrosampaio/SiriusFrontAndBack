from dataclasses import dataclass
from datetime import date
from typing import Literal
from pydantic import Field
from ai.types import StrictModel


class EmptyArgs(StrictModel):
    pass


class TaskArgs(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=2000)
    date: date
    priority: Literal['low', 'medium', 'high'] = 'medium'
    recurrence: Literal['once', 'daily', 'weekly', 'monthly'] = 'once'
    scheduled_time: str | None = Field(default=None, pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    duration_minutes: int | None = Field(default=None, ge=5, le=720, strict=True)


class ExpenseArgs(StrictModel):
    amount: float = Field(gt=0, le=1000000000, allow_inf_nan=False)
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=500)
    date: date


class StudyArgs(StrictModel):
    notebook_id: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(gt=0, le=720, strict=True)
    date: date
    notes: str = Field(default='', max_length=2000)


class CalendarArgs(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    date: date
    start_minute: int = Field(ge=0, lt=1440, strict=True)
    end_minute: int = Field(gt=0, le=1440, strict=True)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: type
    permission: str
    handler: str
    version: int = 1

    def public(self):
        return {'name': self.name, 'version': self.version, 'description': self.description, 'parameters': self.schema.model_json_schema(), 'permission': self.permission}


READS = {
    'get_life_state': 'Estado unificado factual dos oito módulos, disponibilidade e restrições; sem alterações',
    'get_daily_plan': 'Plano de hoje e próximo passo calculados por regras, sem alterar tarefas',
    'get_weekly_review': 'Revisão semanal comparada aos mesmos dias da semana anterior',
    'get_today_tasks': 'Tarefas e conclusões de hoje', 'get_tasks': 'Tarefas que ocorrem hoje',
    'get_habits': 'Hábitos e conclusão de hoje', 'get_finance_summary': 'Receitas, despesas e saldo do mês até hoje',
    'get_budget_status': 'Orçamentos e despesas calculadas por categoria', 'get_study_progress': 'Cadernos e minutos estudados',
    'get_wrong_questions': 'Revisões de tópicos e erros', 'get_next_study_block': 'Próximos blocos de estudo',
    'get_workout_progress': 'Treinos concluídos neste mês', 'get_active_workout': 'Planos de treino disponíveis',
    'get_nutrition_today': 'Consumo nutricional de hoje', 'get_calendar': 'Compromissos fixos de hoje',
    'get_goals': 'Metas e progresso atual', 'get_dashboard_summary': 'Resumo dos módulos', 'get_upcoming_deadlines': 'Prazos das metas',
}
TOOLS = {name: Tool(name, description, EmptyArgs, 'read', name) for name, description in READS.items()}
for name, description, schema in (
    ('create_task', 'Criar uma tarefa; exige confirmação', TaskArgs),
    ('record_expense', 'Registrar uma despesa; exige confirmação', ExpenseArgs),
    ('record_study_session', 'Registrar estudo em caderno existente; exige confirmação', StudyArgs),
    ('create_calendar_event', 'Criar compromisso fixo; exige confirmação', CalendarArgs),
):
    TOOLS[name] = Tool(name, description, schema, 'write', name)


def validate_call(name, arguments):
    if name not in TOOLS:
        raise ValueError('Unknown tool')
    return TOOLS[name].schema.model_validate(arguments).model_dump(mode='json')
