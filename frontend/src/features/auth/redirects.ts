import type { Me } from "./hooks";

export const TODAY = "/pulse/today";
export const ONBOARDING = "/onboarding";

export function needsOnboarding(me: Pick<Me, "role" | "profile">): boolean {
  return me.role === "student" && !me.profile?.onboarding_done;
}

export function homeFor(me: Pick<Me, "role" | "profile">): string {
  if (me.role !== "student") return "/lms";
  return needsOnboarding(me) ? ONBOARDING : TODAY;
}

/** Only same-app paths are accepted as `next`, so a link can't send people elsewhere. */
export function safeNext(raw: string | null): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return null;
  if (["/login", "/signup", "/forgot-password", "/reset-password"].some((p) => raw.startsWith(p)))
    return null;
  return raw;
}

/** Where to go after signing in: the page they asked for, unless their role can't open it or
 * they still have onboarding to finish. */
export function destinationAfterLogin(me: Pick<Me, "role" | "profile">, next: string | null) {
  const wanted = safeNext(next);
  if (needsOnboarding(me)) return ONBOARDING;
  if (!wanted || wanted === "/") return homeFor(me);
  if (me.role !== "student" && (wanted.startsWith("/pulse") || wanted === ONBOARDING))
    return homeFor(me);
  if (wanted === ONBOARDING) return homeFor(me);
  return wanted;
}
