import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderRoute } from "@/test/render";
import { LoginPage } from "./LoginPage";
import { useAuth } from "./store";

describe("LoginPage", () => {
  beforeEach(() => useAuth.setState({ status: "signed-out", access: null }));

  it("validates fields on blur and keeps typed input", async () => {
    renderRoute(<LoginPage />, "/login");
    const email = screen.getByLabelText("Email");
    await userEvent.type(email, "not-an-email");
    await userEvent.tab();
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(email).toHaveValue("not-an-email");
  });

  it("locks inputs and shows Signing in while the request is pending", async () => {
    globalThis.fetch = () => new Promise<Response>(() => undefined);
    renderRoute(<LoginPage />, "/login");
    await userEvent.type(screen.getByLabelText("Email"), "maya@pulse.test");
    await userEvent.type(screen.getByLabelText("Password"), "pulse-demo");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("button", { name: "Signing in…" })).toBeDisabled();
    expect(screen.getByLabelText("Email")).toBeDisabled();
  });
});
