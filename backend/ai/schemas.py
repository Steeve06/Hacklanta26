from typing import Literal

from pydantic import BaseModel, Field


class StudyTaskOut(BaseModel):
    source_type: Literal["chapter", "assessment"]
    source_id: int
    part: str = Field(pattern=r"^[a-z][a-z0-9_]{0,30}$")
    title: str = Field(min_length=3, max_length=140)
    est_minutes: int = Field(ge=5, le=900)
    depends_on: list[str] = Field(default_factory=list, max_length=12)
    min_chunk_minutes: int = Field(ge=5, le=180)
    splittable: bool


class Decomposition(BaseModel):
    tasks: list[StudyTaskOut] = Field(max_length=80)


class SessionTitle(BaseModel):
    index: int = Field(ge=0)
    title: str = Field(min_length=3, max_length=80)


class Polish(BaseModel):
    titles: list[SessionTitle] = Field(max_length=60)
    summary: str = Field(min_length=10, max_length=400)


class QuestionOut(BaseModel):
    question: str = Field(min_length=8, max_length=300)
    type: Literal["multiple_choice", "true_false"]
    options: list[str] = Field(min_length=2, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=8, max_length=400)
    source_excerpt: str = Field(min_length=10, max_length=400)


class QuestionSet(BaseModel):
    questions: list[QuestionOut] = Field(max_length=20)


class Rewrite(BaseModel):
    text: str = Field(min_length=10, max_length=240)
