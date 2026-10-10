import breakup from "./art/breakup.webp";
import calm from "./art/calm.webp";
import disappointed from "./art/disappointed.webp";
import nudge from "./art/nudge.webp";
import redemption from "./art/redemption.webp";
import started from "./art/started.webp";
import voiceNote from "./art/voice-note.webp";
import type { MascotMood, MascotMoment, MascotPose } from "./types";

export const POSE_SRC: Record<MascotPose, string> = {
  calm,
  nudge,
  started,
  "voice-note": voiceNote,
  disappointed,
  breakup,
  redemption,
};

export const MOOD_POSE: Record<MascotMood, MascotPose> = {
  good: "calm",
  medium: "disappointed",
  bad: "voice-note",
};

export const MOMENT_POSE: Record<MascotMoment, MascotPose> = {
  celebrate: "redemption",
  gasp: "breakup",
  fresh_start: "started",
};
