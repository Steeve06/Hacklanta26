import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, errorMessage, unwrap } from "@/api/client";
import { Button, ConfirmModal, Input, Modal, QueryView, Skeleton, toast } from "@/components/ui";
import { ExactTime } from "@/components/Time";
import { downloadFile } from "@/lib/download";
import { fromLocalInputValue, toLocalInputValue, useTimezone } from "@/lib/time";
import { useInvalidateAssessment, useRoster, type AssessmentDetail, type RosterRow } from "./api";
import { StatusPill } from "./StatusPill";

export function InstructorPanel({ assessment }: { assessment: AssessmentDetail }) {
  const roster = useRoster(assessment.id, true);
  const [extending, setExtending] = useState<RosterRow | null>(null);
  const [excusing, setExcusing] = useState<RosterRow | null>(null);
  const invalidate = useInvalidateAssessment();

  const excuse = useMutation({
    mutationFn: async ({ student, excused }: { student: number; excused: boolean }) =>
      unwrap(
        await api.POST("/api/v1/assessments/{assessment_id}/excuse", {
          params: { path: { assessment_id: assessment.id } },
          body: { student, excused },
        }),
      ),
    onSuccess: (_d, vars) => {
      toast.success(vars.excused ? "Student excused." : "Excusal removed.");
      setExcusing(null);
      invalidate(assessment);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <section
      aria-labelledby="roster-heading"
      className="flex flex-col gap-3 border-t border-line pt-4"
    >
      <h2 id="roster-heading" className="text-lg font-bold">
        Student roster
      </h2>
      <QueryView
        query={roster}
        isEmpty={(d) => d.length === 0}
        empty={{ title: "No students enrolled" }}
        skeleton={<Skeleton className="h-48 w-full" />}
      >
        {(rows) => (
          <div className="overflow-x-auto rounded-lg border border-line bg-surface">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <thead className="border-b border-line text-ink-soft">
                <tr>
                  <th scope="col" className="px-3 py-2 font-bold">
                    Student
                  </th>
                  <th scope="col" className="px-3 py-2 font-bold">
                    Status
                  </th>
                  <th scope="col" className="px-3 py-2 font-bold">
                    Due
                  </th>
                  <th scope="col" className="px-3 py-2 font-bold">
                    Score
                  </th>
                  <th scope="col" className="px-3 py-2 font-bold">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.student_id} className="border-b border-line align-top last:border-0">
                    <td className="px-3 py-2">
                      <span className="font-bold">{row.name}</span>
                      <span className="block text-xs text-ink-soft">{row.email}</span>
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill status={row.status} />
                      {row.submitted_at && (
                        <span className="mt-1 block text-xs text-ink-soft">
                          <ExactTime iso={row.submitted_at} />
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <ExactTime iso={row.effective_due_at} />
                      {row.extended && (
                        <span className="block text-xs font-bold text-pine-strong">Extended</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {row.submission_id && row.status !== "excused" ? (
                        <ScoreCell row={row} assessment={assessment} />
                      ) : (
                        <span className="text-ink-faint">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        <Button size="sm" variant="secondary" onClick={() => setExtending(row)}>
                          Extend
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setExcusing(row)}>
                          {row.status === "excused" ? "Un-excuse" : "Excuse"}
                        </Button>
                        {row.has_file && row.submission_id && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              downloadFile(
                                `/api/v1/submissions/${row.submission_id}/file`,
                                `${row.name}-${assessment.title}`,
                              ).catch(() => toast.error("Couldn't download the file."))
                            }
                          >
                            File
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryView>
      {extending && (
        <ExtendModal row={extending} assessment={assessment} onClose={() => setExtending(null)} />
      )}
      <ConfirmModal
        open={Boolean(excusing)}
        title={excusing?.status === "excused" ? "Remove excusal?" : "Excuse this student?"}
        body={
          excusing?.status === "excused"
            ? `${excusing.name} will be expected to complete ${assessment.title} again.`
            : `${excusing?.name ?? "The student"} won't need to complete ${assessment.title}, and their reminders for it stop.`
        }
        confirmLabel={excusing?.status === "excused" ? "Remove excusal" : "Excuse student"}
        pending={excuse.isPending}
        onClose={() => setExcusing(null)}
        onConfirm={() =>
          excusing &&
          excuse.mutate({ student: excusing.student_id, excused: excusing.status !== "excused" })
        }
      />
    </section>
  );
}

function ScoreCell({ row, assessment }: { row: RosterRow; assessment: AssessmentDetail }) {
  const [value, setValue] = useState(row.score ?? "");
  const invalidate = useInvalidateAssessment();
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PATCH("/api/v1/submissions/{submission_id}/score", {
          params: { path: { submission_id: row.submission_id ?? 0 } },
          body: { score: value === "" ? null : String(value) },
        }),
      ),
    onSuccess: () => {
      toast.success("Score saved.");
      invalidate(assessment);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const invalid =
    value !== "" &&
    (Number(value) < 0 || Number(value) > assessment.points || Number.isNaN(Number(value)));
  return (
    <form
      className="flex items-center gap-1"
      onSubmit={(e) => {
        e.preventDefault();
        if (!invalid) save.mutate();
      }}
    >
      <label className="sr-only" htmlFor={`score-${row.student_id}`}>
        Score for {row.name}
      </label>
      <input
        id={`score-${row.student_id}`}
        inputMode="decimal"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        aria-invalid={invalid}
        className="min-h-11 w-16 rounded-md border border-line bg-surface px-2 aria-[invalid=true]:border-berry md:min-h-9"
      />
      <span className="text-ink-soft">/ {assessment.points}</span>
      <Button
        type="submit"
        size="sm"
        variant="secondary"
        pending={save.isPending}
        disabled={invalid}
      >
        Save
      </Button>
    </form>
  );
}

function ExtendModal({
  row,
  assessment,
  onClose,
}: {
  row: RosterRow;
  assessment: AssessmentDetail;
  onClose: () => void;
}) {
  const tz = useTimezone();
  const [due, setDue] = useState(toLocalInputValue(row.effective_due_at, tz));
  const [reason, setReason] = useState("");
  const invalidate = useInvalidateAssessment();
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/assessments/{assessment_id}/overrides", {
          params: { path: { assessment_id: assessment.id } },
          body: {
            student: row.student_id,
            due_at: fromLocalInputValue(due, tz),
            cutoff_at: null,
            reason,
          },
        }),
      ),
    onSuccess: () => {
      toast.success(`Extension saved for ${row.name}.`);
      invalidate(assessment);
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <Modal open title={`Extend for ${row.name}`} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Input
          label={`New due date (${tz})`}
          type="datetime-local"
          value={due}
          onChange={(e) => setDue(e.target.value)}
          required
        />
        <Input
          label="Reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={200}
        />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" pending={save.isPending} pendingLabel="Saving…">
            Save extension
          </Button>
        </div>
      </form>
    </Modal>
  );
}
