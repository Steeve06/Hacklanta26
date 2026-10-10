import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage, unwrap } from "@/api/client";
import { Button, Card, QueryView, Skeleton, toast } from "@/components/ui";
import { stateLabel } from "@/features/pulse/status";
import { cx } from "@/lib/cx";
import { formatExact } from "@/lib/time";

const key = ["demo", "students"] as const;

export function DemoPage() {
  const client = useQueryClient();
  const students = useQuery({
    queryKey: key,
    queryFn: async () => unwrap(await api.GET("/api/v1/demo/students")),
  });
  const [ignoreQuiet, setIgnoreQuiet] = useState(true);
  const refresh = () => void client.invalidateQueries({ queryKey: key });

  const scan = useMutation({
    mutationFn: async (studentId?: number) =>
      unwrap(
        await api.POST("/api/v1/demo/scan-notifications", {
          body: { student_id: studentId, ignore_quiet_hours: ignoreQuiet },
        }),
      ),
    onSuccess: (r) => toast.success(`Scan done: ${r.created} created, ${r.sent} sent.`),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const replan = useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.POST("/api/v1/demo/replan/{student_id}", {
          params: { path: { student_id: id } },
        }),
      ),
    onSuccess: (r) => {
      toast.success(`Re-planned ${r.name}.`);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const travel = useMutation({
    mutationFn: async (body: { student_id: number; hours?: number; reset?: boolean }) =>
      unwrap(
        await api.POST("/api/v1/demo/time-travel", {
          body: { ...body, reset: Boolean(body.reset) },
        }),
      ),
    onSuccess: (r) => {
      toast.success(`${r.name}'s clock is now ${formatExact(r.clock, "UTC")} UTC.`);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-bold">Demo controls</h1>
        <p className="max-w-prose text-ink-soft">
          Only available with DEMO_MODE on. Time-travel shifts one student's clock forward so quiz
          windows, deadlines, reminders and status can be shown live. Students see the shifted time
          after they reload.
        </p>
      </header>
      <Card aria-labelledby="scan-heading">
        <h2 id="scan-heading" className="mb-2 text-lg font-bold">
          Notifications
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            onClick={() => scan.mutate(undefined)}
            pending={scan.isPending && scan.variables === undefined}
            pendingLabel="Scanning…"
          >
            Run notification scan for everyone
          </Button>
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={ignoreQuiet}
              onChange={(e) => setIgnoreQuiet(e.target.checked)}
              className="h-5 w-5"
            />
            Send now even during quiet hours
          </label>
          <a href="/admin/" className="text-sm font-bold text-pine underline">
            Open Django admin
          </a>
        </div>
      </Card>
      <QueryView
        query={students}
        skeleton={<Skeleton className="h-64 w-full" />}
        isEmpty={(d) => d.length === 0}
        empty={{ title: "No onboarded students" }}
      >
        {(rows) => (
          <div className="overflow-x-auto rounded-lg border border-line bg-surface">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <thead className="border-b border-line text-ink-soft">
                <tr>
                  <th scope="col" className="px-3 py-2">
                    Student
                  </th>
                  <th scope="col" className="px-3 py-2">
                    Status
                  </th>
                  <th scope="col" className="px-3 py-2">
                    Their clock (UTC)
                  </th>
                  <th scope="col" className="px-3 py-2">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id} className="border-b border-line align-top last:border-0">
                    <td className="px-3 py-2">
                      <span className="font-bold">{s.name}</span>
                      <span className="block text-xs text-ink-soft">{s.email}</span>
                      <span className="block text-xs text-ink-soft">
                        Sass {s.sass_level}
                        {s.supportive_mode ? " · supportive mode" : ""}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={cx(
                          "font-bold",
                          s.state === "bad"
                            ? "text-berry"
                            : s.state === "medium"
                              ? "text-mustard-ink"
                              : "text-pine-strong",
                        )}
                      >
                        {stateLabel[s.state]}
                      </span>{" "}
                      · {s.score}
                    </td>
                    <td className="px-3 py-2">
                      {formatExact(s.clock, "UTC")}
                      {s.offset_minutes > 0 && (
                        <span className="block text-xs font-bold text-mustard-ink">
                          +{Math.round(s.offset_minutes / 60)} h
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => scan.mutate(s.id)}
                          pending={scan.isPending && scan.variables === s.id}
                        >
                          Scan
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => replan.mutate(s.id)}
                          pending={replan.isPending && replan.variables === s.id}
                        >
                          Re-plan
                        </Button>
                        {[1, 6, 24].map((h) => (
                          <Button
                            key={h}
                            size="sm"
                            variant="ghost"
                            onClick={() => travel.mutate({ student_id: s.id, hours: h })}
                            disabled={travel.isPending}
                          >
                            +{h === 24 ? "1 day" : `${h} h`}
                          </Button>
                        ))}
                        {s.offset_minutes > 0 && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => travel.mutate({ student_id: s.id, reset: true })}
                            disabled={travel.isPending}
                          >
                            Back to now
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
    </div>
  );
}
