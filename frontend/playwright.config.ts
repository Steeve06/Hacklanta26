import { defineConfig, devices } from "@playwright/test";

// The E2E run starts its own backend on :8001 (fresh SQLite file, re-seeded, no Redis, AI off)
// and a Vite server on :5174 that proxies to it, so it never touches your dev database.
const python = process.env.PYTHON ?? "python";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5174",
    trace: "retain-on-failure",
    launchOptions: process.env.PW_CHROMIUM_PATH
      ? { executablePath: process.env.PW_CHROMIUM_PATH }
      : undefined,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // A fresh database every run, so old migrations or leftover data never get in the way.
      command: `${python} -c "import pathlib; pathlib.Path('e2e.sqlite3').unlink(missing_ok=True)" && ${python} manage.py migrate --noinput && ${python} manage.py seed_demo && ${python} manage.py runserver 127.0.0.1:8001 --noreload`,
      cwd: "../backend",
      url: "http://127.0.0.1:8001/api/health",
      timeout: 180_000,
      reuseExistingServer: false,
      env: {
        DJANGO_SETTINGS_MODULE: "config.settings.dev",
        DATABASE_URL: "sqlite:///e2e.sqlite3",
        REDIS_URL: "",
        AI_PROVIDER: "",
        AI_API_KEY: "",
        DEMO_MODE: "true",
        CORS_ALLOWED_ORIGINS: "http://localhost:5174",
        THROTTLE_AUTH: "1000/min",
        STUDY_CHECK_SECONDS_PER_CARD: "0",
      },
    },
    {
      command: "npx vite --port 5174 --strictPort",
      url: "http://localhost:5174",
      timeout: 60_000,
      reuseExistingServer: false,
      env: { VITE_PROXY_TARGET: "http://127.0.0.1:8001", VITE_DEMO_MODE: "true" },
    },
  ],
});
