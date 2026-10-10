from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Candidate:
    trigger: str
    tier: int
    source_type: str
    source_id: int
    course_id: int | None
    variables: dict = field(default_factory=dict)
    link: str = ""
    due_at: datetime | None = None
    gentle: bool = False
