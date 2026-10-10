import { MascotStill } from "@/components/mascot/MascotStill";
import { Button } from "@/components/ui";

export function ServerUnreachable({
  onRetry,
  retrying,
}: {
  onRetry: () => void;
  retrying: boolean;
}) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-start justify-center gap-4 px-4">
      <MascotStill mood="medium" size={88} />
      <h1 className="text-2xl font-bold">Can't reach the server</h1>
      <p className="text-ink-soft">
        Pulse isn't answering. If you just started it, it may still be starting up. Your work is
        saved.
      </p>
      <Button onClick={onRetry} pending={retrying} pendingLabel="Trying again…">
        Retry
      </Button>
    </main>
  );
}
