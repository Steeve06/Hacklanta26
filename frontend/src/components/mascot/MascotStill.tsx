import { MOOD_POSE, POSE_SRC } from "./poses";
import type { MascotMood, MascotPose } from "./types";

/** Leon, standing still: a mood's picture, or a specific pose. Decorative; the text around it
 * always says the same thing. */
export function MascotStill({
  mood = "good",
  pose,
  size = 120,
  className,
}: {
  mood?: MascotMood;
  pose?: MascotPose;
  size?: number;
  className?: string;
}) {
  return (
    <img
      src={POSE_SRC[pose ?? MOOD_POSE[mood]]}
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      decoding="async"
      draggable={false}
      className={className}
      style={{ width: size, height: size, objectFit: "contain" }}
    />
  );
}
