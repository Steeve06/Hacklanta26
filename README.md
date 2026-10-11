# Leon and Learning Hub

Leon is a study planner for students. It reads courses, chapters and deadlines from Learning Hub, a small LMS in the same app, and builds a personal study schedule around the student's free time. It plans around each course's fixed class times, sends reminders in the voice of Leon, an opinionated chameleon, shows how the student is doing (good, medium or bad), and keeps a streak of study checks: after the schedule gives a student a chapter, a 3-minute check of four cards on it (options, a short answer and a matching card) opens for that day and the next, three right answers keep the streak going, and every check earns XP for a weekly leaderboard among classmates. Students can also ask Leon, a chat panel on every page, to change their schedule in plain words.

- Backend: Python 3.12, Django 5.1, Django REST Framework, Celery and Redis, PostgreSQL (SQLite for quick local runs).
- Frontend: React 18, TypeScript, Vite, TanStack Query, Tailwind, Framer Motion and Lottie.
- AI: Anthropic or OpenAI through `backend/ai/client.py`. Every AI step has a deterministic fallback, so the app runs fully without an API key.

Learning Hub lives under `/lms`, Leon under `/pulse`. Both share one login.

## Run it with Docker (recommended)

Needs Docker Desktop (or Docker Engine with Compose v2) and `make`.

```sh
make setup   # creates .env from .env.example and fills in a secret key and Web Push keys
make up      # Postgres, Redis, Django, Celery worker, Celery Beat and Vite
```

In a second terminal, once the containers are up:

