"""Additive preparations, individual evidence and unified review queue.

Existing programs are canonical; a target adds identity/capabilities without
copying notebooks, schedules or edital content.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4,UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Cookie, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from study_mastery import mastery, adaptive_review

ERROR_REASONS = Literal['unknown', 'forgot', 'interpretation', 'attention', 'concepts', 'calculation', 'legislation', 'other',
    'knowledge_gap','concept_confusion','memory','time_management']


class TargetInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=180)
    kind: Literal['contest', 'certification', 'academic', 'course', 'custom'] = 'custom'
    program_id: Optional[str] = Field(default=None, max_length=100)
    institution: str = Field(default='', max_length=180)
    board: str = Field(default='', max_length=100)
    edition: str = Field(default='', max_length=80)
    position: str = Field(default='', max_length=180)
    exam_date: Optional[date] = None


class AttemptInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    notebook_id: str = Field(min_length=1, max_length=100)
    topic_key: str = Field(pattern=r'^\d+(?:_\d+)?$')
    question: str = Field(min_length=1, max_length=12000)
    answer: str = Field(default='', max_length=4000)
    correct: StrictBool
    seconds: int = Field(default=0, ge=0, le=86400)
    source: str = Field(default='manual', max_length=200)
    board: str = Field(default='', max_length=100)
    exam: str = Field(default='', max_length=180)
    position: str = Field(default='', max_length=180)
    question_id: Optional[str] = Field(default=None, max_length=100)
    error_reason: Optional[ERROR_REASONS] = None
    difficulty: Optional[Literal['easy', 'medium', 'hard']] = None
    confidence: Optional[Literal['guess','uncertain','confident']] = None
    skipped: StrictBool = False
    changed_answer: Optional[StrictBool] = None
    internal_question_id: Optional[str] = Field(default=None,max_length=100)


class ErrorUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: ERROR_REASONS


class BlueprintInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=180)
    duration_minutes: int = Field(ge=1, le=600)
    mode: Literal['edital','discipline','topics','weak','quick'] = 'edital'
    notebook_ids: list[UUID] = Field(default_factory=list,max_length=100)
    topic_ids: list[UUID] = Field(default_factory=list,max_length=100)
    num_questions: int = Field(default=20,ge=1,le=200)
    confirm_provisional: bool = False
    wrong_penalty: float = Field(default=0,ge=0,le=100,allow_inf_nan=False)
    blank_penalty: float = Field(default=0,ge=0,le=100,allow_inf_nan=False)
    scoring_source: str = Field(default='',max_length=500)
    scoring_excerpt: str = Field(default='',max_length=2000)
    confirm_scoring_source: bool = False


def topic_title(notebook, key):
    topics = notebook.get('conteudo_programatico') or notebook.get('topicos') or []
    indexes = [int(v) for v in key.split('_')]
    if indexes[0] >= len(topics):
        raise HTTPException(422, 'Assunto não encontrado.')
    item = topics[indexes[0]]
    if len(indexes) == 2:
        children = item.get('subtopicos', []) if isinstance(item, dict) else []
        if indexes[1] >= len(children): raise HTTPException(422, 'Subtópico não encontrado.')
        return str(children[indexes[1]])[:500]
    return str(item.get('assunto', '') if isinstance(item, dict) else item)[:500]
