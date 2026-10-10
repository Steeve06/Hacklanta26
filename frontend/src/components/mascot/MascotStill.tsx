import type { MascotMood } from "./types";

const body: Record<MascotMood, string> = {
  good: "rgb(var(--pine))",
  medium: "rgb(var(--mustard))",
  bad: "rgb(var(--berry))",
};

const mouth: Record<MascotMood, string> = {
  good: "M44 70 Q60 84 76 70",
  medium: "M46 74 L74 72",
  bad: "M44 78 Q60 66 76 78",
};

export function MascotStill({
  mood,
  size = 120,
  className,
}: {
  mood: MascotMood;
  size?: number;
  className?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" aria-hidden="true" className={className}>
      <path
        d={
          mood === "bad"
            ? "M60 18c24 0 40 20 40 44 0 28-12 46-40 46S20 92 20 62c0-24 16-44 40-44z"
            : "M60 12c25 0 42 19 42 46 0 29-17 50-42 50S18 87 18 58c0-27 17-46 42-46z"
        }
        fill={body[mood]}
      />
      <ellipse cx="45" cy="54" rx="8" ry={mood === "medium" ? 5 : 9} fill="#fff" />
      <ellipse cx="75" cy="54" rx="8" ry={mood === "medium" ? 5 : 9} fill="#fff" />
      <circle cx={mood === "medium" ? 49 : 46} cy="56" r="4" fill="#1c2230" />
      <circle cx={mood === "medium" ? 79 : 76} cy="56" r="4" fill="#1c2230" />
      {mood === "bad" && (
        <path
          d="M39 64 q-2 8 0 12"
          stroke="#bfe3ff"
          strokeWidth="4"
          strokeLinecap="round"
          fill="none"
        />
      )}
      <path d={mouth[mood]} stroke="#1c2230" strokeWidth="4.5" fill="none" strokeLinecap="round" />
    </svg>
  );
}
