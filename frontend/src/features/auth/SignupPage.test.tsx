import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockFetch } from "@/test/fetchMock";
import { renderRoute } from "@/test/render";
import { SignupPage } from "./SignupPage";
import { useAuth } from "./store";

const password = () => screen.getByLabelText("Password", { selector: "input" });

describe("SignupPage", () => {
  beforeEach(() => useAuth.setState({ status: "signed-out", access: null }));

  it("validates on blur and shows the password rules as you type", async () => {
    renderRoute(<SignupPage />, "/signup");
    await userEvent.click(screen.getByLabelText("First name"));
    await userEvent.tab();
    expect(await screen.findByText("Enter your first name.")).toBeInTheDocument();

    await userEvent.type(password(), "12345");
    const rules = screen.getByRole("list", { name: "Password rules" });
    expect(rules).toHaveTextContent("At least 10 characters(not yet)");
    expect(rules).toHaveTextContent("Not only numbers(not yet)");
    await userEvent.type(password(), "abcdefgh");
    expect(rules).toHaveTextContent("At least 10 characters(done)");
    expect(rules).toHaveTextContent("Not only numbers(done)");
  });

  it("toggles password visibility", async () => {
    renderRoute(<SignupPage />, "/signup");
    expect(password()).toHaveAttribute("type", "password");
    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(password()).toHaveAttribute("type", "text");
  });

  it("shows a taken email next to the field and keeps the input", async () => {
    let answer: () => void = () => undefined;
    const fetch = mockFetch({
      "POST /api/v1/auth/signup": () =>
        new Promise<Response>((resolve) => {
          answer = () =>
            resolve(json({ email: ["An account with this email already exists."] }, 400));
        }),
    });
    renderRoute(<SignupPage />, "/signup");
    await userEvent.type(screen.getByLabelText("First name"), "Nia");
    await userEvent.type(screen.getByLabelText("Last name"), "Okoro");
    await userEvent.type(screen.getByLabelText("Email"), "MAYA@pulse.test");
    await userEvent.type(password(), "maple-river-lantern");
    await userEvent.type(
      screen.getByLabelText("Confirm password", { selector: "input" }),
      "maple-river-lantern",
    );
    await userEvent.dblClick(screen.getByRole("button", { name: "Create account" }));
    answer();
    expect(
      await screen.findByText("An account with this email already exists."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("MAYA@pulse.test");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("signs a teacher up into their dashboard", async () => {
    let sent: Record<string, unknown> = {};
    mockFetch({
      "POST /api/v1/auth/signup": async (request) => {
        sent = (await request.json()) as Record<string, unknown>;
        return json({ access: "token" }, 201);
      },
      "GET /api/v1/me": () =>
        json({
          id: 9,
          email: "ada@school.edu",
          first_name: "Ada",
          last_name: "Okafor",
          role: "instructor",
          timezone: "America/New_York",
          profile: null,
          server_now: new Date().toISOString(),
          demo_mode: false,
        }),
    });
    renderRoute(<SignupPage />, "/signup", [{ path: "/teach", element: <p>teach page</p> }]);
    await userEvent.click(screen.getByRole("radio", { name: "I teach a course" }));
    expect(screen.getByText(/Use the email your department registered/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("First name"), "Ada");
    await userEvent.type(screen.getByLabelText("Last name"), "Okafor");
    await userEvent.type(screen.getByLabelText("School email"), "ada@school.edu");
    await userEvent.type(password(), "maple-river-lantern");
    await userEvent.type(
      screen.getByLabelText("Confirm password", { selector: "input" }),
      "maple-river-lantern",
    );
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("teach page")).toBeInTheDocument();
    expect(sent).toMatchObject({ role: "teacher", email: "ada@school.edu" });
  });
});
