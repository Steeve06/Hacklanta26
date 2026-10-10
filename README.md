# Pulse and Learning Hub

Pulse is a study planner for students. It reads courses, chapters and deadlines from Learning Hub, a small LMS in the same app, and builds a personal study schedule around the student's free time. It sends reminders with an opinionated mascot, shows how the student is doing (good, medium or bad), and keeps a streak of short chapter quizzes that open on the day the schedule assigns each chapter.

- Backend: Python 3.12, Django 5.1, Django REST Framework, Celery and Redis, PostgreSQL (SQLite for quick local runs).
- Frontend: React 18, TypeScript, Vite, TanStack Query, Tailwind, Framer Motion and Lottie.
- AI: Anthropic or OpenAI through `backend/ai/client.py`. Every AI step has a deterministic fallback, so the app runs fully without an API key.

Learning Hub lives under `/lms`, Pulse under `/pulse`. Both share one login.

## Run it with Docker (recommended)

Needs Docker Desktop (or Docker Engine with Compose v2) and `make`.

```sh
make setup   # creates .env from .env.example and fills in a secret key and Web Push keys
make up      # Postgres, Redis, Django, Celery worker, Celery Beat and Vite
```

In a second terminal, once the containers are up:

```sh
make demo    # migrates, loads the demo term and prints the demo accounts
```

Open http://localhost:5173. API docs are at http://localhost:8000/api/docs and Django admin at http://localhost:8000/admin.

On Windows without `make`, run the same commands by hand in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose run --rm --no-deps -v "${PWD}/.env:/tmp/pulse.env" web python manage.py init_env /tmp/pulse.env
docker compose up --build
# second terminal
docker compose exec web python manage.py seed_demo
```

`make demo` resets all demo data, so you can run it before every demo.

## Run it without Docker

Needs Python 3.12+ and Node 22. With no `DATABASE_URL` the backend uses SQLite, and with no `REDIS_URL` background jobs run inline, so you only need two processes.

macOS / Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
sh scripts/demo.sh                      # creates .env, migrates, seeds
cd backend && python manage.py runserver
```

Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
Copy-Item .env.example .env
cd backend
python manage.py init_env ..\.env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Then, in a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Without a worker, the 10-minute periodic jobs (reminder scan, quiz-window sweep, nightly roll-forward) don't run on their own. Use the buttons on the Demo controls page, or run `python manage.py run_periodic`.

To run the full stack natively, start Postgres and Redis, set `DATABASE_URL` and `REDIS_URL` in `.env`, and add two more processes from `backend/`:

```sh
celery -A config worker --loglevel=info    # Windows: add --pool=solo
celery -A config beat --loglevel=info
```

## Demo accounts

All passwords are `pulse-demo`.

| Account | Who |
| --- | --- |
| maya@pulse.test | Student, on track, 6-quiz streak and a quiz open now |
| sam@pulse.test | Student, slightly behind |
| jordan@pulse.test | Student, badly behind, not enough study time |
| alex@pulse.test | Student with an extension in CS 201, Central time |
| riley@pulse.test | New student, hasn't started onboarding |
| casey@pulse.test | Halfway through onboarding, resumes at step 3 |
| prof.okafor@pulse.test | Instructor, CS 201 |
| dr.marsh@pulse.test | Instructor, PSY 101 |
| prof.reyes@pulse.test | Instructor, BUS 210 |
| admin@pulse.test | Demo controls and Django admin |

The seeded term is 15 weeks and starts 4 weeks before today (set `TERM_START_DATE` to fix it). [DEMO.md](DEMO.md) is a step-by-step demo script.

## Accounts, sign-in and onboarding

- **Sign up** at `/signup` (students only). New students are enrolled in the term's three courses; work that closed before they joined is excused. Instructors and admins come from `seed_demo` or Django admin.
- **Passwords** need 10+ characters, can't be common, only numbers, or close to your name or email. They're hashed with Argon2.
- **Forgot password** emails a link that works once for an hour. Locally, emails print to the backend log: `docker compose logs web` (or the `runserver` terminal). Copy the `/reset-password?...` link into the browser.
- **Remember me** keeps you signed in for 30 days instead of 7. Signing out, or changing or resetting a password, ends the session in every tab (and, for password changes, on other devices).
- **Weekly study hours** are the student's choice (2 to 40, default 10). Pulse never plans more than that in a week; if the work doesn't fit, the overload report names whichever is full: the weekly limit, the daily maximum, or the free time marked.
- **Onboarding** is five steps (courses, study time, preferences, reminders, your schedule), saved each time you press Next. Close the tab or sign out and you pick up at the same step. Pulse pages stay locked until you press **Looks good** on step 5. Everything can be changed later in Settings.
- Ten wrong passwords for one email lock it for 15 minutes; sign-in, sign-up and reset are limited to 5 a minute per IP and per email.

## Updating an existing install

New Python packages and migrations come with updates. With Docker:

```sh
docker compose up --build                                   # rebuilds images, runs migrations on start
docker compose exec web python manage.py seed_demo          # optional: reset the demo data
```

