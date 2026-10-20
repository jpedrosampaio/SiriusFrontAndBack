from dataclasses import dataclass, field
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ToolCall(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)


@dataclass
class AIRequest:
    task: str
    prompt: str
    system: str = ''
    messages: list = field(default_factory=list)
    parts: list = field(default_factory=list)
    schema: dict | None = None
    tools: list = field(default_factory=list)
    max_tokens: int = 4096
    timeout: int = 45
    audio: bytes | None = None
    mime: str = 'audio/webm'
    transport_schema: dict | None = None


@dataclass
class AIResult:
    text: str = ''
    provider: str = ''
    model: str = ''
    usage: dict = field(default_factory=dict)
    data: Any = None
    tool_calls: list = field(default_factory=list)
    fallback: bool = False


class AIError(Exception):
    def __init__(self, kind='provider_error', retry_after=30, *, http_status=None, incompatibility=None, reason=None, reference=None, attempted=False):
        from uuid import uuid4
        self.kind = kind
        self.retry_after = min(300, max(1, retry_after))
        self.http_status=http_status if isinstance(http_status,int) and 100<=http_status<=599 else None
        self.incompatibility=incompatibility if incompatibility in ('schema_keyword','schema_reference','schema_complexity','schema_feature','schema_rejected','model_capability','request_rejected') else None
        self.reason=reason if reason in ('cooldown','no_compatible_route','payload_rejected','pilot_limit') else None
        self.reference=reference or str(uuid4())
        self.attempted=attempted
        super().__init__(kind)  # Never include provider response/prompt/key.
