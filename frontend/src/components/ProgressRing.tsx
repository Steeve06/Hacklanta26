import { motion, useReducedMotion } from "framer-motion";

const stroke: Record<string, string> = { good: "#2f9e7d", medium: "#d9a21b", bad: "#c2415b" };

export function ProgressRing({
  value,
  state,
  size = 44,
  label,
}: {
  value: number;
  state: string;
  size?: number;
  label: string;
}) {
  const reduced = useReducedMotion();
  const radius = size / 2 - 4;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(100, value)) / 100;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="rgb(var(--sunken))"
        strokeWidth="4"
      />
      <motion.circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={stroke[state] ?? stroke.good}
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={circumference}
        initial={{ strokeDashoffset: reduced ? circumference * (1 - pct) : circumference }}
        animate={{ strokeDashoffset: circumference * (1 - pct) }}
        transition={{ duration: reduced ? 0 : 0.9, ease: "easeOut" }}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text
        x="50%"
        y="50%"
        dominantBaseline="central"
        textAnchor="middle"
        fontSize={size / 3.4}
        fontWeight="700"
        fill="rgb(var(--ink))"
      >
        {Math.round(value)}
      </text>
    </svg>
  );
}
