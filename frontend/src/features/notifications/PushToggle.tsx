import { useEffect, useState } from "react";
import { Button, toast } from "@/components/ui";
import { errorMessage } from "@/api/client";
import { isIos } from "@/lib/pwa";
import { disablePush, enablePush, pushState, sendTestPush, type PushState } from "./push";

const explain: Record<PushState, string> = {
  unsupported: isIos()
    ? "On iPhone and iPad, add Leon to your Home Screen first (Share, then Add to Home Screen), open it from there, and turn on push. Reminders still appear in your inbox."
    : "This browser doesn't support push notifications. Reminders still appear in your inbox.",
  unavailable:
    "Push isn't set up on this server. Reminders still appear in your inbox and by email.",
  blocked:
    "Notifications are blocked for this site in your browser settings. Your inbox still works.",
  off: "Get reminders on this device even when Leon isn't open.",
  on: "Reminders are sent to this device.",
};

export function PushToggle({ onDone }: { onDone?: () => void }) {
  const [state, setState] = useState<PushState | null>(null);
  const [pending, setPending] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    pushState()
      .then(setState)
      .catch(() => setState("unavailable"));
  }, []);

  if (state === null) return <p className="text-sm text-ink-soft">Checking this device…</p>;
  const toggle = async () => {
    setPending(true);
    try {
      const next = state === "on" ? await disablePush() : await enablePush();
      setState(next);
      if (next === "on") toast.success("Push notifications are on for this device.");
      onDone?.();
    } catch {
      toast.error("Couldn't change push notifications. Try again.");
    } finally {
      setPending(false);
    }
  };
  const test = async () => {
    setTesting(true);
    try {
      const sent = await sendTestPush();
      toast.success(
        sent ? "Test sent. It should arrive in a few seconds." : "No device accepted the test.",
      );
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setTesting(false);
    }
  };
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="max-w-prose text-sm text-ink-soft">{explain[state]}</p>
      <div className="flex flex-wrap gap-2">
        {state === "on" && (
          <Button
            size="sm"
            variant="ghost"
            pending={testing}
            pendingLabel="Sending…"
            onClick={() => void test()}
          >
            Send a test notification
          </Button>
        )}
        {(state === "on" || state === "off") && (
          <Button
            size="sm"
            variant={state === "on" ? "secondary" : "primary"}
            pending={pending}
            pendingLabel="Working…"
            onClick={() => void toggle()}
          >
            {state === "on" ? "Turn off push" : "Turn on push"}
          </Button>
        )}
      </div>
    </div>
  );
}
