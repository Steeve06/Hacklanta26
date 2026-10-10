type Line = { state: "good" | "medium" | "bad" | "fresh" | "done"; gentle: string; sassy: string };

const LINES: Line[] = [
  {
    state: "fresh",
    gentle: "A fresh start. Let's take it one session at a time.",
    sassy: "Fresh start! I have high hopes. No pressure. (Some pressure.)",
  },
  {
    state: "done",
    gentle: "Everything's done. Take a real break.",
    sassy: "Everything's done? I'm suspicious, but mostly proud.",
  },
  {
    state: "good",
    gentle: "You're on track. Keep the rhythm going.",
    sassy: "Look at you, doing the plan. I could get used to this.",
  },
  {
    state: "medium",
    gentle: "A couple of things need attention. Here's what to look at.",
    sassy: "We're fine. Mostly. Let's not look too closely at that list.",
  },
  {
    state: "bad",
    gentle: "It's a heavy stretch. Let's pick the next small step together.",
    sassy: "I'm not crying, you're crying. Okay, we can fix this.",
  },
];

export function mascotLine(
  state: string,
  opts: { fresh: boolean; allDone: boolean; sass: number },
): string {
  const key = opts.allDone ? "done" : opts.fresh ? "fresh" : state;
  const line = LINES.find((l) => l.state === key) ?? LINES[2];
  return opts.sass <= 1 ? (line?.gentle ?? "") : (line?.sassy ?? "");
}
