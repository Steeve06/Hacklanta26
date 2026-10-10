"""Splitting work items into study tasks. The heuristic is also the fallback for the AI path."""

from dataclasses import dataclass, field

from .inventory import WorkItem

REPLY_LAG_HOURS = 24


@dataclass
class TaskDraft:
    ref: str
    part: str
    title: str
    est_minutes: int
    depends_on: list[str] = field(default_factory=list)
    min_chunk: int = 25
    splittable: bool = True
    lag_hours: int = 0
    ai_generated: bool = False

    @property
    def key(self) -> str:
        return f"{self.ref}:{self.part}"


def chapter_key(chapter_id: int) -> str:
    return f"chapter:{chapter_id}:read"


def heuristic_decompose(item: WorkItem) -> list[TaskDraft]:
    code = item.course_code
    chapter_deps = [chapter_key(cid) for cid in item.chapter_ids]
    minutes = item.baseline_minutes
    if item.kind == "study":
        return [
            TaskDraft(
                item.ref,
                "read",
                f"{code} · Read {item.title}",
                minutes,
                min_chunk=min(25, minutes),
                splittable=minutes > 30,
            )  # fmt: skip
        ]
    if item.kind == "homework":
        if minutes <= 60:
            return [
                TaskDraft(item.ref, "complete", f"{code} · {item.title}", minutes, chapter_deps)
            ]
        draft = round(minutes * 0.6)
        return [
            TaskDraft(item.ref, "draft", f"{code} · Draft {item.title}", draft, chapter_deps),
            TaskDraft(
                item.ref,
                "finish",
                f"{code} · Finish and submit {item.title}",
                minutes - draft,
                [f"{item.ref}:draft"],
            ),  # fmt: skip
        ]
    if item.kind == "discussion":
        original = max(20, round(minutes * 0.6))
        replies = max(15, minutes - original)
        drafts = []
        if not item.original_posted:
            drafts.append(
                TaskDraft(
                    item.ref,
                    "original",
                    f"{code} · Write original post: {item.title}",
                    original,
                    chapter_deps,
                    min_chunk=original,
                    splittable=False,
                )  # fmt: skip
            )
        if item.replies_made < item.replies_required:
            drafts.append(
                TaskDraft(
                    item.ref,
                    "replies",
                    f"{code} · Reply to classmates: {item.title}",
                    replies,
                    [f"{item.ref}:original"] if not item.original_posted else [],
                    min_chunk=replies,
                    splittable=False,
                    lag_hours=REPLY_LAG_HOURS,
                )  # fmt: skip
            )
        return drafts
    return [
        TaskDraft(
            item.ref,
            "take",
            f"{code} · Review and take {item.title}",
            minutes,
            chapter_deps,
            min_chunk=minutes,
            splittable=False,
        )  # fmt: skip
    ]
