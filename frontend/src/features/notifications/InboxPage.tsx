import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { errorMessage } from "@/api/client";
import { Button, Card, QueryView, Skeleton, toast } from "@/components/ui";
import { useMe } from "@/features/auth/hooks";
import { cx } from "@/lib/cx";
import { formatExact, relativeDue, useTimezone } from "@/lib/time";
import { useInbox, useMarkAllRead, useNotificationAction, type Notification } from "./api";
import { PushToggle } from "./PushToggle";
import { SupportiveBanner } from "./SupportiveBanner";

const tierTone: Record<number, string> = {
  0: "border-l-pine",
  1: "border-l-line",
  2: "border-l-mustard",
  3: "border-l-mustard",
  4: "border-l-berry",
  5: "border-l-berry",
};

export function InboxPage() {
  const inbox = useInbox();
  const me = useMe();
  const markAll = useMarkAllRead();
  const act = useNotificationAction();
  const [params, setParams] = useSearchParams();
  const handled = useRef(false);
  const [promptDismissed, setPromptDismissed] = useState(false);

  useEffect(() => {
    const id = Number(params.get("notification"));
    const action = params.get("action");
    if (handled.current || !id || (action !== "snooze" && action !== "tone_down")) return;
    handled.current = true;
    act.mutate(
      { id, action },
      {
        onSuccess: () =>
          toast.success(action === "snooze" ? "Snoozed for an hour." : "Toned it down a notch."),
        onSettled: () => setParams({}, { replace: true }),
      },
    );
  }, [params, act, setParams]);

  const showPrompt = !promptDismissed && me.data?.profile?.push_prompt_seen === false;

  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Notifications</h1>
        {Boolean(inbox.data?.unread) && (
          <Button
            size="sm"
            variant="ghost"
            pending={markAll.isPending}
            onClick={() => markAll.mutate()}
          >
            Mark all as read
          </Button>
        )}
      </header>
      <SupportiveBanner supportUrl={inbox.data?.support_url} />
      {showPrompt && (
        <Card aria-label="Turn on push notifications">
          <h2 className="mb-1 font-bold">Want reminders on this device?</h2>
          <PushToggle onDone={() => setPromptDismissed(true)} />
          <button
            type="button"
            onClick={() => setPromptDismissed(true)}
            className="mt-2 min-h-11 text-sm text-ink-soft underline"
          >
            Not now
          </button>
        </Card>
      )}
      <QueryView
        query={inbox}
        isEmpty={(d) => d.results.length === 0}
        empty={{
          title: "No notifications yet",
          body: "Reminders about sessions, deadlines and quizzes show up here.",
        }}
        skeleton={
          <div className="flex flex-col gap-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        }
      >
        {(data) => (
          <ul className="flex flex-col gap-2">
            {data.results.map((n) => (
              <li key={n.id}>
                <NotificationRow notification={n} />
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </div>
  );
}

function NotificationRow({ notification: n }: { notification: Notification }) {
  const tz = useTimezone();
  const navigate = useNavigate();
  const act = useNotificationAction();
  const unread = !n.read_at;
  const run = (action: "open" | "snooze" | "tone_down") =>
    act.mutate(
      { id: n.id, action },
      {
        onSuccess: (result) => {
          if (action === "open") navigate(n.link || "/pulse");
          if (action === "snooze") toast.info("Snoozed for an hour.");
          if (action === "tone_down")
            toast.info(
              result.supportive_mode
                ? "Switched to supportive reminders."
                : `Sass level is now ${result.sass_level}.`,
            );
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  return (
    <article
      className={cx(
        "flex flex-col gap-2 rounded-md border border-l-4 border-line bg-surface p-4",
        tierTone[n.tier] ?? "border-l-line",
        unread && "bg-pine-soft/30",
      )}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-bold">
          {n.heading}
          {unread && (
            <span className="ml-2 rounded-full bg-pine px-2 py-0.5 text-xs text-on-pine">New</span>
          )}
        </h2>
        {n.sent_at && (
          <time
            dateTime={n.sent_at}
            title={formatExact(n.sent_at, tz)}
            className="text-xs text-ink-soft"
          >
            {relativeDue(n.sent_at)}
          </time>
        )}
      </header>
      <p>{n.text}</p>
      <div className="flex flex-wrap gap-1">
        <Button
          size="sm"
          onClick={() => run("open")}
          pending={act.isPending && act.variables?.action === "open"}
        >
          Open
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => run("snooze")}
          pending={act.isPending && act.variables?.action === "snooze"}
        >
          Snooze 1 h
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => run("tone_down")}
          pending={act.isPending && act.variables?.action === "tone_down"}
        >
          Tone it down
        </Button>
      </div>
    </article>
  );
}
