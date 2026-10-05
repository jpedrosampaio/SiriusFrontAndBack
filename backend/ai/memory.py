import hashlib
from typing import Literal
from pydantic import Field
from ai.types import StrictModel


class MemoryInput(StrictModel):
    category: Literal['preference', 'rule', 'goal', 'context']
    content: str = Field(min_length=1, max_length=1000)


def fingerprint(content):
    return hashlib.sha256(' '.join(content.casefold().split()).encode()).hexdigest()
