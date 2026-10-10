import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "@/api/client";
import { Button, Card, ConfirmModal, QueryView, Skeleton, Textarea, toast } from "@/components/ui";
import { PushToggle } from "@/features/notifications/PushToggle";
import { SupportiveBanner } from "@/features/notifications/SupportiveBanner";
import { useLogout, useMe, useUpdateMe, type Me } from "@/features/auth/hooks";
import { ChangePasswordCard } from "@/features/auth/ChangePasswordCard";
import { useAuth } from "@/features/auth/store";
import { downloadFile } from "@/lib/download";
import { useScrollToHash } from "@/lib/useScrollToHash";
import {
  useAvailability,
  useCancelJob,
  useGenerate,
  useLatestJob,
  useSaveAvailability,
  type AvailabilityBlock,
} from "./api";
import { AvailabilityEditor } from "./AvailabilityEditor";
import { AvailabilityGrid } from "./AvailabilityGrid";
import { formatHours, LOW_WEEKLY_HOURS, totalHours } from "./availability";
import { BlackoutsEditor } from "./BlackoutsEditor";
import { NotificationStyleFields } from "./NotificationStyleFields";
import { PlanProgress } from "./PlanProgress";
import { PreferencesFields } from "./PreferencesFields";
import {
  preferenceErrors,
  styleErrors,
  type NotificationStyle,
  type Preferences,
} from "./preferences";

export function SettingsPage() {
  const me = useMe();
  useScrollToHash(me.isSuccess);
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <h1 className="text-2xl font-bold">Settings</h1>
      <QueryView query={me} skeleton={<Skeleton className="h-96 w-full" />}>
        {(data) =>
          data.role === "student" ? (
            <>
              <PreferencesSection me={data} />
              <AvailabilitySection />
              <Card aria-labelledby="blackouts-heading">
                <h2 id="blackouts-heading" className="mb-1 text-lg font-bold">
                  Blocked-off dates
                </h2>
                <p className="mb-3 text-sm text-ink-soft">
                  Work shifts, trips, anything that isn't part of a normal week.
                </p>
                <BlackoutsEditor />
              </Card>
              <NotificationsSection me={data} />
              <RegenerateSection feedback={data.profile?.plan_feedback ?? ""} />
              <ChangePasswordCard />
              <AccountSection />
            </>
          ) : (
            <>
              <ChangePasswordCard />
              <AccountSection />
            </>
          )
        }
      </QueryView>
    </div>
  );
}

function PreferencesSection({ me }: { me: Me }) {
  const update = useUpdateMe();
  const initial: Preferences = {
    max_hours_per_day: String(me.profile?.max_hours_per_day ?? "3"),
    max_hours_per_week: String(me.profile?.max_hours_per_week ?? "10"),
    session_minutes: me.profile?.session_minutes ?? 50,
    earliest_time: me.profile?.earliest_time ?? "08:00",
    latest_time: me.profile?.latest_time ?? "22:00",
    timezone: me.timezone,
  };
  const [prefs, setPrefs] = useState(initial);
  const invalid = Object.keys(preferenceErrors(prefs)).length > 0;
  const dirty = JSON.stringify(prefs) !== JSON.stringify(initial);
  return (
    <Card aria-labelledby="prefs-heading" id="preferences" className="scroll-mt-20">
      <h2 id="prefs-heading" className="mb-4 text-lg font-bold">
        Study preferences
      </h2>
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          update.mutate(
            {
              timezone: prefs.timezone,
              profile: {
                max_hours_per_day: prefs.max_hours_per_day,
                max_hours_per_week: prefs.max_hours_per_week,
                session_minutes: prefs.session_minutes as 25 | 50 | 90,
                earliest_time: prefs.earliest_time,
                latest_time: prefs.latest_time,
              },
            },
            {
              onSuccess: () => toast.success("Preferences saved."),
              onError: (err) => toast.error(errorMessage(err)),
            },
          );
        }}
      >
        <PreferencesFields value={prefs} onChange={setPrefs} />
        <Button
          type="submit"
          className="self-start"
          disabled={invalid || !dirty}
          pending={update.isPending}
          pendingLabel="Saving…"
        >
          Save preferences
        </Button>
      </form>
    </Card>
  );
}

function AvailabilitySection() {
  const availability = useAvailability();
  return (
    <Card aria-labelledby="availability-heading" id="availability" className="scroll-mt-20">
      <h2 id="availability-heading" className="mb-1 text-lg font-bold">
        Weekly study time
      </h2>
      <p className="mb-3 text-sm text-ink-soft">
        Times are in your time zone. Saving re-plans your schedule.
      </p>
      <QueryView query={availability} skeleton={<Skeleton className="h-80 w-full" />}>
        {(data) => <AvailabilityForm initial={data.blocks} />}
      </QueryView>
    </Card>
  );
}

