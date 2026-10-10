import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import { useAuth } from "@/features/auth/store";
import { json, mockFetch } from "@/test/fetchMock";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { renderRoute } from "@/test/render";
import type { ChatMessage, Conversation } from "./api";
import { AssistantPanel } from "./AssistantPanel";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
});

beforeEach(() => {
  useAuth.setState({ status: "signed-in", access: "token" });
});

const NOW = "2026-10-14T12:00:00Z";

function message(over: Partial<ChatMessage>): ChatMessage {
  return {
    id: 1,
    role: "assistant",
    text: "",
    state: "done",
    changes: [],
    proposal: "none",
    proposal_note: "",
    link: null,
    created_at: NOW,
    ...over,
  };
}

function conversation(messages: ChatMessage[]): Conversation {
  return { id: messages.length ? 3 : null, created_at: messages.length ? NOW : null, messages };
}

const proposal = message({
  id: 2,
  text: "I can skip it and spread the work over later sessions.",
  changes: [{ type: "skip_session", summary: "Skip “PSY 101 · Read Ch 4” (Wed Oct 14, 6:00 PM)." }],
  proposal: "pending",
});
const question = message({ id: 1, role: "student", text: "Skip my next session" });

describe("AssistantPanel", () => {
  it("offers examples and sends one as a message", async () => {
    let sent = "";
    mockFetch({
      "GET /api/v1/assistant/conversation": () => json(conversation([])),
      "POST /api/v1/assistant/messages": async (request) => {
        sent = ((await request.json()) as { text: string }).text;
        return json(conversation([question, message({ id: 2, state: "pending" })]), 202);
      },
    });
    renderRoute(<AssistantPanel open onClose={() => undefined} />);
    await userEvent.click(await screen.findByRole("button", { name: "Skip my next session" }));
    expect(sent).toBe("Skip my next session");
    expect(await screen.findByText("Skip my next session", { selector: "p" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("applies a suggestion only after Confirm", async () => {
    let confirmed = false;
    mockFetch({
      "GET /api/v1/assistant/conversation": () => json(conversation([question, proposal])),
      "POST /api/v1/assistant/messages/2/confirm": () => {
        confirmed = true;
        return json({ ...proposal, proposal: "applied" });
      },
    });
    renderRoute(<AssistantPanel open onClose={() => undefined} />);
    const changes = await screen.findByRole("region", { name: "Suggested changes" });
    expect(changes).toHaveTextContent("Skip “PSY 101 · Read Ch 4”");
    expect(confirmed).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText(/Applied\. Your schedule updates/)).toBeVisible();
    expect(confirmed).toBe(true);
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
  });

  it("shows why a suggestion couldn't be applied", async () => {
    mockFetch({
      "GET /api/v1/assistant/conversation": () =>
        json(
          conversation([
            question,
            { ...proposal, proposal: "failed", proposal_note: "That session already ended." },
          ]),
        ),
    });
    renderRoute(<AssistantPanel open onClose={() => undefined} />);
    expect(
      await screen.findByText("Couldn't apply this: That session already ended."),
    ).toBeVisible();
  });

  it("sends with Enter and keeps the text when sending fails", async () => {
    mockFetch({
      "GET /api/v1/assistant/conversation": () => json(conversation([])),
      "POST /api/v1/assistant/messages": () =>
        json({ detail: "Request was throttled. Expected available in 60 seconds." }, 429),
    });
    renderRoute(<AssistantPanel open onClose={() => undefined} />);
    const box = await screen.findByLabelText("Message");
    await userEvent.type(box, "Move tonight's session{Enter}");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/throttled/));
    expect(box).toHaveValue("Move tonight's session");
  });

  it("closes and opens the page where an applied change shows", async () => {
    const closed: boolean[] = [];
    mockFetch({
      "GET /api/v1/assistant/conversation": () => json(conversation([question, proposal])),
      "POST /api/v1/assistant/messages/2/confirm": () =>
        json({
          ...proposal,
          proposal: "applied",
          link: { to: "/pulse/week?from=2026-10-14", label: "See it in your week" },
        }),
    });
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: <AssistantPanel open onClose={() => closed.push(true)} />,
        },
        { path: "/pulse/week", element: <p>Week page</p> },
      ],
      { initialEntries: ["/"] },
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("Week page")).toBeVisible();
    expect(router.state.location.search).toBe("?from=2026-10-14");
    expect(closed).toEqual([true]);
  });
});
