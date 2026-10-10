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
});
