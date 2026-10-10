import type { MascotMood } from "./types";

const body: Record<MascotMood, string> = { good: "#2f9e7d", medium: "#f2c14e", bad: "#c2415b" };

const mouth: Record<MascotMood, string> = {
  good: "M44 72 Q60 86 76 72",
  medium: "M46 76 L74 72",
  bad: "M46 80 Q60 68 74 80",
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
  const squint = mood === "medium";
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" aria-hidden="true" className={className}>
      <ellipse cx="60" cy="108" rx="34" ry="5" fill="#000" opacity="0.12" />
      <ellipse
        cx="60"
        cy={mood === "bad" ? 64 : 60}
        rx={mood === "bad" ? 47 : 44}
        ry={mood === "bad" ? 38 : 41}
        fill={body[mood]}
      />
      <ellipse cx="51" cy="57" rx="5.5" ry={squint ? 3.5 : 6.5} fill="#fff" />
      <ellipse cx="69" cy="57" rx="5.5" ry={squint ? 3.5 : 6.5} fill="#fff" />
      <circle cx={squint ? 53 : 51.5} cy={mood === "bad" ? 59.5 : 58} r="2.6" fill="#1c2230" />
      <circle cx={squint ? 71 : 69.5} cy={mood === "bad" ? 59.5 : 58} r="2.6" fill="#1c2230" />
      {mood === "bad" && <ellipse cx="46" cy="70" rx="2.2" ry="3.4" fill="#99d1ff" />}
      <path d={mouth[mood]} stroke="#1c2230" strokeWidth="3" fill="none" strokeLinecap="round" />
    </svg>
  );
}
