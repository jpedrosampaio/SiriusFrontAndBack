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
    def __init__(self, kind='provider_error', retry_after=30):
        self.kind = kind
        self.retry_after = min(300, max(1, retry_after))
        super().__init__(kind)  # Never include provider response/prompt/key.
