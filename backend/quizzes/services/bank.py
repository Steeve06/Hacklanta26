"""Per-chapter banks of check cards: model-written questions checked against the chapter text,
with questions built from the chapter's key terms as the fallback and top-up. Every bank also has
"type the missing term" questions from the key terms, for short-answer and matching cards."""

import logging
import random
import re

from django.db import transaction

from ai.client import AIError, available, complete_json, note_fallback
from ai.schemas import QuestionOut, QuestionSet
from lms.models import Chapter

from ..models import CheckQuestion

logger = logging.getLogger(__name__)

TARGET = 12
PER_CALL = 14
MIN_BANK = 8
MAX_CHAPTER_CHARS = 18_000
BOLD = re.compile(r"\*\*([^*]{2,60})\*\*")


def normalize(text: str) -> str:
    text = re.sub(r"[*_`#>|]", "", text)
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def grounded(question: QuestionOut, chapter_text: str) -> bool:
    return normalize(question.source_excerpt) in chapter_text


def valid(question: QuestionOut) -> bool:
    options = [o.strip().lower() for o in question.options]
    if len(set(options)) != len(options):
        return False
    if question.correct_index >= len(options):
        return False
    if question.type == "true_false":
        return options == ["true", "false"]
    return len(options) == 4


def ai_questions(chapter: Chapter) -> list[QuestionOut]:
    corpus = normalize(chapter.body_md)
    kept: list[QuestionOut] = []
    seen: set[str] = set()
    for batch in range(2):
        if len(kept) >= TARGET:
            break
        result = complete_json(
            purpose="study_check", tier="planner", prompt="study_check_v1",
            schema=QuestionSet, max_tokens=4000,
            payload={
                "chapter_title": chapter.title,
                "objectives": chapter.objectives,
                "chapter_text": chapter.body_md[:MAX_CHAPTER_CHARS],
                "count": PER_CALL,
                "batch": batch + 1,
                "avoid": sorted(seen)[:40],
            },
        )  # fmt: skip
        for q in result.questions:
            key = normalize(q.question)
            if key in seen or not valid(q) or not grounded(q, corpus):
                continue
            seen.add(key)
            kept.append(q)
    return kept


