import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { CheckCard } from "./api";
import { MatchCard } from "./MatchCard";

const base: CheckCard = {
  position: 2,
  kind: "match",
  type: "matching",
  front: "Match each key term to the sentence it completes.",
  options: [],
  terms: ["Spaced practice", "Interleaving", "Elaboration"],
  clues: [
    "_____ mixes problem types.",
    "_____ spreads study over several sessions.",
    "_____ connects new ideas to old ones.",
  ],
  source: "PSY 101 · Ch 3: Learning Strategies",
  chapter_id: 5,
  course_id: 3,
  result: null,
};

describe("MatchCard", () => {
  it("pairs each term with a sentence before it can be checked", async () => {
    const onAnswer = vi.fn();
    render(<MatchCard card={base} pending={false} onAnswer={onAnswer} />);
    const check = screen.getByRole("button", { name: "Check" });
    expect(check).toBeDisabled();
    const pick = async (term: string, clue: RegExp) => {
      await userEvent.click(screen.getByRole("button", { name: new RegExp(term) }));
      await userEvent.click(screen.getByRole("button", { name: clue }));
    };
    await pick("Spaced practice", /spreads study/);
    await pick("Interleaving", /mixes problem/);
    await pick("Elaboration", /connects new/);
    await userEvent.click(check);
    expect(onAnswer).toHaveBeenCalledWith([1, 0, 2]);
  });

  it("shows which matches were wrong and the right term", () => {
    render(
      <MatchCard
        card={{
          ...base,
          result: {
            correct: false,
            explanation: "",
            source_excerpt: "",
            chosen: null,
            answer: null,
            given_text: null,
            expected_text: null,
            pairs: [0, 1, 2],
            right_pairs: [1, 0, 2],
          },
        }}
        pending={false}
        onAnswer={() => undefined}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Not all matched.");
    expect(screen.getByText("Answer: Interleaving")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /connects new.*right\)/ })).toBeInTheDocument();
  });
});
