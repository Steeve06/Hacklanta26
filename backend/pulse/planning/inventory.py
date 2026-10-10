"""Turn a Learning Hub snapshot into the list of unfinished work for one student."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from lms.selectors import AssessmentInfo, ChapterInfo, StudentSnapshot

TYPE_DEFAULT_MINUTES = {"homework": 120, "discussion": 45, "quiz": 30}
CHAPTER_FACTOR = 1.2
CHAPTER_WEIGHT_SHARE = 0.5
CHAPTER_MIN_WEIGHT = 2.0


@dataclass
class WorkItem:
    source_type: str
    source_id: int
    course_id: int
    course_code: str
    kind: str
    title: str
    baseline_minutes: int
    not_before: datetime
    deadline: datetime
    weight: float
    chapter_ids: list[int] = field(default_factory=list)
    late_window: bool = False
    detail: str = ""
    original_posted: bool = False
    replies_required: int = 0
    replies_made: int = 0

    @property
    def ref(self) -> str:
        return f"{self.source_type}:{self.source_id}"

    def content_hash(self) -> str:
        parts = [self.ref, self.kind, self.title, str(self.baseline_minutes), self.detail,
                 ",".join(map(str, self.chapter_ids)), str(self.original_posted)]  # fmt: skip
        return hashlib.sha256("|".join(parts).encode()).hexdigest()


@dataclass
class Excluded:
    source_id: int
    course_code: str
    title: str
    reason: str


@dataclass
class Inventory:
    items: list[WorkItem]
    excluded: list[Excluded]


def baseline_for_assessment(a: AssessmentInfo) -> int:
    return a.est_minutes or TYPE_DEFAULT_MINUTES[a.type]


def baseline_for_chapter(ch: ChapterInfo) -> int:
    return max(10, round(ch.reading_minutes * CHAPTER_FACTOR))


def build_inventory(snapshot: StudentSnapshot, horizon_end: datetime) -> Inventory:
    now = snapshot.now
    items: list[WorkItem] = []
    excluded: list[Excluded] = []
    open_chapters = {c.id: c for c in snapshot.chapters if c.completed_at is None}

    chapter_deadline: dict[int, datetime] = {}
    chapter_weight: dict[int, float] = {}
    for a in snapshot.assessments:
        if a.done or a.status == "missed":
            continue
        for cid in a.chapter_ids:
            if cid in open_chapters:
                chapter_deadline[cid] = min(chapter_deadline.get(cid, a.due_at), a.due_at)
                chapter_weight[cid] = max(chapter_weight.get(cid, 0.0), float(a.weight_pct))

    for a in snapshot.assessments:
        if a.status == "excused" or a.done:
            continue
        if a.status == "missed":
            excluded.append(Excluded(a.id, a.course_code, a.title, "late window closed"))
            continue
        late = now > a.due_at
        deadline = a.closes_at if late else a.due_at
        if a.open_at > horizon_end:
            continue
        items.append(
            WorkItem(
                source_type="assessment",
                source_id=a.id,
                course_id=a.course_id,
                course_code=a.course_code,
                kind=a.type,
                title=a.title,
                baseline_minutes=baseline_for_assessment(a),
                not_before=a.open_at,
                deadline=deadline,
                weight=float(a.weight_pct),
                chapter_ids=[cid for cid in a.chapter_ids if cid in open_chapters],
                late_window=late,
                detail=a.instructions[:400],
                original_posted=a.original_posted,
                replies_required=a.replies_required,
                replies_made=a.replies_made,
            )
        )

    for ch in open_chapters.values():
        if ch.available_from > horizon_end:
            continue
        deadline = chapter_deadline.get(ch.id) or ch.week_end or horizon_end
        deadline = max(deadline, ch.available_from + timedelta(days=2))
        if deadline <= now:
            deadline = now + timedelta(days=7)
        weight = max(CHAPTER_MIN_WEIGHT, chapter_weight.get(ch.id, 0) * CHAPTER_WEIGHT_SHARE)
        items.append(
            WorkItem(
                source_type="chapter",
                source_id=ch.id,
                course_id=ch.course_id,
                course_code=ch.course_code,
                kind="study",
                title=f"Ch {ch.order}: {ch.title}",
                baseline_minutes=baseline_for_chapter(ch),
                not_before=ch.available_from,
                deadline=min(deadline, horizon_end),
                weight=weight,
                detail="; ".join(ch.objectives) + "|" + ch.content_hash,
            )
        )
    return Inventory(items=items, excluded=excluded)
