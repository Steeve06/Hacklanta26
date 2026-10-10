import { useState } from "react";
import { PushToggle } from "@/features/notifications/PushToggle";
import { NotificationStyleFields } from "@/features/pulse/NotificationStyleFields";
import { styleErrors, type NotificationStyle } from "@/features/pulse/preferences";
import type { StepProps } from "../stepTypes";
import { StepFooter } from "../StepFooter";

export function NotificationsStep({ state, saving, submit, goTo, error }: StepProps) {
  const saved = state.notifications;
  const [style, setStyle] = useState<NotificationStyle>({
    sass_level: saved.sass_level,
    quiet_start: saved.quiet_start.slice(0, 5),
    quiet_end: saved.quiet_end.slice(0, 5),
  });
  return (
    <section aria-label="Reminders" className="flex flex-col gap-4">
      <NotificationStyleFields value={style} onChange={setStyle} disabled={saving} />
      <div className="rounded-lg border border-line bg-surface p-4">
        <h2 className="mb-1 font-bold">Reminders on this device (optional)</h2>
        <PushToggle />
      </div>
      <StepFooter
        onBack={() => goTo(3)}
        onNext={() => submit({ ...style })}
        nextLabel="Build my schedule"
        nextDisabled={Object.keys(styleErrors(style)).length > 0}
        saving={saving}
        error={error}
      />
    </section>
  );
}
