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
  SkeletonLines,
  Textarea,
  toast,
} from "@/components/ui";
import { fromLocalInputValue, toLocalInputValue, useTimezone } from "@/lib/time";
import { lmsKeys, useChapter, useChapters, type ChapterDetail } from "./api";
import { useNumericParam } from "./useIds";

export function ChapterEditorPage() {
  const courseId = useNumericParam("courseId");
  const { chapterId } = useParams();
  const editing = chapterId !== undefined;
  const chapter = useChapter(Number(chapterId ?? 0));
  const chapters = useChapters(courseId);
  const crumbs = [
    { label: "Courses", to: "/lms" },
    { label: "Content", to: `/lms/courses/${courseId}` },
    { label: editing ? "Edit chapter" : "New chapter" },
  ];
  if (!editing) {
    const nextOrder = (chapters.data?.reduce((max, c) => Math.max(max, c.order), 0) ?? 0) + 1;
    return (
      <div>
        <Breadcrumbs items={crumbs} />
        <ChapterForm courseId={courseId} initial={null} nextOrder={nextOrder} />
      </div>
    );
  }
  return (
    <div>
      <Breadcrumbs items={crumbs} />
      <QueryView query={chapter} skeleton={<SkeletonLines lines={8} />}>
        {(data) => <ChapterForm courseId={courseId} initial={data} nextOrder={data.order} />}
      </QueryView>
    </div>
  );
}

function ChapterForm({
  courseId,
  initial,
  nextOrder,
}: {
  courseId: number;
  initial: ChapterDetail | null;
  nextOrder: number;
}) {
  const tz = useTimezone();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [form, setForm] = useState({
    order: String(initial?.order ?? nextOrder),
    title: initial?.title ?? "",
    reading_minutes: String(initial?.reading_minutes ?? 15),
    available_from: toLocalInputValue(initial?.available_from ?? new Date().toISOString(), tz),
    objectives: initial?.objectives.join("\n") ?? "",
    body_md: initial?.body_md ?? "",
    links: initial?.links.map((l) => `${l.label} | ${l.url}`).join("\n") ?? "",
  });
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  const body = () => ({
    order: Number(form.order),
    title: form.title,
    reading_minutes: Number(form.reading_minutes),
    available_from: fromLocalInputValue(form.available_from, tz),
    objectives: form.objectives
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
    links: form.links
      .split("\n")
      .map((line) => line.split("|").map((s) => s.trim()))
      .filter(([label, url]) => label && url)
      .map(([label, url]) => ({ label: label ?? "", url: url ?? "" })),
    body_md: form.body_md,
  });

  const save = useMutation({
    mutationFn: async () =>
      initial
        ? unwrap(
            await api.PATCH("/api/v1/chapters/{chapter_id}", {
              params: { path: { chapter_id: initial.id } },
              body: body(),
            }),
          )
        : unwrap(
            await api.POST("/api/v1/courses/{course_id}/chapters", {
              params: { path: { course_id: courseId } },
              body: body(),
            }),
          ),
    onSuccess: (chapter) => {
      toast.success(initial ? "Chapter saved." : "Chapter created.");
      void client.invalidateQueries({ queryKey: lmsKeys.chapters(courseId) });
      client.setQueryData(lmsKeys.chapter(chapter.id), chapter);
      navigate(`/lms/courses/${courseId}/chapters/${chapter.id}`);
    },
    onError: (err) => {
      if (err instanceof ApiError) setFieldErrors(err.fields);
      toast.error(errorMessage(err));
    },
  });

  const remove = useMutation({
    mutationFn: async () => {
      if (!initial) return;
      await api.DELETE("/api/v1/chapters/{chapter_id}", {
        params: { path: { chapter_id: initial.id } },
      });
    },
    onSuccess: () => {
      toast.success("Chapter deleted.");
      void client.invalidateQueries({ queryKey: lmsKeys.chapters(courseId) });
      navigate(`/lms/courses/${courseId}`);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm({ ...form, [key]: e.target.value });
  const err = (key: string) => fieldErrors[key]?.[0];
  const missingBody = !form.body_md.trim();
  const invalid = !form.title.trim() || !form.objectives.trim() || missingBody;

  function submit(e: FormEvent) {
    e.preventDefault();
    setFieldErrors({});
    if (!invalid) save.mutate();
  }

  return (
    <form onSubmit={submit} noValidate className="flex max-w-3xl flex-col gap-4">
      <h1 className="text-2xl font-bold">
        {initial ? `Edit chapter ${initial.order}` : "New chapter"}
      </h1>
      <div className="grid gap-4 sm:grid-cols-[8rem_1fr]">
        <Input
          label="Number"
          type="number"
          min={1}
          value={form.order}
          onChange={set("order")}
          error={err("order")}
        />
        <Input
          label="Title"
          value={form.title}
          onChange={set("title")}
          error={err("title") ?? (form.title.trim() ? undefined : "Add a title.")}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Reading time (minutes)"
          type="number"
          min={1}
          value={form.reading_minutes}
          onChange={set("reading_minutes")}
          error={err("reading_minutes")}
        />
        <Input
          label={`Available from (${tz})`}
          type="datetime-local"
          value={form.available_from}
          onChange={set("available_from")}
          error={err("available_from")}
        />
      </div>
      <Textarea
        label="Learning objectives"
        hint="One per line."
        value={form.objectives}
        onChange={set("objectives")}
        error={err("objectives")}
        rows={4}
      />
      <Textarea
        label="Chapter text (Markdown)"
        hint="Students read this, and quiz questions are generated from it. Changing it regenerates the chapter's questions."
        value={form.body_md}
        onChange={set("body_md")}
        error={err("body_md") ?? (missingBody ? "Add the chapter text." : undefined)}
        rows={14}
        className="font-mono text-sm"
      />
      <Textarea
        label="Further reading"
        hint="One per line as: Label | https://example.com"
        value={form.links}
        onChange={set("links")}
        error={err("links")}
        rows={3}
      />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" pending={save.isPending} pendingLabel="Saving…" disabled={invalid}>
          {initial ? "Save chapter" : "Create chapter"}
        </Button>
        {initial && (
          <Button variant="danger" onClick={() => setConfirmDelete(true)}>
            Delete chapter
          </Button>
        )}
      </div>
      <ConfirmModal
        open={confirmDelete}
        title="Delete this chapter?"
        body="Students lose access to it and its quiz questions. This can't be undone."
        confirmLabel="Delete chapter"
        pending={remove.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
      />
    </form>
  );
}
