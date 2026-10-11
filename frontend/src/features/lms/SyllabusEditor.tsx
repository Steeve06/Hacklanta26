import { useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "@/api/client";
import { Button, Input, Textarea, toast } from "@/components/ui";
import { useUpdateSyllabus } from "@/features/teach/api";
import type { Syllabus } from "./api";

type Row = { label: string; weight_pct: string };

export function SyllabusEditor({
  courseId,
  initial,
  onDone,
}: {
  courseId: number;
  initial: Syllabus;
  onDone: () => void;
}) {
  const update = useUpdateSyllabus(courseId);
  const [description, setDescription] = useState(initial.description);
  const [officeHours, setOfficeHours] = useState(initial.office_hours);
  const [rows, setRows] = useState<Row[]>(
    initial.grading.map((g) => ({ label: g.label, weight_pct: String(g.weight_pct) })),
  );
  const total = rows.reduce((sum, r) => sum + (Number(r.weight_pct) || 0), 0);
  const fields = update.error instanceof ApiError ? update.error.fields : {};

  function submit(e: FormEvent) {
    e.preventDefault();
    update.mutate(
      {
        description,
        office_hours: officeHours,
        grading: rows
          .filter((r) => r.label.trim())
          .map((r) => ({ label: r.label.trim(), weight_pct: Number(r.weight_pct) })),
      },
      {
        onSuccess: () => {
          toast.success("Syllabus saved.");
          onDone();
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  return (
    <form onSubmit={submit} noValidate className="flex max-w-3xl flex-col gap-4">
      <h2 className="text-lg font-bold">Edit syllabus</h2>
      <Textarea
        label="About this course"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={5}
        error={fields.description?.[0]}
      />
      <Input
        label="Office hours"
        value={officeHours}
        onChange={(e) => setOfficeHours(e.target.value)}
        error={fields.office_hours?.[0]}
      />
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 font-bold">Grading</legend>
        {rows.map((row, i) => (
          <div key={i} className="grid items-end gap-2 sm:grid-cols-[1fr_8rem_auto]">
            <Input
              label="Category"
              value={row.label}
              onChange={(e) =>
                setRows(rows.map((r, j) => (j === i ? { ...r, label: e.target.value } : r)))
              }
            />
            <Input
              label="Weight (%)"
              type="number"
              min={0}
              max={100}
              value={row.weight_pct}
              onChange={(e) =>
                setRows(rows.map((r, j) => (j === i ? { ...r, weight_pct: e.target.value } : r)))
              }
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setRows(rows.filter((_, j) => j !== i))}
            >
              Remove
            </Button>
          </div>
        ))}
        <p
          className={
            total === 100 || rows.length === 0
              ? "text-sm text-ink-soft"
              : "text-sm font-bold text-berry"
          }
        >
          Total: {total}% {rows.length > 0 && total !== 100 && "(must add up to 100%)"}
        </p>
        {fields.grading && <p className="text-sm font-bold text-berry">{fields.grading[0]}</p>}
        <Button
          variant="secondary"
          className="self-start"
          onClick={() => setRows([...rows, { label: "", weight_pct: "" }])}
        >
          Add a category
        </Button>
      </fieldset>
      <div className="flex gap-2">
        <Button type="submit" pending={update.isPending} pendingLabel="Saving…">
          Save syllabus
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
