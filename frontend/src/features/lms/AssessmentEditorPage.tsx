import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError, errorMessage, unwrap } from "@/api/client";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import {
  Button,
  ConfirmModal,
  Input,
  QueryView,
  Select,
  SkeletonLines,
  Textarea,
  toast,
} from "@/components/ui";
import { fromLocalInputValue, toLocalInputValue, useTimezone } from "@/lib/time";
import {
  lmsKeys,
  useAssessment,
  useChapters,
  useQuestions,
  type AssessmentDetail,
  type ChapterSummary,
  type QuestionWrite,
} from "./api";
import { useNumericParam } from "./useIds";

type DraftQuestion = {
  prompt: string;
  type: "multiple_choice" | "true_false";
  options: string;
  correct_index: number;
};

export function AssessmentEditorPage() {
  const courseId = useNumericParam("courseId");
  const { assessmentId } = useParams();
  const editing = assessmentId !== undefined;
  const assessment = useAssessment(Number(assessmentId ?? 0));
  const questions = useQuestions(Number(assessmentId ?? 0), editing);
  const chapters = useChapters(courseId);
  const crumbs = [
    { label: "Courses", to: "/lms" },
    { label: "Assignments", to: `/lms/courses/${courseId}/assignments` },
    { label: editing ? "Edit assignment" : "New assignment" },
  ];
  return (
    <div>
      <Breadcrumbs items={crumbs} />
      {editing ? (
        <QueryView query={assessment} skeleton={<SkeletonLines lines={10} />}>
          {(data) =>
            questions.isPending ? (
              <SkeletonLines lines={10} />
            ) : (
              <AssessmentForm
                courseId={courseId}
                initial={data}
                chapters={chapters.data ?? []}
                initialQuestions={questions.data ?? []}
              />
            )
          }
        </QueryView>
      ) : (
        <AssessmentForm
          courseId={courseId}
          initial={null}
          chapters={chapters.data ?? []}
          initialQuestions={[]}
        />
      )}
    </div>
  );
}

function toDraft(q: QuestionWrite): DraftQuestion {
  return {
    prompt: q.prompt,
    type: q.type,
    options: (q.options as string[]).join("\n"),
    correct_index: q.correct_index,
  };
}

