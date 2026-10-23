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
    def __init__(self, kind='provider_error', retry_after=30, *, http_status=None, incompatibility=None, reason=None, reference=None, attempted=False,
                 request_format=None,schema_sha256=None,schema_bytes=None,provider_rejection=None,response_validation=None):
        from uuid import uuid4
        self.kind = kind
        self.retry_after = min(300, max(1, retry_after))
        self.http_status=http_status if isinstance(http_status,int) and 100<=http_status<=599 else None
        self.incompatibility=incompatibility if incompatibility in ('schema_keyword','schema_reference','schema_complexity','schema_feature','schema_rejected','model_capability','request_rejected','format_field','format_mime') else None
        self.reason=reason if reason in ('cooldown','no_compatible_route','payload_rejected','pilot_limit') else None
        self.reference=reference or str(uuid4())
        self.attempted=attempted
        self.request_format=request_format if request_format in ('gemini_response_format','groq_json_schema') else None
        self.schema_sha256=schema_sha256 if isinstance(schema_sha256,str) and len(schema_sha256)==64 and all(c in '0123456789abcdef' for c in schema_sha256) else None
        self.schema_bytes=schema_bytes if isinstance(schema_bytes,int) and 0<schema_bytes<=60000 else None
        from ai.provider_diagnostics import safe_rejection
        self.provider_rejection=safe_rejection(provider_rejection)
        from ai.validation_diagnostics import safe_validation
        self.response_validation=safe_validation(response_validation)
        super().__init__(kind)  # Never include provider response/prompt/key.
