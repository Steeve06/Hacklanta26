import { useReducedMotion } from "framer-motion";
import { lazy, Suspense, useEffect, useState, type ComponentType, type CSSProperties } from "react";
import { MascotStill } from "./MascotStill";
import type { MascotMood, MascotMoment } from "./types";

type PlayerProps = {
  src: object;
  loop: boolean;
  autoplay: boolean;
  className?: string;
  style?: CSSProperties;
  subscriptions?: { complete?: () => void };
  "aria-hidden"?: boolean;
};

const Lottie = lazy(() =>
  import("lottie-react").then((m) => ({
    default: m.LottieLight as unknown as ComponentType<PlayerProps>,
  })),
);

type Clip = MascotMood | MascotMoment;

const loaders: Record<Clip, () => Promise<{ default: unknown }>> = {
  good: () => import("./animations/good.json"),
  medium: () => import("./animations/medium.json"),
  bad: () => import("./animations/bad.json"),
  celebrate: () => import("./animations/celebrate.json"),
  gasp: () => import("./animations/gasp.json"),
  fresh_start: () => import("./animations/fresh_start.json"),
};

const PLAYED_PREFIX = "pulse-moment:";

function alreadyPlayed(key: string): boolean {
  try {
    return window.sessionStorage.getItem(PLAYED_PREFIX + key) === "1";
  } catch {
    return false;
  }
}

function markPlayed(key: string): void {
  try {
    window.sessionStorage.setItem(PLAYED_PREFIX + key, "1");
  } catch {
    // Storage can be unavailable (private mode); the moment just replays next time.
  }
}

function useClip(clip: Clip): unknown {
  const [loaded, setLoaded] = useState<{ clip: Clip; data: unknown } | null>(null);
  useEffect(() => {
    let alive = true;
    void loaders[clip]().then((module) => {
      if (alive) setLoaded({ clip, data: module.default });
    });
    return () => {
      alive = false;
    };
  }, [clip]);
  return loaded?.clip === clip ? loaded.data : null;
}

type Props = {
  mood: MascotMood;
  moment?: { kind: MascotMoment; key: string } | null;
  size?: number;
  className?: string;
};

/** The mascot's state machine: loops the mood, interrupts once per new moment, then returns. */
export function Mascot({ mood, moment, size = 160, className }: Props) {
  const reduced = useReducedMotion();
  const [finished, setFinished] = useState<string | null>(null);
  const playing =
    moment && finished !== moment.key && !alreadyPlayed(moment.key) ? moment.kind : null;

  const clip: Clip = playing ?? mood;
  const data = useClip(clip);
  const still = <MascotStill mood={mood} size={size} className={className} />;

  if (reduced || !data) return still;
  return (
    <Suspense fallback={still}>
      <Lottie
        key={clip}
        src={data as object}
        loop={!playing}
        autoplay
        style={{ width: size, height: size }}
        className={className}
        aria-hidden
        subscriptions={{
          complete: () => {
            if (!moment) return;
            markPlayed(moment.key);
            setFinished(moment.key);
          },
        }}
      />
    </Suspense>
  );
}
