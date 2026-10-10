import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "@/api/client";
import {
  Button,
  Card,
  ConfirmModal,
  Input,
  QueryView,
  Skeleton,
  Textarea,
  toast,
} from "@/components/ui";
import { PushToggle } from "@/features/notifications/PushToggle";
import { SupportiveBanner } from "@/features/notifications/SupportiveBanner";
import { useLogout, useMe, useUpdateMe, type Me } from "@/features/auth/hooks";
import { useAuth } from "@/features/auth/store";
import { downloadFile } from "@/lib/download";
import {
  useAvailability,
  useCancelJob,
  useGenerate,
  useLatestJob,
  useSaveAvailability,
  type AvailabilityBlock,
} from "./api";
import { AvailabilityEditor, totalHours } from "./AvailabilityEditor";
import { BlackoutsEditor } from "./BlackoutsEditor";
import { PlanProgress } from "./PlanProgress";
import { preferenceErrors, PreferencesFields, type Preferences } from "./PreferencesFields";

export function SettingsPage() {
  const me = useMe();
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
              <AccountSection />
            </>
          ) : (
            <AccountSection />
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
    session_minutes: me.profile?.session_minutes ?? 50,
    earliest_time: me.profile?.earliest_time ?? "08:00",
    latest_time: me.profile?.latest_time ?? "22:00",
    timezone: me.timezone,
    sass_level: me.profile?.sass_level ?? 3,
  };
  const [prefs, setPrefs] = useState(initial);
  const invalid = Object.keys(preferenceErrors(prefs)).length > 0;
  const dirty = JSON.stringify(prefs) !== JSON.stringify(initial);
  return (
    <Card aria-labelledby="prefs-heading">
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
                session_minutes: prefs.session_minutes as 25 | 50 | 90,
                earliest_time: prefs.earliest_time,
                latest_time: prefs.latest_time,
                sass_level: prefs.sass_level,
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
    <Card aria-labelledby="availability" id="availability">
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
  return (
    <div className="flex flex-col gap-3">
      <AvailabilityEditor value={blocks} onChange={setBlocks} />
      <p className="text-sm font-bold">
        {totalHours(blocks).toFixed(1).replace(".0", "")} hours a week
      </p>
      {blocks.length === 0 && (
        <p className="text-sm font-bold text-berry">
          With no study time, Pulse can't plan anything.
        </p>
      )}
      <Button
        className="self-start"
        disabled={!dirty}
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
  const [quietStart, setQuietStart] = useState((me.profile?.quiet_start ?? "22:00").slice(0, 5));
  const [quietEnd, setQuietEnd] = useState((me.profile?.quiet_end ?? "08:00").slice(0, 5));
  const [override, setOverride] = useState(Boolean(me.profile?.quiet_hours_override_for_deadlines));
  return (
    <Card aria-labelledby="notif-heading">
      <h2 id="notif-heading" className="mb-3 text-lg font-bold">
        Notifications
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
                  quiet_start: quietStart,
                  quiet_end: quietEnd,
                  quiet_hours_override_for_deadlines: override,
                },
              },
              {
                onSuccess: () => toast.success("Quiet hours saved."),
                onError: (err) => toast.error(errorMessage(err)),
              },
            );
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label="Quiet hours start"
              type="time"
              value={quietStart}
              onChange={(e) => setQuietStart(e.target.value)}
            />
            <Input
              label="Quiet hours end"
              type="time"
              value={quietEnd}
              onChange={(e) => setQuietEnd(e.target.value)}
            />
          </div>
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
            pending={update.isPending}
            pendingLabel="Saving…"
          >
            Save quiet hours
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
        Pulse re-plans automatically when things change. Rebuild if you want a fresh start or
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
