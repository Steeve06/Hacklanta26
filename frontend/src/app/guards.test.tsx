import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { useAuth } from "@/features/auth/store";
import { OnboardingGate } from "@/features/onboarding/OnboardingGate";
import { PulseGate } from "@/features/pulse/PulseGate";
import { json, mockFetch, studentMe } from "@/test/fetchMock";
import { PublicOnly } from "./PublicOnly";
import { RequireAuth } from "./RequireAuth";

function app(path: string) {
  const page = (text: string) => <p>{text}</p>;
  const router = createMemoryRouter(
    [
      { element: <PublicOnly />, children: [{ path: "/login", element: page("login page") }] },
      {
        element: <RequireAuth />,
        children: [
          {
            path: "/onboarding",
            element: <OnboardingGate />,
            children: [{ index: true, element: page("onboarding page") }],
          },
          {
            path: "/pulse",
            element: <PulseGate />,
            children: [{ path: "today", element: page("today page") }],
          },
          { path: "/lms", element: page("lms page") },
        ],
      },
    ],
    { initialEntries: [path] },
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function signedInAs(me: ReturnType<typeof studentMe>) {
  mockFetch({
    "POST /api/v1/auth/refresh": () => json({ access: "token" }),
    "GET /api/v1/me": () => json(me),
  });
}

describe("route guards", () => {
  beforeEach(() => useAuth.setState({ status: "unknown", access: null }));

  it("sends signed-out visitors to sign in and remembers where they were going", async () => {
    mockFetch({ "POST /api/v1/auth/refresh": () => json({ detail: "Session expired." }, 401) });
    const router = app("/pulse/today");
    expect(await screen.findByText("login page")).toBeInTheDocument();
    expect(router.state.location.search).toBe("?next=%2Fpulse%2Ftoday");
  });

  it("shows Can't reach the server instead of signing out when the backend is down", async () => {
    mockFetch({ "POST /api/v1/auth/refresh": () => json({}, 503) });
    app("/pulse/today");
    expect(await screen.findByRole("heading", { name: "Can't reach the server" })).toBeVisible();
  });

  it("keeps students out of Leon until onboarding is done", async () => {
    signedInAs(studentMe(false));
    app("/pulse/today");
    expect(await screen.findByText("onboarding page")).toBeInTheDocument();
  });

  it("sends onboarded students away from onboarding and sign-in", async () => {
    signedInAs(studentMe(true));
    app("/onboarding");
    expect(await screen.findByText("today page")).toBeInTheDocument();
  });

  it("redirects signed-in users who open /login", async () => {
    signedInAs(studentMe(true));
    app("/login");
    expect(await screen.findByText("today page")).toBeInTheDocument();
  });

  it("sends instructors who open onboarding or Leon to Learning Hub", async () => {
    signedInAs(studentMe(false, "instructor"));
    app("/onboarding");
    expect(await screen.findByText("lms page")).toBeInTheDocument();
  });
});