function AvailabilityForm({ initial }: { initial: AvailabilityBlock[] }) {
  const [blocks, setBlocks] = useState(initial);
  const save = useSaveAvailability();
  const dirty = JSON.stringify(blocks) !== JSON.stringify(initial);
  const hours = totalHours(blocks);
  return (
    <div className="flex flex-col gap-3">
      <AvailabilityGrid value={blocks} onChange={setBlocks} />
      <p aria-live="polite" className="flex flex-wrap items-baseline gap-x-2 text-sm">
        <span className="font-bold">{formatHours(hours)} hours a week</span>
        {blocks.length > 0 && hours < LOW_WEEKLY_HOURS && (
          <span className="text-mustard-ink">That's under {LOW_WEEKLY_HOURS} hours.</span>
        )}
      </p>
      <details className="rounded-lg border border-line p-3">
        <summary className="min-h-11 cursor-pointer py-2 font-bold">Enter exact times</summary>
        <AvailabilityEditor
          value={blocks}
          onChange={setBlocks}
          onMerged={(n) => toast.info(`Merged ${n} overlapping block${n === 1 ? "" : "s"}.`)}
        />
      </details>
      {blocks.length === 0 && (
        <p className="text-sm font-bold text-berry">
          With no study time, Leon can't plan anything.
        </p>
      )}
      <Button
        className="self-start"
        disabled={!dirty || blocks.length === 0}
        pending={save.isPending}
        pendingLabel="Saving…"
        onClick={() =>
          save.mutate(blocks, {
            onSuccess: () => toast.success("Study time saved. Your schedule is being updated."),
            onError: (err) => toast.error(errorMessage(err)),
          })
        }
      >
        Save study time
      </Button>
    </div>
  );
}

function NotificationsSection({ me }: { me: Me }) {
  const update = useUpdateMe();
  const initial: NotificationStyle = {
    sass_level: me.profile?.sass_level ?? 2,
    quiet_start: (me.profile?.quiet_start ?? "22:00").slice(0, 5),
    quiet_end: (me.profile?.quiet_end ?? "08:00").slice(0, 5),
  };
  const [style, setStyle] = useState(initial);
  const [override, setOverride] = useState(Boolean(me.profile?.quiet_hours_override_for_deadlines));
  const invalid = Object.keys(styleErrors(style)).length > 0;
  return (
    <Card aria-labelledby="notif-heading">
      <h2 id="notif-heading" className="mb-3 text-lg font-bold">
        Reminders
      </h2>
      <div className="flex flex-col gap-4">
        <SupportiveBanner />
        <PushToggle />
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            update.mutate(
              {
                profile: {
                  sass_level: style.sass_level,
                  quiet_start: style.quiet_start,
                  quiet_end: style.quiet_end,
                  quiet_hours_override_for_deadlines: override,
                },
              },
              {
                onSuccess: () => toast.success("Reminder settings saved."),
                onError: (err) => toast.error(errorMessage(err)),
              },
            );
          }}
        >
          <NotificationStyleFields value={style} onChange={setStyle} />
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={override}
              onChange={(e) => setOverride(e.target.checked)}
              className="h-5 w-5 accent-[rgb(var(--pine))]"
            />
            Still remind me during quiet hours if something is due during them
          </label>
          <Button
            type="submit"
            variant="secondary"
            className="self-start"
            disabled={invalid}
            pending={update.isPending}
            pendingLabel="Saving…"
          >
            Save reminder settings
          </Button>
        </form>
      </div>
    </Card>
  );
}

function RegenerateSection({ feedback: saved }: { feedback: string }) {
  const [feedback, setFeedback] = useState(saved);
  const generate = useGenerate();
  const job = useLatestJob();
  const current = job.data;
  const cancel = useCancelJob();
  const running = current && (current.state === "queued" || current.state === "running");
  const announced = useRef<number | null>(null);
  useEffect(() => {
    if (current?.state === "done" && current.id !== announced.current && generate.isSuccess) {
      announced.current = current.id;
      toast.success("Your schedule was rebuilt.");
    }
  }, [current, generate.isSuccess]);

  return (
    <Card aria-labelledby="regen-heading">
      <h2 id="regen-heading" className="mb-1 text-lg font-bold">
        Rebuild your schedule
      </h2>
      <p className="mb-3 text-sm text-ink-soft">
        Leon re-plans automatically when things change. Rebuild if you want a fresh start or
        different emphasis.
      </p>
      {running && current ? (
        <PlanProgress
          job={current}
          onCancel={() => cancel.mutate(current.id)}
          cancelling={cancel.isPending}
        />
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            generate.mutate(feedback, { onError: (err) => toast.error(errorMessage(err)) });
          }}
        >
          <Textarea
            label="What should change? (optional)"
            placeholder="Less on weekends, more mornings"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            rows={2}
            maxLength={300}
          />
          <Button
            type="submit"
            variant="secondary"
            className="self-start"
            pending={generate.isPending}
            pendingLabel="Starting…"
          >
            Rebuild schedule
          </Button>
        </form>
      )}
    </Card>
  );
}

function AccountSection() {
  const logout = useLogout();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);
  return (
    <Card aria-labelledby="account-heading">
      <h2 id="account-heading" className="mb-3 text-lg font-bold">
        Account and data
      </h2>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          pending={exporting}
          pendingLabel="Preparing…"
          onClick={() => {
            setExporting(true);
            downloadFile("/api/v1/me/export", "pulse-export.json")
              .catch(() => toast.error("Couldn't export your data."))
              .finally(() => setExporting(false));
          }}
        >
          Download my data
        </Button>
        <Button
          variant="ghost"
          onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login") })}
        >
          Sign out
        </Button>
        <Button variant="danger" onClick={() => setConfirming(true)}>
          Delete account
        </Button>
      </div>
      <ConfirmModal
        open={confirming}
        title="Delete your account?"
        body="Your submissions, schedule, notifications and streak are deleted permanently. This can't be undone."
        confirmLabel="Delete my account"
        pending={deleting}
        onClose={() => setConfirming(false)}
        onConfirm={async () => {
          setDeleting(true);
          const result = await api.DELETE("/api/v1/me");
          setDeleting(false);
          if (result.response.ok) {
            useAuth.getState().expire();
            navigate("/login", { replace: true });
          } else toast.error("Couldn't delete the account. Try again.");
        }}
      />
    </Card>
  );
}
