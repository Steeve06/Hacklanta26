from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class TaskSpec:
    """One unit of study work the solver must place. Minutes are what is still left to do."""

    key: str
    source_type: str
    source_id: int
    part: str
    course_id: int
    course_code: str
    title: str
    kind: str
    minutes: int
    min_chunk: int
    splittable: bool
    not_before: datetime
    deadline: datetime
    weight: float
    depends_on: list[str] = field(default_factory=list)
    lag_after_deps: timedelta = timedelta(0)
    chapter_id: int | None = None
    late_window: bool = False
    reportable: bool = True


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class Placement:
    task_key: str
    start: datetime
    end: datetime
    day: date
    course_id: int
    kind: str
    pinned: bool = False
    at_risk: bool = False
    session_id: int | None = None
    quiz_keys: tuple[str, ...] = ()

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class Preferences:
    day_factor: dict[int, float] = field(default_factory=dict)
    preferred_hours: tuple[int, int] | None = None
    productive_hours: frozenset[int] = frozenset()


@dataclass
class Constraints:
    tz: object
    now: datetime
    horizon_end: datetime
    max_minutes_per_day: int
    session_minutes: int
    break_minutes: int = 10
    slack_ratio: float = 0.15
    max_same_course_per_day: int = 2


@dataclass
class Shortfall:
    task_key: str
    minutes: int


@dataclass
class SolveResult:
    placements: list[Placement]
    shortfalls: list[Shortfall]
    at_risk: set[str]
    iterations: int
    elapsed_ms: int
    penalty: float