```sh
make demo         # migrates, registers the term's empty courses and prints the accounts
make demo-sample  # the same, with sample chapters, assignments and student history
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

`make demo` resets all demo data, so you can run it before every demo. It leaves the three courses empty, waiting for their teachers to sign up and add content (see [Teachers](#teachers)). `make demo-sample` (or `seed_demo --sample-content`) fills them with the sample term instead, which is what [DEMO.md](DEMO.md) walks through.

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

Without a worker, the 10-minute periodic jobs (reminder scan, streak sweep, nightly roll-forward) don't run on their own. Use the buttons on the Demo controls page, or run `python manage.py run_periodic`.

To run the full stack natively, start Postgres and Redis, set `DATABASE_URL` and `REDIS_URL` in `.env`, and add two more processes from `backend/`:

```sh
celery -A config worker --loglevel=info    # Windows: add --pool=solo
celery -A config beat --loglevel=info
```

## Demo accounts

All passwords are `pulse-demo`. The student descriptions apply to `--sample-content`; with plain `seed_demo` the courses are empty, the instructor accounts don't exist until the teachers sign up (choose "I teach a course" with the email below and any password) (until then, signing in as one explains that).

| Account | Who |
| --- | --- |
| maya@pulse.test | Student, on track, 6-check streak with a study check open now, top of this week's leaderboard |
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

- **Sign up** at `/signup`. Students choose "I'm a student" and are enrolled in the term's courses; work that closed before they joined is excused. Teachers choose "I teach a course" and must use the email their course was registered with (see [Teachers](#teachers)). Admins come from `seed_demo` or `createsuperuser`.
- **Passwords** need 10+ characters, can't be common, only numbers, or close to your name or email. They're hashed with Argon2.
- **Forgot password** emails a link that works once for an hour. Locally, emails print to the backend log: `docker compose logs web` (or the `runserver` terminal). Copy the `/reset-password?...` link into the browser.
- **Remember me** keeps you signed in for 30 days instead of 7. Signing out, or changing or resetting a password, ends the session in every tab (and, for password changes, on other devices).
- **Weekly study hours** are the student's choice (2 to 40, default 10). Leon never plans more than that in a week; if the work doesn't fit, the overload report names whichever is full: the weekly limit, the daily maximum, or the free time marked.
- **Onboarding** is five steps (courses, study time, preferences, reminders, your schedule), saved each time you press Next. Close the tab or sign out and you pick up at the same step. Leon pages stay locked until you press **Looks good** on step 5. Everything can be changed later in Settings.
- **Navigation:** Today, Week (study plan, course calendar and a link to the term overview), Study checks, Leaderboard, Courses and Settings. Study checks are the short checks after scheduled chapters; course quizzes stay in Learning Hub. On a phone, Settings is the gear in the top bar.
- **Class times** are fixed per course (in `CAMPUS_TIMEZONE`, New York by default), listed on course cards and the syllabus, shown on the course calendar, and never used for study sessions. Change them in Django admin under Courses.
- **Ask Leon** (the chat button in the sidebar, or the speech bubble at the top on a phone) takes requests like "skip tonight's session", "I'm working Friday evening" or "keep Sundays free". It answers with the change it would make, and nothing happens until the student presses **Confirm**. Each change is checked against the student's own schedule, hours and deadlines both when it's suggested and when it's confirmed.
- Ten wrong passwords for one email lock it for 15 minutes; sign-in, sign-up and reset are limited to 5 a minute per IP and per email.

## Teachers

Course content comes from teachers, not from fixed files.

1. **An admin registers the course**: code, title, class times and the teacher's email. Use **Register courses** in the app (admin account), or `python manage.py register_course "ENG 105" "Academic Writing" kim@school.edu --teacher-name "Kim Lee" --meeting "tue 09:00-10:15 Hall 2"`. `seed_demo` registers CS 201, PSY 101 and BUS 210 for `prof.okafor@`, `dr.marsh@` and `prof.reyes@pulse.test`. Every student in the term is enrolled.
2. **The teacher signs up** at `/signup` with "I teach a course" and that email. The account was waiting without a password; signing up claims it, and the teacher lands on the **Dashboard** with the course already there. Signing in before signing up says to sign up first.
3. **The teacher adds content** from the dashboard: chapters (Markdown), assignments, discussions and quizzes (multiple choice or true/false), plus the syllabus description, office hours and grading weights. Content can be hidden until it's ready.
4. **Students see it in Learning Hub as before**, it is planned into their schedule, and chapters feed their study checks and daily cards. Each new item also reaches them as an inbox notification and, on devices with push turned on, a push notification (sent when the item opens, outside quiet hours).

## Updating an existing install

New Python packages and migrations come with updates. With Docker:

```sh
docker compose up --build                                   # rebuilds images, runs migrations on start
docker compose exec web python manage.py seed_demo          # optional: reset the demo data (add --sample-content for the filled term)
```

Without Docker (virtualenv active): `pip install -r backend/requirements-dev.txt`, then from `backend/` run `python manage.py migrate` and, optionally, `python manage.py seed_demo`. Re-seeding replaces the demo accounts and courses; accounts you created with sign-up are kept and re-enrolled in the new courses. `docker compose down` keeps the database; only `docker compose down -v` deletes it.

## Manual test steps

1. **Sign up:** open `/signup`, create an account, and check that the password rules tick as you type and a taken email shows an error next to the field.
2. **Onboarding:** go through all five steps. Reload on step 3 and you stay on step 3 with your earlier answers. On step 5, check that **Your choices** shows the hours you marked and your limits, and that the advice under the plan names the limit that's actually full (weekly, daily, or free time). Check the week's plan and the study checks note, then press **Looks good** to land on Today.
3. **Resume:** sign in as `casey@pulse.test` and you land on step 3. Sign in as `riley@pulse.test` and you land on step 1. Sign in as `maya@pulse.test` and you go straight to Today.
4. **Redirects:** while signed in, open `/login` and you're sent home. As `prof.okafor@pulse.test`, open `/onboarding` and you're sent to Learning Hub.
5. **Password reset:** on the sign-in page, choose **Forgot password?**, then copy the link from the backend log, set a new password, and sign in with it. The same link fails a second time.
6. **Persistence check:** sign up and finish onboarding, then run `docker compose down` and `docker compose up`. Sign in again: your study time, preferences, reminder style and schedule are all still there.
7. **Ask Leon:** as `alex@pulse.test`, open **Ask Leon** and send "Skip my next session". The reply lists the change; the session is still planned until you press **Confirm**, then it shows as skipped in Week.
8. **Two tabs:** sign in, open a second tab, and sign out in the first. The second tab's next action sends it to the sign-in page.

## Tests

```sh
# backend (from backend/, virtualenv active)
pytest                                   # 297 tests, about 25 s
pytest --cov --cov-report=term-missing   # coverage, 93% overall

# frontend (from frontend/)
npm run lint && npm run typecheck && npm test

