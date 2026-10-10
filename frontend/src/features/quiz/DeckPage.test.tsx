import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useAuth } from "@/features/auth/store";
import { renderRoute } from "@/test/render";
import type { DeckDetail, DeckItem } from "./api";
import { TodayDeckPage } from "./DeckPage";

const SOURCE = "CS 201 · Ch 5: Hashing";

function item(position: number, fields: Partial<DeckItem>): DeckItem {
  return {
    position,
    type: "flashcard",
    source: SOURCE,
    chapter_id: 5,
    course_id: 3,
    prompt: "",
    back: null,
    options: null,
    terms: null,
    clues: null,
    answered: false,
    correct: null,
    response: null,
    solution: null,
    ...fields,
  };
}

function makeDeck(): DeckDetail {
  return {
    id: 7,
    day: "2026-10-14",
    state: "open",
    question_count: 4,
    time_limit_seconds: 300,
    started_at: null,
    deadline: null,
    completed_at: null,
    knew: 0,
    xp: 0,
    counted_for_streak: false,
    milestone: null,
    streak: 2,
    focus: {
      kind: "upcoming",
      course_id: 3,
      course_code: "CS 201",
      assessment_id: 9,
      assessment_title: "Quiz 2: Hashing",
      due_at: "2026-10-16T03:59:00Z",
    },
    items: [
      item(0, {
        type: "mcq",
        prompt: "Fill in the blank: A ____ answers lookups in constant time.",
        options: ["collision", "hash table", "heap", "bucket"],
      }),
      item(1, { type: "short", prompt: "Fill in the blank: Two keys in one bucket is a ____." }),
      item(2, {
        type: "match",
        prompt: "Match each term to the sentence it completes.",
        terms: ["hash function", "open addressing", "separate chaining"],
        clues: [
          "____ stores a list per bucket.",
          "A ____ turns keys into integers.",
          "____ probes for a free slot.",
        ],
      }),
      item(3, { type: "flashcard", prompt: "What is chunking?", back: "Grouping items." }),
    ],
  };
}

// What the fake server accepts as right for each position, and what it reveals afterwards.
const KEY: Record<number, { right: unknown; solution: unknown }> = {
  0: {
    right: { choice: 1 },
    solution: {
      answer: "hash table",
      explanation: "A hash table answers lookups.",
      choice: 1,
    },
  },
  1: {
    right: { text: "collision" },
    solution: { answer: "collision", explanation: "Two keys in one bucket is a collision." },
  },
  2: { right: { pairs: [1, 2, 0] }, solution: { pairs: [1, 2, 0] } },
  3: {
    right: { knew: true },
    solution: { answer: "Grouping items.", explanation: "Grouping items." },
  },
};

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("TodayDeckPage", () => {
  let deck: DeckDetail;
  let answers: { position: number; response: unknown }[];

  beforeEach(() => {
    useAuth.setState({ status: "signed-in", access: "token" });
    deck = makeDeck();
    answers = [];
    globalThis.fetch = async (input: RequestInfo | URL) => {
      const request = input as Request;
      if (request.method === "POST" && request.url.endsWith("/api/v1/decks/7/start")) {
        const now = Date.now();
        deck = {
          ...deck,
          started_at: new Date(now).toISOString(),
          deadline: new Date(now + 300_000).toISOString(),
        };
        return json(deck);
      }
      if (request.method === "POST" && request.url.endsWith("/api/v1/decks/7/answer")) {
        const body = (await request.json()) as { position: number; response: unknown };
        answers.push(body);
        const key = KEY[body.position] ?? { right: null, solution: null };
        const correct = JSON.stringify(key.right) === JSON.stringify(body.response);
        deck = {
          ...deck,
          items: deck.items.map((i) =>
            i.position === body.position
              ? { ...i, answered: true, correct, response: body.response, solution: key.solution }
              : i,
          ),
        };
        if (deck.items.every((i) => i.answered)) {
          const knew = deck.items.filter((i) => i.correct).length;
          deck = {
            ...deck,
            state: "done",
            completed_at: new Date().toISOString(),
            counted_for_streak: true,
            knew,
            xp: knew * 10 + 20,
            streak: 3,
            milestone: 3,
          };
        }
        return json(deck);
      }
      if (request.url.endsWith("/api/v1/decks/today")) return json(deck);
      return new Response("{}", { status: 404 });
    };
  });

  it("runs a timed session through every question type", async () => {
    const user = userEvent.setup();
    renderRoute(<TodayDeckPage />, "/pulse/quiz/today");
    expect(await screen.findByText("5-minute session · 4 questions")).toBeInTheDocument();
    expect(screen.getByText(/Prep for Quiz 2: Hashing \(CS 201\), due/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start" }));

    // Multiple choice: a wrong pick shows the right answer
    expect(await screen.findByRole("timer")).toHaveTextContent(/^[45]:\d\d$/);
    await user.click(screen.getByRole("button", { name: /heap/ }));
    expect(await screen.findByText("Not quite")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /hash table.*correct answer/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));

    // Short answer
    await user.type(await screen.findByLabelText("Your answer"), "collision");
    await user.click(screen.getByRole("button", { name: "Check" }));
    expect(await screen.findByText("Correct! +10 XP")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));

    // Matching: tap a term, then its sentence
    const check = await screen.findByRole("button", { name: "Check" });
    expect(check).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "hash function" }));
    await user.click(screen.getByRole("button", { name: /turns keys into integers/ }));
    await user.click(screen.getByRole("button", { name: "open addressing" }));
    await user.click(screen.getByRole("button", { name: /probes for a free slot/ }));
    await user.click(screen.getByRole("button", { name: "separate chaining" }));
    await user.click(screen.getByRole("button", { name: /stores a list per bucket/ }));
    await user.click(screen.getByRole("button", { name: "Check" }));
    expect(await screen.findByText("Correct! +10 XP")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));

    // Flashcard: flip and rate yourself, which finishes the session
    await user.click(await screen.findByRole("button", { name: "Show answer" }));
    await user.click(screen.getByRole("button", { name: "Got it" }));

    expect(
      await screen.findByRole("heading", { name: "3 of 4 correct · +50 XP" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Counted for your streak: 3 days in a row. That's a 3-day milestone.",
    );
    expect(screen.getAllByRole("link", { name: "Review this in the chapter" })[0]).toHaveAttribute(
      "href",
      "/lms/courses/3/chapters/5",
    );
    expect(answers).toEqual([
      { position: 0, response: { choice: 2 } },
      { position: 1, response: { text: "collision" } },
      { position: 2, response: { pairs: [1, 2, 0] } },
      { position: 3, response: { knew: true } },
    ]);
  });
});
