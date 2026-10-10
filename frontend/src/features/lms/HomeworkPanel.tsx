import { useRef, useState, type FormEvent } from "react";
import { Button, ProgressBar, Textarea, toast } from "@/components/ui";
import { ExactTime } from "@/components/Time";
import { downloadFile } from "@/lib/download";
import { useNow } from "@/lib/useNow";
import { uploadForm, UploadError, type UploadHandle } from "@/lib/upload";
import { useInvalidateAssessment, type AssessmentDetail } from "./api";
import { StatusPill } from "./StatusPill";
import { validateFile } from "./validateFile";

type Phase = { kind: "idle" } | { kind: "uploading"; pct: number } | { kind: "submitting" };

export function HomeworkPanel({ assessment }: { assessment: AssessmentDetail }) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string>();
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const handle = useRef<UploadHandle | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const invalidate = useInvalidateAssessment();

  const now = useNow();
  const closesAt = new Date(
    assessment.effective_cutoff_at ?? assessment.effective_due_at,
  ).getTime();
  const pastDue = now > new Date(assessment.effective_due_at).getTime();
  const alreadySubmitted = assessment.submissions.some(
    (s) => ["submitted", "late"].includes(s.status) || s.score !== null,
  );
  const closed = now > closesAt || (pastDue && alreadySubmitted) || assessment.status === "excused";
  const fileError = validateFile(file);
  const empty = !text.trim() && !file;
  const busy = phase.kind !== "idle";

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (empty) {
      setError("Add a text answer or attach a file.");
      return;
    }
    if (fileError) return;
    setError(undefined);
    const form = new FormData();
    if (text.trim()) form.append("text", text);
    if (file) form.append("file", file);
    setPhase({ kind: "uploading", pct: 0 });
    handle.current = uploadForm(`/api/v1/assessments/${assessment.id}/submissions`, form, (pct) =>
      setPhase(pct >= 100 ? { kind: "submitting" } : { kind: "uploading", pct }),
    );
    try {
      await handle.current.promise;
      toast.success(pastDue ? "Submitted late." : "Submitted.");
      setText("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      invalidate(assessment);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") toast.info("Upload cancelled.");
      else setError(err instanceof UploadError ? err.message : "Upload failed. Try again.");
    } finally {
      handle.current = null;
      setPhase({ kind: "idle" });
    }
  }

  return (
    <section
      aria-labelledby="submit-heading"
      className="flex max-w-prose flex-col gap-4 border-t border-line pt-4"
    >
      <h2 id="submit-heading" className="text-lg font-bold">
        Your submission
      </h2>
      {assessment.submissions.length > 0 && (
        <ul className="flex flex-col gap-2">
          {assessment.submissions.map((s) => (
            <li
              key={s.id}
              className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-surface px-3 py-2 text-sm"
            >
              <span className="font-bold">Attempt {s.attempt_no}</span>
              <StatusPill
                status={s.score !== null && s.score !== undefined ? "graded" : s.status}
              />
              {s.submitted_at && <ExactTime iso={s.submitted_at} />}
              {s.file_name && (
                <button
                  type="button"
                  className="min-h-11 text-pine underline md:min-h-0"
                  onClick={() =>
                    downloadFile(
                      `/api/v1/submissions/${s.id}/file`,
                      s.file_name ?? "submission",
                    ).catch(() => toast.error("Couldn't download the file."))
                  }
                >
                  {s.file_name}
                </button>
              )}
              {s.score !== null && s.score !== undefined && (
                <span className="font-bold">
                  {s.score} / {assessment.points}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {closed ? (
        <p className="rounded-md bg-sunken p-3 text-sm text-ink-soft">
          {assessment.status === "excused"
            ? "You're excused from this assignment."
            : now > closesAt
              ? "Submissions are closed for this assignment."
              : "Resubmissions are only allowed until the due date."}
        </p>
      ) : (
        <form noValidate onSubmit={submit} className="flex flex-col gap-4">
          {pastDue && (
            <p
              role="note"
              className="rounded-md border border-mustard bg-mustard-soft p-3 text-sm text-mustard-ink"
            >
              The due date has passed. You can still submit until the late cut-off, and it will be
              marked late.
            </p>
          )}
          <Textarea
            label="Text answer"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={busy}
            rows={6}
          />
          <div className="flex flex-col gap-1">
            <label htmlFor="hw-file" className="text-sm font-bold">
              File (PDF, DOCX or ZIP, up to 10 MB)
            </label>
            <input
              id="hw-file"
              ref={fileInput}
              type="file"
              accept=".pdf,.docx,.zip"
              disabled={busy}
              aria-invalid={Boolean(fileError)}
              aria-describedby={fileError ? "hw-file-error" : undefined}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="min-h-11 text-sm file:mr-3 file:min-h-11 file:rounded-md file:border file:border-line file:bg-surface file:px-3 file:font-bold file:text-ink"
            />
            {fileError && (
              <p id="hw-file-error" className="text-xs font-bold text-berry">
                {fileError}
              </p>
            )}
          </div>
          {phase.kind === "uploading" && (
            <ProgressBar value={phase.pct} label="Uploading" showLabel />
          )}
          {error && (
            <p role="alert" className="text-sm font-bold text-berry">
              {error}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              pending={busy}
              pendingLabel={phase.kind === "submitting" ? "Submitting…" : "Uploading…"}
              disabled={Boolean(fileError)}
            >
              {alreadySubmitted ? "Resubmit" : "Submit"}
            </Button>
            {phase.kind === "uploading" && (
              <Button variant="secondary" onClick={() => handle.current?.cancel()}>
                Cancel upload
              </Button>
            )}
          </div>
        </form>
      )}
    </section>
  );
}
