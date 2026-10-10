import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useAuth } from "@/features/auth/store";
import { renderRoute } from "@/test/render";
import type { DeckDetail } from "./api";
import { TodayDeckPage } from "./DeckPage";

function makeDeck(): DeckDetail {
  return {
    id: 7,
    day: "2026-10-14",
    state: "open",
    card_count: 2,
    started_at: null,
    completed_at: null,
    knew: 0,
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
    cards: [
      {
        id: 1,
        topic: "course",
        source: "CS 201 · Ch 5: Hashing",
        front: "What is chunking?",
        back: "Grouping items.",
        knew: null,
        chapter_id: 5,
        course_id: 3,
      },
      {
        id: 2,
        topic: "focus",
        source: "Focus",
        front: "What is deep work?",
        back: "Focused time.",
        knew: null,
        chapter_id: null,
        course_id: null,
      },
    ],
  };
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("TodayDeckPage", () => {
  let deck: DeckDetail;
  let reviews: unknown[];

  beforeEach(() => {
    useAuth.setState({ status: "signed-in", access: "token" });
    deck = makeDeck();
    reviews = [];
    globalThis.fetch = async (input: RequestInfo | URL) => {
      const request = input as Request;
      if (request.method === "POST" && request.url.endsWith("/api/v1/decks/7/review")) {
        const body = (await request.json()) as { card_id: number; knew: boolean };
        reviews.push(body);
        deck = {
          ...deck,
          cards: deck.cards.map((c) => (c.id === body.card_id ? { ...c, knew: body.knew } : c)),
        };
        if (deck.cards.every((c) => c.knew !== null)) {
          deck = {
            ...deck,
            state: "done",
            completed_at: "2026-10-14T16:00:00Z",
            counted_for_streak: true,
            knew: deck.cards.filter((c) => c.knew).length,
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

  it("flips a card, rates it and moves on until the deck is done", async () => {
    renderRoute(<TodayDeckPage />, "/pulse/quiz/today");
    expect(await screen.findByText("What is chunking?")).toBeInTheDocument();
    expect(screen.getByText(/Prep for Quiz 2: Hashing \(CS 201\), due/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Got it" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Show answer" }));
    expect(screen.getByText("Grouping items.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));

    expect(await screen.findByText("What is deep work?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show answer" }));
    await userEvent.click(screen.getByRole("button", { name: "Still learning" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Counted for your streak: 3 days in a row. That's a 3-day milestone.",
    );
    expect(screen.getByRole("link", { name: "Review this in the chapter" })).toHaveAttribute(
      "href",
      "/lms/courses/3/chapters/5",
    );
    expect(reviews).toEqual([
      { card_id: 1, knew: true },
      { card_id: 2, knew: false },
    ]);
  });
});
