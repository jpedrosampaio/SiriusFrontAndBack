"""Shared exercise prescription contract; contains no persistence or provider code."""
from pydantic import BaseModel, Field, field_validator


class Exercise(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    sets: int=Field(default=3,ge=1,le=100)
    reps: str=Field(default='12',max_length=100)
    weight: str=Field(default='',max_length=100)
    rest_seconds: int=Field(default=60,ge=0,le=3600)
    muscle_group: str=Field(default='',max_length=300)
    tutorial: str=Field(default='',max_length=20000)
    video_url: str=Field(default='',max_length=2000)
    notes: str=Field(default='',max_length=20000)

    @field_validator('reps','weight',mode='before')
    @classmethod
    def text_number(cls,value): return str(value) if isinstance(value,(int,float)) else value