function AssessmentForm({
  courseId,
  initial,
  chapters,
  initialQuestions,
}: {
  courseId: number;
  initial: AssessmentDetail | null;
  chapters: ChapterSummary[];
  initialQuestions: QuestionWrite[];
}) {
  const tz = useTimezone();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [form, setForm] = useState(() => ({
    type: initial?.type ?? "homework",
    title: initial?.title ?? "",
    instructions: initial?.instructions ?? "",
    open_at: toLocalInputValue(initial?.open_at ?? new Date().toISOString(), tz),
    due_at: toLocalInputValue(
      initial?.due_at ?? new Date(Date.now() + 7 * 86_400_000).toISOString(),
      tz,
    ),
    cutoff_at: initial?.cutoff_at ? toLocalInputValue(initial.cutoff_at, tz) : "",
    points: String(initial?.points ?? 10),
    weight_pct: String(initial?.weight_pct ?? "5"),
    est_minutes: initial?.est_minutes ? String(initial.est_minutes) : "",
    discussion_replies_required: String(initial?.discussion_replies_required ?? 2),
    time_limit_minutes: String(initial?.time_limit_minutes ?? 20),
    max_attempts: String(initial?.max_attempts ?? 1),
    published: initial?.published ?? true,
  }));
  const [chapterIds, setChapterIds] = useState<number[]>(initial?.chapter_ids ?? []);
  const [questions, setQuestions] = useState<DraftQuestion[]>(initialQuestions.map(toDraft));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [confirmDelete, setConfirmDelete] = useState(false);

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm({ ...form, [key]: e.target.value });
  const err = (key: string) => fieldErrors[key]?.[0];

  const payload = () => ({
    type: form.type,
    title: form.title,
    instructions: form.instructions,
    chapter_ids: chapterIds,
    open_at: fromLocalInputValue(form.open_at, tz),
    due_at: fromLocalInputValue(form.due_at, tz),
    cutoff_at: form.cutoff_at ? fromLocalInputValue(form.cutoff_at, tz) : null,
    points: Number(form.points),
    weight_pct: form.weight_pct,
    est_minutes: form.est_minutes ? Number(form.est_minutes) : null,
    discussion_replies_required: Number(form.discussion_replies_required),
    time_limit_minutes: Number(form.time_limit_minutes),
    max_attempts: Number(form.max_attempts),
    published: form.published,
    ...(form.type === "quiz"
      ? {
          questions: questions.map((q, i) => ({
            order: i + 1,
            type: q.type,
            prompt: q.prompt,
            options:
              q.type === "true_false"
                ? ["True", "False"]
                : q.options
                    .split("\n")
                    .map((o) => o.trim())
                    .filter(Boolean),
            correct_index: q.correct_index,
          })),
        }
      : {}),
  });

  const save = useMutation({
    mutationFn: async () =>
      initial
        ? unwrap(
            await api.PATCH("/api/v1/assessments/{assessment_id}", {
              params: { path: { assessment_id: initial.id } },
              body: payload(),
            }),
          )
        : unwrap(
            await api.POST("/api/v1/courses/{course_id}/assessments", {
              params: { path: { course_id: courseId } },
              body: payload(),
            }),
          ),
    onSuccess: (saved) => {
      toast.success(initial ? "Assignment saved." : "Assignment created.");
      void client.invalidateQueries({ queryKey: lmsKeys.assessments(courseId) });
      void client.invalidateQueries({ queryKey: lmsKeys.questions(saved.id) });
      client.setQueryData(lmsKeys.assessment(saved.id), saved);
      navigate(`/lms/courses/${courseId}/assignments/${saved.id}`);
    },
    onError: (e) => {
      if (e instanceof ApiError) setFieldErrors(e.fields);
      toast.error(errorMessage(e));
    },
  });

  const remove = useMutation({
    mutationFn: async () => {
      if (initial)
        await api.DELETE("/api/v1/assessments/{assessment_id}", {
          params: { path: { assessment_id: initial.id } },
        });
    },
    onSuccess: () => {
      toast.success("Assignment deleted.");
      void client.invalidateQueries({ queryKey: lmsKeys.assessments(courseId) });
      navigate(`/lms/courses/${courseId}/assignments`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const invalid =
    !form.title.trim() ||
    !form.instructions.trim() ||
    (form.type === "quiz" && questions.some((q) => !q.prompt.trim()));

  function submit(e: FormEvent) {
    e.preventDefault();
    setFieldErrors({});
    if (!invalid) save.mutate();
  }

  return (
    <form onSubmit={submit} noValidate className="flex max-w-3xl flex-col gap-4">
      <h1 className="text-2xl font-bold">{initial ? "Edit assignment" : "New assignment"}</h1>
      <div className="grid gap-4 sm:grid-cols-[12rem_1fr]">
        <Select label="Type" value={form.type} onChange={set("type")} disabled={Boolean(initial)}>
          <option value="homework">Homework</option>
          <option value="discussion">Discussion</option>
          <option value="quiz">Quiz</option>
        </Select>
        <Input
          label="Title"
          value={form.title}
          onChange={set("title")}
          error={err("title") ?? (form.title.trim() ? undefined : "Add a title.")}
        />
      </div>
      <Textarea
        label="Instructions (Markdown)"
        value={form.instructions}
        onChange={set("instructions")}
        error={err("instructions")}
        rows={6}
      />
      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-bold">Linked chapters</legend>
        <div className="flex flex-wrap gap-2">
          {chapters.map((c) => (
            <label
              key={c.id}
              className="flex min-h-11 items-center gap-2 rounded-md border border-line px-3 text-sm"
            >
              <input
                type="checkbox"
                checked={chapterIds.includes(c.id)}
                onChange={(e) =>
                  setChapterIds(
                    e.target.checked
                      ? [...chapterIds, c.id]
                      : chapterIds.filter((id) => id !== c.id),
                  )
                }
                className="h-4 w-4 accent-[rgb(var(--pine))]"
              />
              Ch {c.order}: {c.title}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-3">
        <Input
          label={`Opens (${tz})`}
          type="datetime-local"
          value={form.open_at}
          onChange={set("open_at")}
          error={err("open_at")}
        />
        <Input
          label="Due"
          type="datetime-local"
          value={form.due_at}
          onChange={set("due_at")}
          error={err("due_at")}
        />
        <Input
          label="Late cut-off (optional)"
          type="datetime-local"
          value={form.cutoff_at}
          onChange={set("cutoff_at")}
          error={err("cutoff_at")}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Input
          label="Points"
          type="number"
          min={1}
          value={form.points}
          onChange={set("points")}
          error={err("points")}
        />
        <Input
          label="Weight (% of grade)"
          type="number"
          min={0}
          max={100}
          step="0.5"
          value={form.weight_pct}
          onChange={set("weight_pct")}
          error={err("weight_pct")}
        />
        <Input
          label="Estimated effort (minutes)"
          hint="Leave empty to let Pulse estimate it."
          type="number"
          min={5}
          value={form.est_minutes}
          onChange={set("est_minutes")}
          error={err("est_minutes")}
        />
      </div>
      {form.type === "discussion" && (
        <Input
          label="Replies required"
          type="number"
          min={0}
          max={10}
          value={form.discussion_replies_required}
          onChange={set("discussion_replies_required")}
        />
      )}
      {form.type === "quiz" && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Time limit (minutes)"
              type="number"
              min={1}
              value={form.time_limit_minutes}
              onChange={set("time_limit_minutes")}
            />
            <Select
              label="Attempts allowed"
              value={form.max_attempts}
              onChange={set("max_attempts")}
              error={err("max_attempts")}
            >
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3">3</option>
            </Select>
          </div>
          <QuestionsEditor questions={questions} onChange={setQuestions} error={err("questions")} />
        </>
      )}
      <label className="flex min-h-11 items-center gap-2 font-bold">
        <input
          type="checkbox"
          checked={form.published}
          onChange={(e) => setForm({ ...form, published: e.target.checked })}
          className="h-5 w-5 accent-[rgb(var(--pine))]"
        />
        Visible to students
      </label>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" pending={save.isPending} pendingLabel="Saving…" disabled={invalid}>
          {initial ? "Save assignment" : "Create assignment"}
        </Button>
        {initial && (
          <Button variant="danger" onClick={() => setConfirmDelete(true)}>
            Delete assignment
          </Button>
        )}
      </div>
      <ConfirmModal
        open={confirmDelete}
        title="Delete this assignment?"
        body="Submissions, posts and attempts for it are deleted too, and students' plans drop its study sessions. This can't be undone."
        confirmLabel="Delete assignment"
        pending={remove.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
      />
    </form>
  );
}

function QuestionsEditor({
  questions,
  onChange,
  error,
}: {
  questions: DraftQuestion[];
  onChange: (q: DraftQuestion[]) => void;
  error?: string;
}) {
  const update = (i: number, patch: Partial<DraftQuestion>) =>
    onChange(questions.map((q, j) => (j === i ? { ...q, ...patch } : q)));
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-2 text-lg font-bold">Questions</legend>
      {error && <p className="text-sm font-bold text-berry">{error}</p>}
      {questions.map((q, i) => {
        const options =
          q.type === "true_false"
            ? ["True", "False"]
            : q.options.split("\n").filter((o) => o.trim());
        return (
          <div key={i} className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
            <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
              <Input
                label={`Question ${i + 1}`}
                value={q.prompt}
                onChange={(e) => update(i, { prompt: e.target.value })}
              />
              <Select
                label="Kind"
                value={q.type}
                onChange={(e) =>
                  update(i, { type: e.target.value as DraftQuestion["type"], correct_index: 0 })
                }
              >
                <option value="multiple_choice">Multiple choice</option>
                <option value="true_false">True / false</option>
              </Select>
            </div>
            {q.type === "multiple_choice" && (
              <Textarea
                label="Options"
                hint="One per line, 2 to 6."
                value={q.options}
                onChange={(e) => update(i, { options: e.target.value })}
                rows={4}
              />
            )}
            <Select
              label="Correct answer"
              value={String(q.correct_index)}
              onChange={(e) => update(i, { correct_index: Number(e.target.value) })}
            >
              {options.map((o, k) => (
                <option key={`${o}-${k}`} value={k}>
                  {o}
                </option>
              ))}
            </Select>
            <Button
              variant="ghost"
              size="sm"
              className="self-start"
              onClick={() => onChange(questions.filter((_, j) => j !== i))}
            >
              Remove question
            </Button>
          </div>
        );
      })}
      <Button
        variant="secondary"
        className="self-start"
        onClick={() =>
          onChange([
            ...questions,
            { prompt: "", type: "multiple_choice", options: "", correct_index: 0 },
          ])
        }
      >
        Add question
      </Button>
    </fieldset>
  );
}
