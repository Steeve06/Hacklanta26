import { vi } from "vitest";

type Handler = (request: Request) => Response | Promise<Response>;

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Route fetch calls by "METHOD /path"; anything unmatched is a 404. */
export function mockFetch(routes: Record<string, Handler>) {
  const spy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(String(input), init);
    const url = new URL(request.url);
    const handler = routes[`${request.method} ${url.pathname}`];
    return handler ? handler(request) : json({ detail: "Not found." }, 404);
  });
  globalThis.fetch = spy as typeof fetch;
  return spy;
}

export const studentMe = (onboardingDone: boolean, role = "student") => ({
  id: 1,
  email: "nia@example.edu",
  first_name: "Nia",
  last_name: "Okoro",
  role,
  timezone: "America/New_York",
  server_now: new Date().toISOString(),
  demo_mode: false,
  profile: role === "student" ? { onboarding_done: onboardingDone, sass_level: 2 } : null,
});
