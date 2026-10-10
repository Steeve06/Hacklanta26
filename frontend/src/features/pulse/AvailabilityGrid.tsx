import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { cx } from "@/lib/cx";
import type { AvailabilityBlock } from "./api";
import { fromSlots, toSlots, WEEKDAYS } from "./availability";

const FIRST_HOUR = 6;
const HOURS = Array.from({ length: 24 - FIRST_HOUR }, (_, i) => FIRST_HOUR + i);
const SHORT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function hourLabel(hour: number): string {
  if (hour === 12) return "12 PM";
  return hour < 12 ? `${hour} AM` : `${hour - 12} PM`;
}

function endLabel(hour: number): string {
  return hour + 1 === 24 ? "midnight" : hourLabel(hour + 1);
}

type Cell = { day: number; hour: number };
type Fill = "full" | "half" | "empty";

/** A week of one-hour cells, 6 AM to midnight. Tap or click a cell to toggle it, drag with a
 * mouse to paint several, or move with the arrow keys and press Space. Half-hour blocks made
 * with the exact-times editor show as half-filled cells and are kept unless you toggle them. */
export function AvailabilityGrid({
  value,
  onChange,
}: {
  value: AvailabilityBlock[];
  onChange: (blocks: AvailabilityBlock[]) => void;
}) {
  const slots = toSlots(value);
  const [focus, setFocus] = useState<Cell>({ day: 0, hour: 18 });
  const paint = useRef<{ fill: boolean; touched: Set<string>; slots: Set<string> } | null>(null);
  const cells = useRef(new Map<string, HTMLButtonElement>());

  const fillOf = (day: number, hour: number, from: Set<string> = slots): Fill => {
    const a = from.has(`${day}:${hour * 2}`);
    const b = from.has(`${day}:${hour * 2 + 1}`);
    return a && b ? "full" : a || b ? "half" : "empty";
  };

  const setCell = (from: Set<string>, { day, hour }: Cell, on: boolean) => {
    for (const i of [hour * 2, hour * 2 + 1]) {
      if (on) from.add(`${day}:${i}`);
      else from.delete(`${day}:${i}`);
    }
  };

  const toggle = (cell: Cell) => {
    const next = new Set(slots);
    setCell(next, cell, fillOf(cell.day, cell.hour) !== "full");
    onChange(fromSlots(next));
  };

  const cellFromPoint = (x: number, y: number): Cell | null => {
    const el = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-cell]");
    if (!el?.dataset.cell) return null;
    const [day, hour] = el.dataset.cell.split(":").map(Number);
    return day === undefined || hour === undefined ? null : { day, hour };
  };

  const onPointerDown = (event: PointerEvent<HTMLButtonElement>, cell: Cell) => {
    if (event.pointerType === "touch") return;
    event.preventDefault();
    const fill = fillOf(cell.day, cell.hour) !== "full";
    const next = new Set(slots);
    setCell(next, cell, fill);
    paint.current = { fill, touched: new Set([`${cell.day}:${cell.hour}`]), slots: next };
    setFocus(cell);
    onChange(fromSlots(next));
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const state = paint.current;
    if (!state) return;
    const cell = cellFromPoint(event.clientX, event.clientY);
    if (!cell || state.touched.has(`${cell.day}:${cell.hour}`)) return;
    state.touched.add(`${cell.day}:${cell.hour}`);
    setCell(state.slots, cell, state.fill);
    onChange(fromSlots(state.slots));
  };

  const endPaint = () => {
    paint.current = null;
  };

  const moveFocus = (event: KeyboardEvent<HTMLButtonElement>, cell: Cell) => {
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const move = moves[event.key];
    if (!move) return;
    event.preventDefault();
    const next = {
      day: Math.min(6, Math.max(0, cell.day + move[0])),
      hour: Math.min(23, Math.max(FIRST_HOUR, cell.hour + move[1])),
    };
    setFocus(next);
    cells.current.get(`${next.day}:${next.hour}`)?.focus();
  };

  const hidden = value.some((b) => Number(b.start_time.slice(0, 2)) < FIRST_HOUR);

  return (
    <div className="flex flex-col gap-2">
      <div
        role="grid"
        aria-label="Weekly study time"
        className="select-none"
        onPointerMove={onPointerMove}
        onPointerUp={endPaint}
        onPointerLeave={endPaint}
        onPointerCancel={endPaint}
      >
        <div role="row" className="grid grid-cols-[2.5rem_repeat(7,minmax(0,1fr))] gap-px">
          <span role="columnheader">
            <span className="sr-only">Time</span>
          </span>
          {SHORT_DAYS.map((d, i) => (
            <span
              key={d}
              role="columnheader"
              aria-label={WEEKDAYS[i]}
              className="pb-1 text-center text-xs font-bold text-ink-soft"
            >
              {d}
            </span>
          ))}
        </div>
        <div className="overflow-hidden rounded-md border border-line bg-line">
          {HOURS.map((hour) => (
            <div
              key={hour}
              role="row"
              className="grid grid-cols-[2.5rem_repeat(7,minmax(0,1fr))] gap-px"
            >
              <span
                role="rowheader"
                className="flex items-start justify-end bg-surface pr-1 pt-0.5 text-[0.65rem] leading-tight text-ink-soft"
              >
                {hourLabel(hour)}
              </span>
              {SHORT_DAYS.map((_, day) => {
                const fill = fillOf(day, hour);
                const key = `${day}:${hour}`;
                const focused = focus.day === day && focus.hour === hour;
                return (
                  <span key={key} role="gridcell" className="flex">
                    <button
                      type="button"
                      data-cell={key}
                      ref={(el) => {
                        if (el) cells.current.set(key, el);
                        else cells.current.delete(key);
                      }}
                      tabIndex={focused ? 0 : -1}
                      aria-pressed={fill === "full" ? true : fill === "half" ? "mixed" : false}
                      aria-label={`${WEEKDAYS[day]} ${hourLabel(hour)} to ${endLabel(hour)}`}
                      onPointerDown={(e) => onPointerDown(e, { day, hour })}
                      onClick={(e) => {
                        if (e.detail === 0 || paintedByTouch(e)) toggle({ day, hour });
                      }}
                      onKeyDown={(e) => moveFocus(e, { day, hour })}
                      onFocus={() => setFocus({ day, hour })}
                      className={cx(
                        "relative h-11 w-full focus-visible:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink",
                        fill === "full" ? "bg-pine" : "bg-surface hover:bg-pine-soft",
                      )}
                    >
                      {fill === "half" && (
                        <span
                          aria-hidden="true"
                          className="absolute inset-x-0 bottom-0 h-1/2 bg-pine/60"
                        />
                      )}
                    </button>
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-ink-soft">
        Tap a cell to add or remove that hour. With a mouse you can drag across cells; with a
        keyboard, use the arrow keys and Space.
        {hidden && " Some study time before 6 AM is kept but not shown here."}
      </p>
    </div>
  );
}

/** Touch taps toggle on click (no drag painting on touch, so the page can still scroll). Mouse
 * presses were already handled on pointer down. */
function paintedByTouch(event: React.MouseEvent<HTMLButtonElement>): boolean {
  const native = event.nativeEvent as globalThis.PointerEvent;
  return native.pointerType === "touch" || native.pointerType === "";
}
