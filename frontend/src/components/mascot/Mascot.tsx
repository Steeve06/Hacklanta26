import { motion, useReducedMotion, type TargetAndTransition } from "framer-motion";
import { useEffect, useState } from "react";
import { MascotStill } from "./MascotStill";
import { MOMENT_POSE, MOOD_POSE, POSE_SRC } from "./poses";
import type { MascotMood, MascotMoment } from "./types";

const PLAYED_PREFIX = "leon-moment:";
const MOMENT_MS = 1800;

/** A slow loop per mood: Leon breathes when things are fine, side-eyes when they're slipping,
 * and droops when they're not. */
const MOOD_LOOP: Record<MascotMood, TargetAndTransition> = {
  good: {
    scale: [1, 1.03, 1],
    y: [0, -2, 0],
    transition: { duration: 3.2, repeat: Infinity, ease: "easeInOut" },
  },
  medium: {
    rotate: [0, -3, 0, 3, 0],
    transition: { duration: 4, repeat: Infinity, ease: "easeInOut" },
  },
  bad: {
    y: [0, 4, 0],
    scaleY: [1, 0.97, 1],
    transition: { duration: 2.6, repeat: Infinity, ease: "easeInOut" },
  },
};

/** One-shot moments, played once per key and then back to the mood. */
const MOMENT_PLAY: Record<MascotMoment, TargetAndTransition> = {
  celebrate: {
    y: [0, -18, 0, -10, 0],
    rotate: [0, -6, 6, -3, 0],
    scale: [1, 1.08, 1, 1.04, 1],
    transition: { duration: 1.6, ease: "easeOut" },
  },
  gasp: {
    x: [0, -6, 6, -4, 4, 0],
    transition: { duration: 0.8, ease: "easeInOut" },
  },
  fresh_start: {
    scale: [0.6, 1.1, 1],
    opacity: [0, 1, 1],
    transition: { duration: 0.9, ease: "easeOut" },
  },
};

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

type Props = {
  mood: MascotMood;
  moment?: { kind: MascotMoment; key: string } | null;
  size?: number;
  className?: string;
};

/** Leon's state machine: loops the mood, interrupts once per new moment, then returns. */
export function Mascot({ mood, moment, size = 160, className }: Props) {
  const reduced = useReducedMotion();
  const [finished, setFinished] = useState<string | null>(null);
  const playing =
    moment && finished !== moment.key && !alreadyPlayed(moment.key) ? moment.kind : null;

  useEffect(() => {
    if (!playing || !moment) return;
    const timer = window.setTimeout(() => {
      markPlayed(moment.key);
      setFinished(moment.key);
    }, MOMENT_MS);
    return () => window.clearTimeout(timer);
  }, [playing, moment]);

  const pose = playing ? MOMENT_POSE[playing] : MOOD_POSE[mood];
  if (reduced) return <MascotStill pose={pose} size={size} className={className} />;
  return (
    <motion.img
      key={playing ?? mood}
      src={POSE_SRC[pose]}
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      draggable={false}
      decoding="async"
      className={className}
      style={{ width: size, height: size, objectFit: "contain", transformOrigin: "50% 85%" }}
      animate={playing ? MOMENT_PLAY[playing] : MOOD_LOOP[mood]}
    />
  );
}
