import { errorMessage } from "@/api/client";
import { Button, toast } from "@/components/ui";
import { useMe, useUpdateMe } from "@/features/auth/hooks";

export function SupportiveBanner({ supportUrl }: { supportUrl?: string }) {
  const me = useMe();
  const update = useUpdateMe();
  if (!me.data?.profile?.supportive_mode) return null;
  return (
    <section
      aria-labelledby="supportive-heading"
      className="flex flex-col gap-2 rounded-lg border border-pine bg-pine-soft p-4"
    >
      <h2 id="supportive-heading" className="font-bold">
        Reminders are in supportive mode
      </h2>
      <p className="max-w-prose text-sm">
        Things look heavy right now, so Pulse switched to gentle, encouraging reminders. If you'd
        like to talk to someone, your campus has support available.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <a
          href={supportUrl ?? "https://988lifeline.org/"}
          target="_blank"
          rel="noopener noreferrer"
          className="font-bold text-pine-strong underline"
        >
          Find campus support
        </a>
        <Button
          size="sm"
          variant="secondary"
          pending={update.isPending}
          onClick={() =>
            update.mutate(
              { profile: { supportive_mode: false } },
              {
                onSuccess: () => toast.success("Back to your usual reminders."),
                onError: (e) => toast.error(errorMessage(e)),
              },
            )
          }
        >
          Switch back to my usual reminders
        </Button>
      </div>
    </section>
  );
}
