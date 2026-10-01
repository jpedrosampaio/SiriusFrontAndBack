"""Validated study workspace payloads, shared with isolated contract tests."""
from datetime import date as CalendarDate
from typing import Optional
from pydantic import BaseModel, Field

class DraftUpdate(BaseModel):
    text: str = Field(max_length=100000)
    revision: int = Field(ge=0)


class PlanSettings(BaseModel):
    start_date: CalendarDate
    end_date: CalendarDate
    availability: list[int] = Field(min_length=7, max_length=7)
    block_minutes: int = Field(default=50, ge=15, le=120)
    adaptive: bool = False


class TopicPractice(BaseModel):
    topic_key: str = Field(pattern=r'^\d+(?:_\d+)?$')
    total: int = Field(ge=1, le=1000)
    correct: int = Field(ge=0, le=1000)


class PlanEntryUpdate(BaseModel):
    completed: Optional[bool] = None
    date: Optional[CalendarDate] = None