Without Docker (virtualenv active): `pip install -r backend/requirements-dev.txt`, then from `backend/` run `python manage.py migrate` and, optionally, `python manage.py seed_demo`. Re-seeding replaces the demo accounts and courses; accounts you created with sign-up are kept and re-enrolled in the new courses. `docker compose down` keeps the database; only `docker compose down -v` deletes it.

## Manual test steps

1. **Sign up:** open `/signup`, create an account, and check that the password rules tick as you type and a taken email shows an error next to the field.
2. **Onboarding:** go through all five steps. Reload on step 3 and you stay on step 3 with your earlier answers. On step 5, check that **Your choices** shows the hours you marked and your limits, and that the advice under the plan names the limit that's actually full (weekly, daily, or free time). Check the week's plan and the first quiz window, then press **Looks good** to land on Today.
3. **Resume:** sign in as `casey@pulse.test` and you land on step 3. Sign in as `riley@pulse.test` and you land on step 1. Sign in as `maya@pulse.test` and you go straight to Today.
4. **Redirects:** while signed in, open `/login` and you're sent home. As `prof.okafor@pulse.test`, open `/onboarding` and you're sent to Learning Hub.
5. **Password reset:** on the sign-in page, choose **Forgot password?**, then copy the link from the backend log, set a new password, and sign in with it. The same link fails a second time.
6. **Persistence check:** sign up and finish onboarding, then run `docker compose down` and `docker compose up`. Sign in again: your study time, preferences, reminder style and schedule are all still there.
7. **Two tabs:** sign in, open a second tab, and sign out in the first. The second tab's next action sends it to the sign-in page.

## Tests

```sh
# backend (from backend/, virtualenv active)
pytest                                   # 227 tests, about 20 s
pytest --cov --cov-report=term-missing   # coverage, 93% overall

# frontend (from frontend/)
npm run lint && npm run typecheck && npm test

# end to end (from frontend/): starts its own Django on :8001 and Vite on :5174
npx playwright install chromium          # once
npx playwright test
```

The E2E run uses `python` from your PATH; set `PYTHON=/path/to/.venv/bin/python` if that isn't the virtualenv. CI (`.github/workflows/ci.yml`) runs lint, type checks, unit tests on Postgres, and the E2E flows. It never deploys.

After changing an API serializer or view, regenerate the TypeScript types with `make api-types`.

## Environment variables

Every variable is documented in [.env.example](.env.example). The ones you're most likely to change:

| Variable | Default | What it does |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | placeholder | Signing key. `init_env` fills it in. |
| `DATABASE_URL` | SQLite file | Postgres URL in Docker and production. |
| `REDIS_URL` | empty | Celery broker and cache. Empty runs jobs inline. |
| `AI_PROVIDER`, `AI_API_KEY` | `anthropic`, empty | Empty key = deterministic fallbacks only. |
| `AI_MODEL_PLANNER`, `AI_MODEL_LIGHT` | Sonnet / Haiku | Models for decomposition and quiz questions / titles and copy. |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | empty | Web Push keys. `init_env` fills them in. |
| `EMAIL_*` | console backend | Email fallback for urgent reminders. |
| `USE_CELERY_BEAT` | `true` | `false` when periodic jobs run from cron instead. |
| `CRON_TOKEN` | empty | Enables `POST /api/cron` for an external scheduler. |
| `SOLVER` | `greedy` | `cpsat` uses OR-Tools if installed. |
| `TERM_START_DATE` | 4 weeks ago | First day of the seeded term. |
| `DEMO_MODE`, `VITE_DEMO_MODE` | `false` | Demo controls and time-travel; demo logins on the sign-in page. |
| `FRONTEND_URL` | `http://localhost:5173` | Base of the links in password-reset and reminder emails. |
| `THROTTLE_AUTH` | `5/min` | Sign-in, sign-up and reset requests per IP and per email. |

## Repository layout

```
backend/
  config/         settings (base, dev, test, prod), urls, celery, periodic jobs
  accounts/       users, profiles, JWT auth, server clock
  lms/            Learning Hub: courses, chapters, assessments, submissions
  pulse/          availability, planner and solver, sessions, status, demo controls
  notifications/  templates, triggers, delivery (in-app, push, email), guardrails
  quizzes/        question banks, quiz windows, attempts, streaks
  ai/             provider client, prompts, schemas, cost log
  seed/           seed_demo command and course content
frontend/
  src/app/        router, shell, providers
  src/features/   auth, lms, pulse, quiz, notifications, demo
  src/components/ shared UI, mascot
  src/api/        client and generated OpenAPI types
  e2e/            Playwright flows
```

## More

- [DECISIONS.md](DECISIONS.md): choices made where the brief left room.
- [DEPLOY.md](DEPLOY.md): how to deploy the backend to Render and the frontend to Vercel.
- [CREDITS.md](CREDITS.md): fonts, content and asset sources.
- [GIT.md](GIT.md): commit history and pushing the repo to GitHub.
