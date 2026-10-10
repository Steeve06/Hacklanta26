"""Per-chapter question banks: AI questions checked against the chapter text, cloze fallback."""

import logging
import random
import re

from django.db import transaction

from ai.client import AIError, available, complete_json, note_fallback
from ai.schemas import QuestionOut, QuestionSet
from lms.models import Chapter

from ..models import BankQuestion

logger = logging.getLogger(__name__)

TARGET = 30
PER_CALL = 15
MIN_BANK = 5
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
    for batch in range(TARGET // PER_CALL):
        result = complete_json(
            purpose="quiz_questions", tier="planner", prompt="quiz_questions_v1",
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
                question=f"Fill in the blank: {blanked}"[:300],
                type="multiple_choice",
                options=options,
                correct_index=options.index(term),
                explanation=plain[:400],
                source_excerpt=plain[:400],
            )
        )
        if len(questions) % 3 == 0:
            swap = rng.choice(distractors)
            false_statement = _plain(sentence.replace(f"**{term}**", swap, 1))
            truthful = len(questions) % 2 == 0
            questions.append(
                QuestionOut(
                    question=f"True or false: {plain if truthful else false_statement}"[:300],
                    type="true_false",
                    options=["True", "False"],
                    correct_index=0 if truthful else 1,
                    explanation=f"The chapter says: {plain}"[:400],
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


@transaction.atomic
def rebuild_bank(chapter: Chapter) -> int:
    """Retire questions from older versions of the chapter and build a fresh bank."""
    BankQuestion.objects.filter(chapter=chapter).exclude(content_hash=chapter.content_hash).update(
        retired=True
    )
    current = BankQuestion.objects.filter(
        chapter=chapter, content_hash=chapter.content_hash, retired=False
    )
    if current.count() >= MIN_BANK:
        return 0
    origin = BankQuestion.Origin.AI
    questions: list[QuestionOut] = []
    if available():
        try:
            questions = ai_questions(chapter)
        except AIError as exc:
            note_fallback("quiz_questions", str(exc))
    if len(questions) < MIN_BANK:
        questions, origin = cloze_questions(chapter), BankQuestion.Origin.CLOZE
    BankQuestion.objects.bulk_create(
        BankQuestion(
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
    )
    return len(questions)


def usable(chapter: Chapter):
    return BankQuestion.objects.filter(
        chapter=chapter, content_hash=chapter.content_hash, retired=False
    )
