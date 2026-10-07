"""User-confirmed immutable proposals and atomic, idempotent execution."""
from typing import Literal
from pydantic import Field
from ai.types import StrictModel


class Preferences(StrictModel):
    profile: Literal['conservative', 'balanced', 'proactive'] = 'balanced'
    automations: bool = False
    quiet_start: int = Field(default=22, ge=0, le=23)
    quiet_end: int = Field(default=8, ge=0, le=23)
    daily_cap: int = Field(default=3, ge=0, le=10)
    blocked_tools: list[str] = Field(default_factory=list, max_length=30)


def autonomy(tool, prefs):
    if tool.name in prefs.blocked_tools: return 'BLOCKED'
    if tool.permission == 'read': return 'READ_ONLY'
    if prefs.profile == 'conservative': return 'PROPOSE_ONLY'
    # Proactivity is permission to suggest, never permission to spend or mutate.
    return 'CONFIRM_REQUIRED'
