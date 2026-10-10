import { MascotStill } from "@/components/mascot/MascotStill";
import { Button, Card, toast } from "@/components/ui";
import { install, isIos, useInstall } from "@/lib/pwa";

/** Put Leon on the home screen: one tap where the browser offers it, steps on iPhone. */
export function InstallCard() {
  const prompt = useInstall((s) => s.prompt);
  const installed = useInstall((s) => s.installed);
  const ios = isIos();

  let body: React.ReactNode;
  if (installed) {
    body = <p className="text-sm text-ink-soft">Leon is installed on this device.</p>;
  } else if (prompt) {
    body = (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-prose text-sm text-ink-soft">
          Open Leon from your home screen or dock, in its own window, like any other app.
        </p>
        <Button
          size="sm"
          onClick={() =>
            void install().then((ok) => {
              if (ok) toast.success("Leon is installed.");
            })
          }
        >
          Install Leon
        </Button>
      </div>
    );
  } else if (ios) {
    body = (
      <ol className="list-decimal pl-5 text-sm text-ink-soft">
        <li>In Safari, tap the Share button.</li>
        <li>Choose Add to Home Screen, then Add.</li>
        <li>Open Leon from your Home Screen and turn on push below.</li>
      </ol>
    );
  } else {
    body = (
      <p className="text-sm text-ink-soft">
        Your browser can install Leon from its menu (look for Install app or Add to Home screen). On
        a phone, Leon needs to be opened over HTTPS for this; see the README.
      </p>
    );
  }
  return (
    <Card aria-labelledby="install-heading" className="flex items-start gap-4">
      <MascotStill pose="nudge" size={56} className="hidden shrink-0 sm:block" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <h2 id="install-heading" className="text-lg font-bold">
          Leon on this device
        </h2>
        {body}
      </div>
    </Card>
  );
}
