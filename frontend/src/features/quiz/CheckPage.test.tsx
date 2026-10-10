import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { useAuth } from "@/features/auth/store";
import type { CheckCard, CheckDetail } from "./api";
import { CheckPage } from "./CheckPage";

vi.mock("@/components/mascot/Mascot", () => ({ Mascot: () => null }));

const QUESTIONS: { front: string; options: string[]; answer: number }[] = [
  { front: "What does spaced practice spread out?", options: ["Study", "Sleep"], answer: 0 },
  { front: "Retrieval practice means rereading.", options: ["True", "False"], answer: 1 },
];

function question(position: number) {
  const q = QUESTIONS[position];
  if (!q) throw new Error(`no question ${position}`);
  return q;
}

function card(position: number): CheckCard {
  const q = question(position);
  return {
    position,
    kind: "choice",
    type: "multiple_choice",
    terms: [],
    clues: [],
    front: q.front,
    options: q.options,
    source: "PSY 101 · Ch 3: Learning Strategies",
    chapter_id: 5,
    course_id: 3,
    result: null,
  };
}

function makeCheck(): CheckDetail {
  return {
    id: 7,
    title: "PSY 101 Ch 3",
    chapters: [{ id: 5, course_id: 3, course_code: "PSY 101", order: 3, title: "Learning" }],
    kind: "scheduled",
    scheduled_date: "2026-10-14",
    opens_at: "2026-10-14T04:00:00Z",
    closes_at: "2099-10-16T03:59:59Z",
    state: "open",
    passed: false,
    counted_for_streak: false,
    tries_left: 2,
    best_correct: null,
    card_count: 2,
    pass_mark: 2,
    attempt: null,
    milestone: null,
    streak: 2,
  };
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function renderCheck() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/pulse/checks/:checkId", element: <CheckPage /> }], {
    initialEntries: ["/pulse/checks/7"],
  });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("CheckPage", () => {
  let check: CheckDetail;
  let answers: { position: number; choice: number }[];

  beforeEach(() => {
    useAuth.setState({ status: "signed-in", access: "token" });
    check = makeCheck();
    answers = [];
    globalThis.fetch = async (input: RequestInfo | URL) => {
      const request = input as Request;
      if (request.method === "POST" && request.url.endsWith("/api/v1/checks/7/start")) {
        check = {
          ...check,
          attempt: {
            number: 1,
            correct: 0,
            finished: false,
            timed_out: false,
            expires_at: new Date(Date.now() + 180_000).toISOString(),
            xp: 0,
            cards: [card(0), card(1)],
          },
        };
        return json(check);
      }
      if (request.method === "POST" && request.url.endsWith("/api/v1/checks/7/answer")) {
        const body = (await request.json()) as { position: number; choice: number };
        answers.push(body);
        const attempt = check.attempt;
        if (!attempt) return new Response("{}", { status: 400 });
        const right = question(body.position).answer;
        const cards = attempt.cards.map((c) =>
          c.position === body.position
            ? {
                ...c,
                result: {
                  chosen: body.choice,
                  answer: right,
                  correct: body.choice === right,
                  explanation: "Because the chapter says so.",
                  source_excerpt: "spreads study over several sessions",
                  given_text: null,
                  expected_text: null,
                  pairs: null,
                  right_pairs: null,
                },
              }
            : c,
        );
        const finished = cards.every((c) => c.result !== null);
        const correct = cards.filter((c) => c.result?.correct).length;
        check = {
          ...check,
          attempt: { ...attempt, cards, correct, finished, xp: finished ? correct * 10 + 20 : 0 },
          ...(finished
            ? {
                state: "passed",
                passed: true,
                counted_for_streak: true,
                streak: 3,
                milestone: 3,
                tries_left: 0,
              }
            : {}),
        };
        return json(check);
      }
      if (request.url.endsWith("/api/v1/checks/7")) return json(check);
      return new Response("{}", { status: 404 });
    };
  });

  it("answers each card, shows why, and reports the streak", async () => {
    renderCheck();
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));

    expect(await screen.findByText(question(0).front)).toBeInTheDocument();
    expect(screen.getByRole("timer")).toHaveTextContent(/^[23]:\d\d$/);
    await userEvent.click(screen.getByRole("button", { name: "Study" }));
    expect(await screen.findByText("Right")).toBeInTheDocument();
    expect(screen.getByText(/From the chapter/)).toHaveTextContent(
      "spreads study over several sessions",
    );
    await userEvent.click(screen.getByRole("button", { name: "Next card" }));

    expect(await screen.findByText(question(1).front)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "False" }));
    await userEvent.click(await screen.findByRole("button", { name: "See how you did" }));

    expect(await screen.findByRole("heading", { name: "2 of 2 right" })).toBeInTheDocument();
    expect(screen.getByText("Passed. 3 checks in a row: that's a milestone.")).toBeInTheDocument();
    expect(screen.getByText("+40 XP")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Review this chapter/ })).toHaveAttribute(
      "href",
      "/lms/courses/3/chapters/5",
    );
    expect(answers).toEqual([
      { position: 0, choice: 0 },
      { position: 1, choice: 1 },
    ]);
  });

  it("hides the options' answers until a card is answered", async () => {
    renderCheck();
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    await screen.findByText(question(0).front);
    expect(screen.queryByText("Right")).not.toBeInTheDocument();
    expect(screen.queryByText(/From the chapter/)).not.toBeInTheDocument();
  });
});
