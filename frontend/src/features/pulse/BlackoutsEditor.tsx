import { useState, type FormEvent } from "react";
import { errorMessage } from "@/api/client";
import { Button, Input, QueryView, Skeleton, toast } from "@/components/ui";
import { formatExact, fromLocalInputValue, useTimezone } from "@/lib/time";
import { useAddBlackout, useBlackouts, useDeleteBlackout } from "./api";

export function BlackoutsEditor() {
  const tz = useTimezone();
  const blackouts = useBlackouts();
  const add = useAddBlackout();
  const remove = useDeleteBlackout();
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [label, setLabel] = useState("");
  const [touched, setTouched] = useState(false);
  const error =
    touched && (!start || !end)
      ? "Pick a start and an end."
      : touched && end <= start
        ? "End must be after start."
        : undefined;

  function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!start || !end || end <= start) return;
    add.mutate(
      { start: fromLocalInputValue(start, tz), end: fromLocalInputValue(end, tz), label },
      {
        onSuccess: () => {
          setStart("");
          setEnd("");
          setLabel("");
          setTouched(false);
          toast.success("Blocked off. Your plan will work around it.");
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <QueryView query={blackouts} skeleton={<Skeleton className="h-12 w-full" />}>
        {(rows) =>
          rows.length === 0 ? (
            <p className="text-sm text-ink-soft">No blocked-off dates.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {rows.map((b) => (
                <li
                  key={b.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm"
                >
                  <span>
                    <span className="font-bold">{b.label || "Busy"}</span> ·{" "}
                    {formatExact(b.start, tz)} – {formatExact(b.end, tz)}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    pending={remove.isPending && remove.variables === b.id}
                    onClick={() => remove.mutate(b.id)}
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )
        }
      </QueryView>
      <form
        onSubmit={submit}
        noValidate
        className="grid gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end"
      >
        <Input
          label="Busy from"
          type="datetime-local"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          error={error}
        />
        <Input
          label="Until"
          type="datetime-local"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
        <Input
          label="Label (optional)"
          placeholder="Work shift"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          maxLength={80}
        />
        <Button type="submit" variant="secondary" pending={add.isPending} pendingLabel="Adding…">
          Block off
        </Button>
      </form>
    </div>
  );
}
