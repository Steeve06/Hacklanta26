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
| riley@pulse.test | New student, sees onboarding |
| prof.okafor@pulse.test | Instructor, CS 201 |
| dr.marsh@pulse.test | Instructor, PSY 101 |
| prof.reyes@pulse.test | Instructor, BUS 210 |
| admin@pulse.test | Demo controls and Django admin |

The seeded term is 15 weeks and starts 4 weeks before today (set `TERM_START_DATE` to fix it). [DEMO.md](DEMO.md) is a step-by-step demo script.

## Tests

```sh
# backend (from backend/, virtualenv active)
pytest                                   # 162 tests, about 30 s
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
