import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

const COLORS = ["#2f9e7d", "#f2c14e", "#c2415b", "#3a63b8"];
const PIECES = Array.from({ length: 24 }, (_, i) => ({
  id: i,
  x: Math.cos((i / 24) * Math.PI * 2) * (120 + (i % 4) * 30),
  y: Math.sin((i / 24) * Math.PI * 2) * (90 + (i % 3) * 25) - 60,
  rotate: (i % 2 ? 1 : -1) * (180 + i * 20),
  color: COLORS[i % COLORS.length],
}));

export function Confetti({ show }: { show: boolean }) {
  const reduced = useReducedMotion();
  if (reduced) return null;
  return (
    <AnimatePresence>
      {show && (
        <div
          aria-hidden="true"
          data-testid="confetti"
          className="pointer-events-none absolute inset-0 overflow-visible"
        >
          {PIECES.map((p) => (
            <motion.span
              key={p.id}
              className="absolute left-1/2 top-1/2 h-3 w-1.5 rounded-sm"
              style={{ backgroundColor: p.color }}
              initial={{ x: 0, y: 0, opacity: 1, rotate: 0 }}
              animate={{ x: p.x, y: p.y + 140, opacity: 0, rotate: p.rotate }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.6, ease: [0.2, 0.7, 0.4, 1] }}
            />
          ))}
        </div>
      )}
    </AnimatePresence>
  );
}