# end to end (from frontend/): starts its own Django on :8001 and Vite on :5174
npx playwright install chromium          # once
npx playwright test
```

The E2E run uses `python` from your PATH; set `PYTHON=/path/to/.venv/bin/python` if that isn't the virtualenv. CI (`.github/workflows/ci.yml`) runs lint, type checks, unit tests on Postgres, and the E2E flows. It never deploys.

After changing an API serializer or view, regenerate the TypeScript types with `make api-types`.

## Use Leon on your phone

Leon is a Progressive Web App: it installs to a phone's home screen, opens full screen like any app, shows push notifications for reminders, and still opens (with a "can't reach the server" page) when there's no connection. Phones only allow installing and push over HTTPS, so give your laptop's Leon a temporary HTTPS address:

```sh
docker compose up -d                                   # Leon as usual
docker compose --profile phone up -d --build phone     # the built app on http://localhost:4173
cloudflared tunnel --url http://localhost:4173         # prints https://<random-words>.trycloudflare.com
```

Open the printed address on the phone. The phone service serves the built app, a handful of files, because the development server's hundreds of small files often leave a phone on a blank page over a tunnel. It rebuilds from your current code each time it starts (`docker compose --profile phone restart phone` after changes). Install `cloudflared` with `winget install --id Cloudflare.cloudflared` on Windows or `brew install cloudflared` on macOS; `docker compose --profile phone up tunnel` runs it in a container instead.

The address changes every time you start the tunnel, and an app installed from an old address won't open, so install again from the new one. If the tunnel fails with "certificate signed by unknown authority", the network is inspecting HTTPS (common on school and office Wi-Fi): connect the laptop to a phone hotspot and run it again.

- **iPhone and iPad (iOS 16.4 or later):** in Safari, Share > **Add to Home Screen**. Open Leon from the Home Screen, sign in (the Home Screen app has its own sign-in), then Settings > **Turn on push** > **Send a test notification**. Apple only allows web push for apps added to the Home Screen.
- **Android (Chrome):** Settings > **Leon on this device** > **Install Leon** (or the browser menu's Install app), then turn on push and send a test.
- **Desktop Chrome or Edge:** `http://localhost:5173` counts as secure, so install and push work there without a tunnel.

Push needs VAPID keys in `.env` (`init_env` creates them). If notifications don't arrive: check the notification permission for Leon, make sure the phone isn't in Do Not Disturb or a focus mode, and use **Send a test notification**. Reminders wait up to 12 hours for a phone that's asleep or offline; code-red and missed-deadline reminders are sent as high priority.

A deployed Leon (see [DEPLOY.md](DEPLOY.md)) is already on HTTPS, so phones can install it straight from its address.

## Turning on the AI

Without a key, Leon runs on built-in rules: the schedule is planned from heuristics, study-check cards come from each chapter's key terms, and Ask Leon recognises common requests by keyword. With a key, the model:

- estimates each piece of work and splits it into study tasks in a sensible order (the solver still places them, so hours and deadlines are always respected),
- writes session titles, the plan summary, and reads notes like "mornings are best",
- writes the four study-check questions from the chapter text (each one checked against a quote from the chapter),
- answers in Ask Leon and proposes changes.

To turn it on, put your own key in `.env` (never commit it):

```sh
AI_PROVIDER=anthropic        # or openai
AI_API_KEY=your-key-here
```

Then run `docker compose up -d`. It recreates the containers that use `.env`; `docker compose restart` would keep the old settings. `GET /api/health` shows `"ai": "configured (anthropic)"` (or openai) when it's picked up. Every call, its tokens and cost are logged in Django admin under **AI call logs**. If the provider fails five times in a row, Leon switches to the built-in rules for 10 minutes.

## Environment variables

Every variable is documented in [.env.example](.env.example). The ones you're most likely to change:

| Variable | Default | What it does |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | placeholder | Signing key. `init_env` fills it in. |
| `DATABASE_URL` | SQLite file | Postgres URL in Docker and production. |
| `REDIS_URL` | empty | Celery broker and cache. Empty runs jobs inline. |
| `AI_PROVIDER`, `AI_API_KEY` | `anthropic`, empty | Empty key = deterministic fallbacks only. |
| `AI_MODEL_PLANNER`, `AI_MODEL_LIGHT` | Sonnet / Haiku | Models for decomposition / titles and copy. |
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
  quizzes/        study checks, question banks, streaks, weekly XP leaderboard
  assistant/      the Ask Leon chat: replies, proposed changes, keyword fallback
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
