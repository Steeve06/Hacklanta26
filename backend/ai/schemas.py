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


class Rewrite(BaseModel):
    text: str = Field(min_length=10, max_length=240)


class DayPreference(BaseModel):
    weekday: int = Field(ge=0, le=6)
    factor: float = Field(ge=0, le=1)


class FeedbackPrefs(BaseModel):
    days: list[DayPreference] = Field(default_factory=list, max_length=7)
    preferred_hours: list[int] | None = Field(default=None, min_length=2, max_length=2)
    understood: bool = True


class QuestionOut(BaseModel):
    question: str = Field(min_length=8, max_length=220)
    type: Literal["multiple_choice", "true_false"]
    options: list[str] = Field(min_length=2, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=8, max_length=300)
    source_excerpt: str = Field(min_length=10, max_length=400)


class QuestionSet(BaseModel):
    questions: list[QuestionOut] = Field(max_length=20)


class TimeRange(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")


class AssistantAction(BaseModel):
    """One proposed change. Only the fields for its `type` are used; the server checks them."""

    type: Literal[
        "skip_session", "mark_done", "reschedule_session", "move_session", "block_time",
        "set_day_availability", "set_limits", "schedule_note", "rebuild_schedule",
    ]  # fmt: skip
    session_id: int | None = None
    start: str | None = Field(default=None, max_length=25, description="local, YYYY-MM-DDTHH:MM")
    end: str | None = Field(default=None, max_length=25, description="local, YYYY-MM-DDTHH:MM")
    label: str | None = Field(default=None, max_length=60)
    weekday: int | None = Field(default=None, ge=0, le=6)
    blocks: list[TimeRange] | None = Field(default=None, max_length=6)
    max_hours_per_week: float | None = None
    max_hours_per_day: float | None = None
    session_minutes: int | None = None
    earliest_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    latest_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    note: str | None = Field(default=None, max_length=300)


class AssistantTurn(BaseModel):
    reply: str = Field(min_length=1, max_length=900)
    actions: list[AssistantAction] = Field(default_factory=list, max_length=6)
