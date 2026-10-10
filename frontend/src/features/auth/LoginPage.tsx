import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { errorMessage, isUnreachable } from "@/api/client";
import { Button, Input } from "@/components/ui";
import { useDelayed } from "@/lib/useDelayed";
import { AuthLayout } from "./AuthLayout";
import { useLogin } from "./hooks";
import { PasswordInput } from "./PasswordInput";
import { destinationAfterLogin } from "./redirects";

const EMAIL = /^\S+@\S+\.\S+$/;

const DEMO_ACCOUNTS = [
  { email: "maya@pulse.test", note: "On track" },
  { email: "jordan@pulse.test", note: "Badly behind" },
  { email: "casey@pulse.test", note: "Halfway through onboarding" },
  { email: "riley@pulse.test", note: "Hasn't started onboarding" },
  { email: "prof.okafor@pulse.test", note: "Instructor, CS 201" },
  { email: "admin@pulse.test", note: "Admin" },
];

export function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [touched, setTouched] = useState({ email: false, password: false });
  const slow = useDelayed(login.isPending, 3000);

  const emailError =
    touched.email && !EMAIL.test(email.trim()) ? "Enter a valid email address." : undefined;
  const passwordError = touched.password && !password ? "Enter your password." : undefined;
  const invalid = !EMAIL.test(email.trim()) || !password;
  const offline = login.isError && isUnreachable(login.error);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    setTouched({ email: true, password: true });
    if (invalid || login.isPending) return;
    login.mutate(
      { email: email.trim(), password, remember },
      {
        onSuccess: (me) =>
          navigate(destinationAfterLogin(me, params.get("next")), { replace: true }),
      },
    );
  }

  return (
    <AuthLayout title="Sign in" busy={login.isPending || login.isSuccess}>
      <form noValidate onSubmit={submit} className="flex flex-col gap-4">
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          disabled={login.isPending}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, email: true }))}
          error={emailError}
        />
        <PasswordInput
          label="Password"
          autoComplete="current-password"
          value={password}
          disabled={login.isPending}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, password: true }))}
          error={passwordError}
        />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={remember}
              disabled={login.isPending}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-5 w-5"
            />
            Keep me signed in for 30 days
          </label>
          <Link to="/forgot-password" className="text-sm font-bold text-pine underline">
            Forgot password?
          </Link>
        </div>
        {login.isError && !offline && (
          <p role="alert" className="text-sm font-bold text-berry">
            {errorMessage(login.error)}
          </p>
        )}
        {offline && (
          <div
            role="alert"
            className="flex flex-col items-start gap-2 rounded-md border border-berry/40 bg-berry-soft p-3"
          >
            <p className="text-sm font-bold">Can't reach the server. It may still be starting.</p>
            <Button size="sm" variant="secondary" onClick={() => submit()}>
              Retry
            </Button>
          </div>
        )}
        <Button type="submit" pending={login.isPending} pendingLabel="Signing in…">
          Sign in
        </Button>
        <p aria-live="polite" className="min-h-5 text-sm text-ink-soft">
          {slow ? "Waking up the server…" : ""}
        </p>
      </form>
      <p className="border-t border-line pt-4 text-sm">
        New here?{" "}
        <Link to="/signup" className="font-bold text-pine underline">
          Create an account
        </Link>
      </p>
      {import.meta.env.VITE_DEMO_MODE === "true" && (
        <details className="mt-2 text-sm">
          <summary className="min-h-11 cursor-pointer py-2 font-bold text-ink-soft">
            Demo accounts
          </summary>
          <p className="mb-2 text-ink-soft">
            Password for all: <code className="rounded-sm bg-sunken px-1">pulse-demo</code>
          </p>
          <ul className="flex flex-col">
            {DEMO_ACCOUNTS.map((account) => (
              <li key={account.email}>
                <button
                  type="button"
                  className="flex min-h-11 w-full items-center justify-between gap-3 rounded-sm px-2 text-left hover:bg-sunken"
                  onClick={() => {
                    setEmail(account.email);
                    setPassword("pulse-demo");
                  }}
                >
                  <span className="font-bold">{account.email}</span>
                  <span className="text-ink-soft">{account.note}</span>
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </AuthLayout>
  );
}
