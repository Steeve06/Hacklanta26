import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, errorMessage } from "@/api/client";
import { MascotStill } from "@/components/mascot/MascotStill";
import { Button, Input, TopProgress } from "@/components/ui";
import { useDelayed } from "@/lib/useDelayed";
import { useLogin } from "./hooks";
import { useAuth } from "./store";

const DEMO_ACCOUNTS = [
  { email: "maya@pulse.test", note: "On track" },
  { email: "jordan@pulse.test", note: "Badly behind" },
  { email: "riley@pulse.test", note: "Brand new" },
  { email: "prof.okafor@pulse.test", note: "Instructor, CS 201" },
];

function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/";
  return raw;
}

export function LoginPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const navigate = useNavigate();
  const status = useAuth((s) => s.status);
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState({ email: false, password: false });
  const slow = useDelayed(login.isPending, 3000);

  if (status === "signed-in" && !login.isSuccess) return <Navigate to={next} replace />;

  const emailError =
    touched.email && !/^\S+@\S+\.\S+$/.test(email) ? "Enter a valid email address." : undefined;
  const passwordError =
    touched.password && password.length === 0 ? "Enter your password." : undefined;
  const invalid = !/^\S+@\S+\.\S+$/.test(email) || password.length === 0;
  const serverError =
    login.error instanceof ApiError || login.error ? errorMessage(login.error) : undefined;

  function submit(event: FormEvent) {
    event.preventDefault();
    setTouched({ email: true, password: true });
    if (invalid) return;
    login.mutate(
      { email, password, remember: false },
      { onSuccess: () => navigate(next, { replace: true }) },
    );
  }

  return (
    <div className="min-h-dvh bg-paper">
      <TopProgress active={login.isPending || login.isSuccess} />
      <main className="mx-auto grid min-h-dvh max-w-5xl items-center gap-10 px-4 py-10 md:grid-cols-[1fr_minmax(0,26rem)] md:px-8">
        <div className="flex flex-col gap-4">
          <MascotStill mood="good" size={96} />
          <h1 className="text-3xl font-extrabold">Pulse</h1>
          <p className="max-w-md text-lg text-ink-soft">
            Your courses, your deadlines and one very invested study buddy who will notice if you
            skip.
          </p>
        </div>
        <section
          aria-labelledby="signin-title"
          className="rounded-lg border border-line bg-surface p-5 md:p-6"
        >
          <h2 id="signin-title" className="mb-4 text-xl font-bold">
            Sign in
          </h2>
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
            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              disabled={login.isPending}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, password: true }))}
              error={passwordError}
            />
            {serverError && (
              <p role="alert" className="text-sm font-bold text-berry">
                {serverError}
              </p>
            )}
            <Button
              type="submit"
              pending={login.isPending}
              pendingLabel="Signing in…"
              disabled={invalid && touched.email && touched.password}
            >
              Sign in
            </Button>
            <p aria-live="polite" className="min-h-5 text-sm text-ink-soft">
              {slow ? "Waking up the server…" : ""}
            </p>
          </form>
          {import.meta.env.VITE_DEMO_MODE === "true" && (
            <details className="mt-2 border-t border-line pt-3 text-sm">
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
        </section>
      </main>
    </div>
  );
}
