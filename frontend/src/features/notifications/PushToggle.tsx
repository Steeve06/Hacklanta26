import { useEffect, useState } from "react";
import { Button, toast } from "@/components/ui";
import { disablePush, enablePush, pushState, type PushState } from "./push";

const explain: Record<PushState, string> = {
  unsupported:
    "This browser doesn't support push notifications. Reminders still appear in your inbox.",
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
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="max-w-prose text-sm text-ink-soft">{explain[state]}</p>
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
  );
}