def _sentences(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    body = "\n".join(line for line in lines if not line.lstrip().startswith(("#", "|", "-")))
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", body))
    return [p.strip() for p in parts if 40 <= len(p.strip()) <= 260]


def _plain(text: str) -> str:
    return re.sub(r"\*\*|\*|`", "", text)


def cloze_questions(chapter: Chapter, rng: random.Random | None = None) -> list[QuestionOut]:
    """Deterministic questions built from the chapter's bold key terms."""
    rng = rng or random.Random(chapter.content_hash)
    terms = list(dict.fromkeys(t.strip() for t in BOLD.findall(chapter.body_md)))
    sentences = [s for s in _sentences(chapter.body_md) if BOLD.search(s)]
    questions: list[QuestionOut] = []
    for sentence in sentences:
        term = BOLD.search(sentence).group(1).strip()
        distractors = [
            t for t in terms if term.lower() not in t.lower() and t.lower() not in term.lower()
        ]
        if len(distractors) < 3:
            continue
        plain = _plain(sentence)
        blanked = _plain(sentence.replace(f"**{term}**", "_____", 1))
        options = [term, *rng.sample(distractors, 3)]
        rng.shuffle(options)
        questions.append(
            QuestionOut(
                question=f"Fill in the blank: {blanked}"[:220],
                type="multiple_choice",
                options=options,
                correct_index=options.index(term),
                explanation=plain[:300],
                source_excerpt=plain[:400],
            )
        )
        if len(questions) % 3 == 0:
            swap = rng.choice(distractors)
            false_statement = _plain(sentence.replace(f"**{term}**", swap, 1))
            truthful = len(questions) % 2 == 0
            questions.append(
                QuestionOut(
                    question=f"True or false: {plain if truthful else false_statement}"[:220],
                    type="true_false",
                    options=["True", "False"],
                    correct_index=0 if truthful else 1,
                    explanation=f"The chapter says: {plain}"[:300],
                    source_excerpt=plain[:400],
                )
            )
        if len(questions) >= TARGET:
            break
    for objective in chapter.objectives:
        if len(questions) >= TARGET:
            break
        siblings = Chapter.objects.filter(course=chapter.course).exclude(pk=chapter.pk)
        others = [o for c in siblings for o in c.objectives]
        if len(others) < 3:
            break
        options = [objective, *rng.sample(others, 3)]
        rng.shuffle(options)
        questions.append(
            QuestionOut(
                question=f"Which of these is a learning objective of “{chapter.title}”?",
                type="multiple_choice",
                options=[o[:200] for o in options],
                correct_index=options.index(objective),
                explanation=f"“{objective}” is one of this chapter's objectives.",
                source_excerpt=f"Learning objective: {objective}"[:400],
            )
        )
    return [q for q in questions if valid(q)]


def term_questions(chapter: Chapter) -> list[CheckQuestion]:
    """One short answer per key term: the sentence that introduces it, with the term blanked."""
    rows: list[CheckQuestion] = []
    seen: set[str] = set()
    for sentence in _sentences(chapter.body_md):
        match = BOLD.search(sentence)
        if not match:
            continue
        term = match.group(1).strip()
        if term.lower() in seen or len(term) > 60:
            continue
        seen.add(term.lower())
        plain = _plain(sentence)
        rows.append(
            CheckQuestion(
                chapter=chapter,
                type=CheckQuestion.Type.SHORT_ANSWER,
                prompt=_plain(sentence.replace(match.group(0), "_____", 1))[:260],
                answer=_plain(term),
                explanation=plain[:300],
                source_excerpt=plain[:400],
                content_hash=chapter.content_hash,
                origin=CheckQuestion.Origin.TERM,
            )  # fmt: skip
        )
        if len(rows) >= TARGET:
            break
    return rows


def ensure_terms(chapter: Chapter) -> None:
    if not usable(chapter).filter(origin=CheckQuestion.Origin.TERM).exists():
        CheckQuestion.objects.bulk_create(term_questions(chapter))


def _rows(chapter: Chapter, questions: list[QuestionOut], origin: str) -> list[CheckQuestion]:
    return [
        CheckQuestion(
            chapter=chapter,
            type=q.type,
            prompt=q.question,
            options=q.options,
            correct_index=q.correct_index,
            explanation=q.explanation,
            source_excerpt=q.source_excerpt,
            content_hash=chapter.content_hash,
            origin=origin,
        )  # fmt: skip
        for q in questions
    ]


def rebuild_bank(chapter: Chapter, *, allow_ai: bool = True) -> int:
    """Retire cards from older versions of the chapter and fill the bank for the current text.
    The model call runs outside any transaction; only the writes are atomic. `allow_ai=False`
    builds key-term cards only, for when a student is waiting."""
    stale = CheckQuestion.objects.filter(chapter=chapter).exclude(content_hash=chapter.content_hash)
    stale.update(retired=True)
    ensure_terms(chapter)
    use_ai = allow_ai and available()
    if not needs_cards(chapter, use_ai=use_ai):
        return 0
    written: list[QuestionOut] = []
    if use_ai:
        try:
            written = ai_questions(chapter)
        except AIError as exc:
            note_fallback("study_check", str(exc))
    rows = _rows(chapter, written, CheckQuestion.Origin.AI)
    upgrade = len(rows) >= MIN_BANK
    if not upgrade:
        seen = {normalize(q.question) for q in written}
        extra = [q for q in cloze_questions(chapter) if normalize(q.question) not in seen]
        rows += _rows(chapter, extra[: TARGET - len(rows)], CheckQuestion.Origin.CLOZE)
    with transaction.atomic():
        current = choices(chapter)
        if upgrade:
            # Model-written cards replace key-term ones; past answers keep their questions.
            current.filter(origin=CheckQuestion.Origin.CLOZE).update(retired=True)
        elif current.count() >= MIN_BANK:
            return 0
        CheckQuestion.objects.bulk_create(rows)
    return len(rows)


def needs_cards(chapter: Chapter, *, use_ai: bool) -> bool:
    """True when the bank is short of option questions, or only has key-term ones and the model
    is available."""
    current = choices(chapter)
    if current.count() < MIN_BANK:
        return True
    return use_ai and not current.filter(origin=CheckQuestion.Origin.AI).exists()


def usable(chapter: Chapter):
    return CheckQuestion.objects.filter(
        chapter=chapter, content_hash=chapter.content_hash, retired=False
    )


def choices(chapter: Chapter):
    """The bank's option questions (multiple choice and true/false)."""
    return usable(chapter).exclude(type=CheckQuestion.Type.SHORT_ANSWER)
