# Decisions

Choices made where the build prompt left room, with the reason for each.

## Foundation

- **Python 3.12 in Docker, 3.12+ locally.** The Dockerfile pins 3.12. The code also runs on 3.13, which is what the build machine had.
- **Refresh token in an httpOnly cookie scoped to `/api/v1/auth/`.** The access token lives only in memory. On page load the app calls `/auth/refresh` to get a new access token, so a reload keeps you signed in without storing anything in localStorage.
- **No Redis means inline jobs.** When `REDIS_URL` is empty, Celery runs tasks eagerly and Django uses an in-memory cache. This keeps "run without Docker" to two processes (Django and Vite). The UI still polls the job endpoint, so behaviour is the same.
- **One clock for the whole server.** `accounts.clock.now(user)` is the only source of "now" in scheduling, notifications, status and quizzes. Demo time-travel adds a per-student offset there and nowhere else, and only when `DEMO_MODE=true`.
- **Typed client with `openapi-fetch`.** Types come from `openapi-typescript`; `openapi-fetch` uses them directly, so there is no generated runtime code and no hand-written API types.
- **Vite 8 / TypeScript 5.9.** TypeScript 7 is out but `typescript-eslint` does not support it yet.

## Learning Hub

- **Original seed content.** All 24 chapters (8 per course, 650–900 words each) were written for this project rather than copied from OpenStax, so there is nothing to attribute; CREDITS.md lists only fonts and libraries.
- **Reading time is study time.** Seeded `reading_minutes` assumes careful study reading at about 70 words per minute, not skimming speed, so a chapter is a realistic 10–13 minute study block.
- **"Late" means submitted late.** An unsubmitted item past its due date but inside its late window keeps `not_started`/`in_progress` and the API adds `overdue: true`. Once the cut-off passes it becomes `missed`.
- **Excused is a submission row.** Excusing a student creates a `Submission` with status `excused`; removing the excusal deletes it. This keeps one place to look for per-student state.
- **Quiz best score counts.** Each instructor-quiz attempt that beats the previous best writes a new `Submission`; the latest graded row is the best one.
- **Files are served through an authenticated endpoint**, never from a public media URL, so only the student and the course instructor can download a submission.
- **Brand-new demo student is a late add.** Riley's past-due work is excused so her status starts clean instead of showing missed work from before she enrolled.

## Scheduler

- **Whole term placed in detail.** The solver places every remaining task up to the end of term, not just the next 14 days, because a full plan for three courses takes about 0.1 s. The plan summary talks about the next two weeks; later weeks simply move on the nightly roll-forward.
- **Sessions are copied forward, not shared.** Each re-plan writes a new `Schedule` version. Sessions that already ended (or were marked done, partial, skipped or rescheduled) are copied into the new version, so the active schedule always holds the full history. The 20 most recent versions are kept.
- **Unsplittable tasks may exceed the preferred session length.** Writing a discussion post or taking a quiz happens in one sitting, so these run as long as they need, as long as they fit one availability block. If no block is long enough, the overload report flags "needs one longer block".
- **Slack and soft constraints are a first pass.** Each task is first placed with the 15% slack reserve, the two-sessions-per-course-per-day limit and the regenerate feedback; only what doesn't fit is retried without them, then without the deadline buffer (flagged "tight deadline"). Anything still left goes into the overload report.
- **Stability = pinning.** Planned sessions in the next 24 hours are kept in place when still valid. If keeping them would make something miss its deadline, the plan is rebuilt without pins and the better result wins.
- **Reschedule removes that slot only.** Rescheduling a session marks it `rescheduled` and keeps its time blocked for the re-plan, so the work lands somewhere else.
- **Regenerate feedback is parsed, then remembered.** "Less on weekends" or "mornings" becomes day weights and an hour preference, stored on the profile so nightly re-plans keep honouring it.
- **Re-plan debounce coalesces.** Automatic triggers set a 60-second "pending" flag per student; further triggers inside that window are absorbed because the queued job reads the latest data when it starts (5 seconds later with a worker, immediately without one).
- **OR-Tools is optional.** `SOLVER=cpsat` is accepted but falls back to the greedy solver (with a log line) unless `ortools` is installed; the greedy + local search meets every budget on its own.

- **Urgency flows back through dependencies.** A task that something due sooner depends on (reading a chapter before a discussion post due tonight) is ordered as if it were due then. It still only has to finish by its own deadline.
- **Replies don't wait for classmates when time is short.** The one-day gap before discussion replies is dropped when the discussion is due within 12 hours of that gap.
- **Tonight's sessions stay put unless something due within a day would be missed.** Re-planning keeps sessions in the next 24 hours where they were, but if dropping that rule covers more work due within a day, the new plan wins even if it's slightly worse overall.
- **The plan is for keeping up, not catching up.** Past-due work leaves the plan (it can still be submitted late from Learning Hub) and counts against the streak instead. The plan summary says what it left out.
- **A tight plan is a note, not an alarm.** When some work won't fully fit, Today shows one closed line (only for work due in the next 7 days) with the details and suggestions inside. It no longer forces the mascot to "bad"; work that won't fit in the next 3 days is listed as a reason. Only having no study time at all is an alert and forces "bad".
- **Overload advice names what's actually full.** If unused free time sits behind a full daily or weekly limit, the advice says to raise that limit. Free-time advice only names days before the deadline, and work due within a day gets its own line.

## AI layer

- **Structured output via a forced tool call (Anthropic) or `json_schema` (OpenAI).** Either way the result is validated with Pydantic before anything uses it.
- **Cache per work item, not per course.** Each item's decomposition is cached under a hash of its content and the prompt version, so a re-plan sends only new or changed items back to the model (one call per course that has any). Routine re-plans make zero calls.
- **Titles and summary only on explicit generates.** Polished titles are cached per task and reused; re-plans use those titles and a template summary. This keeps a first schedule at ≤ 4 calls (one per course plus one polish) and routine re-plans at 0.
- **Two kinds of retry.** A network error or schema mismatch is retried once after a short backoff inside the client; a response that parses but fails our checks (missing items, unknown or cyclic dependencies) is retried once with the problems listed. After that the course falls back to the heuristic and an `AICallLog` row records `fallback_used`.
- **Estimates are scaled, not rejected.** If an item's task minutes add up to more than 1.5× or less than 0.5× the baseline, they are scaled proportionally into that range.
- **Circuit breaker in the cache.** Five consecutive failures switch AI off for ten minutes for every worker sharing the cache.
- **Prices are approximate.** `ai/client.py` holds a small per-model price table for the daily cost total in Django admin; unknown models log a cost of 0.

## Status and animation

- **Overall score is a weighted average of course scores**, weighted by each course's remaining assignment weight (+1 so finished courses still count a little). Overall state then gets its own forced rules: any unresolved overload forces bad; a missed item worth 10% or more forces at least medium.
- **"Unresolved overload" means any item in the overload report.** If adding hours or getting an extension would fix it, the student still needs to act, so the mascot stays in the bad state until the plan fits.
- **No sessions yet = full adherence.** A student with no past sessions isn't penalised for adherence, and a student with no history at all is shown as good with the fresh-start moment.
- **One-shot moments come from the server** (`celebrate` after an on-time submission in the last 15 minutes, `gasp` when something is due within 3 hours, `fresh_start` for new students) with a stable key, and the browser remembers which keys it has already played in session storage.
- **Mascot animations are generated, not hand-exported.** `frontend/scripts/make_mascot.py` writes small Lottie files (4–19 KB). They play through lottie-react's light build, loaded lazily, and fall back to a static SVG while loading or when reduced motion is on.

## Notifications

- **One reminder per assignment per scan: the most urgent.** An essay due in 2 hours fires `code_red`, not also `final_stretch` and `upcoming_due`.
- **Supportive mode copy is its own level (0).** It's gentle, encouraging, adds the campus support link to emails, and is used whenever supportive mode is on.
- **Extensions map to a tier-1 "upcoming" reminder at sass 1** and never produce missed/late reminders. Excused items produce nothing.
- **Template choice skips any text already sent in 14 days.** Templates whose placeholders can't be filled are skipped too (a submission win never uses a streak line). If every variant has been used, the reminder is skipped rather than repeated.
- **Storm = 4 or more new reminders in one scan.** They're stored in the inbox only and one digest is pushed/emailed.
- **Caps apply within a scan as well as across the day**, so a single scan can't exceed 5 or put more than 2 (3 for tiers 4–5) on one assignment.
- **Dismissing supportive mode lasts 14 days** before the automatic "3 missed items" rule can turn it on again.
- **Snooze re-queues the same notification** an hour later; it's re-checked and re-sent like a new one.
- **Push actions from the lock screen open the app** with `?notification=…&action=…`, because the service worker has no access token; the app performs the action.
- **AI rewording of reminders is off by default** (`NOTIFICATION_AI_VARIATION=true` to enable). When on, a rewrite that fails the guardrails is dropped and the template text is sent.
- **Unsubscribe uses `DELETE /push/subscribe?endpoint=…`** because OpenAPI tooling drops bodies on DELETE.

## Study checks and streaks

- **The streak measures studying, so it follows the schedule.** When the schedule gives a student a chapter, a study check opens at the start of that day (the day of its last session if it's spread over several) and closes at the end of the next day. Completing a chapter early opens its check right away. Chapters planned for the same day share one check. This replaced the collaborator's daily general flashcards; there are no optional flashcards on the side.
- **Four cards, four kinds.** A try mixes option questions (multiple choice and true/false), one short answer (type the missing key term) and, when the chapters have enough key terms, one matching card (three terms to the sentences they complete), placed third. Option and short-answer cards flip to show right or wrong, the explanation and the chapter line it comes from; the matching card marks each pair. Three right out of four passes (`STUDY_CHECK_PASS_MARK`); a matching card counts as one. A failed first try leaves one more try with cards not shown before; after that the check is settled. Self-rated flashcards from the daily quiz aren't used here, since a check has to show the student actually knows the material.
- **Short answers forgive small slips.** Case, articles, punctuation and a trailing plural are ignored, and answers of 5+ characters within about one typo (similarity ≥ 0.85) count. This and the matching card come from the daily-quiz work on `main`.
- **Three minutes a try, enforced by the server** (`STUDY_CHECK_TIME_LIMIT`). The clock starts on Start; answers are accepted up to 10 seconds late for network delay. A try whose time ran out is finished on the next read or answer, with unanswered cards counted wrong.
- **XP and the weekly leaderboard.** 10 XP per right answer and 20 for answering every card in time. The leaderboard sums this week's XP (Monday in the viewer's time zone) among everyone who shares a course with the student, filterable by course; ties go to the longer streak, then the name. Names show as first name and last initial. There's no opt-out yet; add one in settings before using this with real students.
- **Questions are written by the model and grounded.** Each question must quote the chapter (checked as a substring after whitespace normalisation); questions with duplicate options or more than one right answer are dropped. Without AI, or if too few survive, option questions come from the chapter's bold key terms. Short-answer questions always come from the key terms (one per term, the sentence that introduces it with the term blanked) and stay when model-written questions arrive. Banks are rebuilt when a chapter's text changes; no model call happens when a student opens a check.
- **Anti-gaming:** answers are graded on the server one card at a time, the right answer is only sent after the student answers, and each card needs at least 4 seconds before its answer counts.
- **Merged with the daily timed quiz from `main`.** That version made the streak a daily habit; this one keeps the streak tied to studying the scheduled chapter, and takes its timer, question types, XP and leaderboard into study checks. Its migrations stay first (`quizzes/0005_timed_sessions`), and `0006_study_checks` then replaces the daily-deck tables, so a database at either version upgrades in order. A database that ran this branch's earlier migration names needs a fresh start (`docker compose down -v`); it only held demo data.
- **Missed deadlines count against the streak.** Coursework that passes its due date without a submission settles once per assessment, like a missed check: it spends a freeze, otherwise resets the streak. Excused work and work with an extension (which moves the due date) don't count; submitting late afterwards doesn't undo it. Misses from the last 7 days are listed under the streak with what they did and, while the late window is open, a link to submit. The sweep runs every 10 minutes and whenever the streak is shown.
- **Streak rules:** consecutive checks passed inside their windows (15 minutes of grace after the close). A missed check spends a freeze (1 earned per 5 passes, 2 max) or resets the streak. Days without a check don't count either way. Milestones at 3, 7, 14, 30, 50 and 100.

## Two calendars

- **Week has two tabs.** *Study plan* is the schedule Pulse builds. *Course calendar* is what the courses set: due dates (with any extension) and chapter release dates from Learning Hub. Learning Hub has no class meeting times, so there are none to show.

## Ask Pulse (the chat)

- **After Confirm, go to the change.** The panel closes and opens where the change shows: the week containing the session or busy time, or the study time or preferences section of Settings.
- **Suggest, then confirm.** The chat never changes anything on its own. A reply can carry a list of changes; the student presses **Confirm** or **Not now**. A newer suggestion replaces an older one that wasn't answered.
- **A fixed set of changes.** Skip, mark done, reschedule, move to a specific time, keep a one-off time free, replace one weekday's free time, change limits (weekly, daily, session length, study window), and rebuild the plan around a note. Each goes through the same services as the app's buttons, so the planner's hard constraints still hold.
- **Checked twice.** Every change is validated against the student's own data when the reply is made (invalid ones are dropped and the reply says why) and again on Confirm, inside one transaction: if any change no longer applies, none are applied and the card says why.
- **Moved sessions stay put.** A session the student moves to a specific time is marked `locked`, and re-planning keeps it there unless the plan can't fit everything with it in place.
- **The model sees only what it needs:** times in the student's zone, limits, free time, the next 10 days of sessions, deadlines in the next 3 weeks, open checks, the streak and the last 10 messages. No names, emails or grades. Messages are data, not instructions.
- **Replies run in the background** (one at a time per student, polled every 1.5 s) and are limited to 30 messages an hour (`THROTTLE_ASSISTANT`). It uses the planner model because a wrong suggestion costs more than the tokens.
- **Without AI, keywords.** "Skip", "move", "busy/working + a day", "done", "what's next" and day-or-time preferences are recognised by rules, so the chat still works with no key.

## Demo-ready (M8)

- **Demo controls are a page for the admin account**, backed by `/api/v1/demo/*`. Every endpoint returns 404 unless `DEMO_MODE=true`, and only admins can call them. "Send now even during quiet hours" also releases reminders that were already queued for the morning.
- **Time-travel only moves forward.** The offset is per student and never negative, so a demo can't create quiz windows or deadlines in the past. "Back to now" resets it.
- **Demo streaks end yesterday.** The seed gives each student finished decks up to yesterday, so today's deck is always the one that keeps the streak going, whatever the time of day.
- **Course data is cached per course.** Chapters, assignments and syllabus weeks are the same for every student, so the snapshot every scan and re-plan builds reads them from the cache, invalidated by model signals on any change. This halved the notification scan to about 10 ms per student on SQLite.
- **The scan fans out in batches of 200.** With a worker, each batch is its own task; without one they run inline. Either way each batch sends its own due reminders.
- **Periodic jobs have one entry point** (`config/periodic.py`), used by Celery Beat, `manage.py run_periodic` and `POST /api/cron` (header `X-Cron-Token`, off when `CRON_TOKEN` is empty). `USE_CELERY_BEAT=false` empties the Beat schedule so a cron job and Beat never both run.
- **Render runs a worker plus a cron job, not Beat.** The cron job does the 10-minute scans; the worker handles plan and notification-batch tasks.
- **Vercel proxies `/api` to Render**, so the refresh cookie is first-party and stays `SameSite=Lax`. `REFRESH_COOKIE_SAMESITE=None` is available if the API is called cross-site instead.
- **`.env` is read by `manage.py`, wsgi and Celery** when it exists, so running without Docker uses the same file. Real environment variables win; pytest never reads it.
- **`init_env` fills in secrets.** `make setup` (or `python manage.py init_env .env`) writes a fresh Django secret and a VAPID key pair into `.env`, so browser push works without generating keys by hand. The browser reads the public key from the API, so there is no frontend copy.
- **Production refuses a weak secret.** `config.settings.prod` raises at startup if `DJANGO_SECRET_KEY` is the dev default or shorter than 40 characters.
- **E2E runs against its own server pair** (Django on 8001 with a throwaway SQLite file, Vite on 5174), re-seeded at start, so it never touches the dev database.
- **Quiz window sync locks the student's profile row**, so two workers syncing the same student can't both create a window.

## Sign-in, database and onboarding

- **Sessions are rows.** Each sign-in creates an `AuthSession`; its id is a claim in the refresh token and every access token minted from it. The authentication class rejects tokens whose session was revoked (cached for 60 s), so signing out ends every tab's access token on its next request, not 15 minutes later. Tokens issued before this change have no session and must sign in again.
- **CSRF on the cookie endpoints is a custom header plus Origin.** Refresh and logout require `X-Requested-With: pulse` (a custom header forces a CORS preflight that only the frontend origin passes) and, when the browser sends an Origin, one of the allowed origins. The cookie is also `SameSite=Lax`.
- **Lockout lives in the cache**, keyed by email whether or not the account exists, so it doesn't reveal which emails are registered. Throttles count per IP and per email (`THROTTLE_AUTH`).
- **Sign-up says when an email is taken.** The brief asks for a clear field error; password reset still never reveals whether an email exists.
- **Late sign-ups start fresh.** Joining mid-term enrols you in the term's courses and excuses work whose deadline (or late cut-off) has already passed, so day one is never "falling behind". Chapters from earlier weeks still need reading and are planned.
- **Onboarding progress is its own table; answers live where the app reads them.** Each step writes straight to the profile, user timezone or availability. `Onboarding` stores the current step, completed steps, a version and when schedule inputs last changed; step 5 rebuilds the schedule when availability or preferences changed after it was generated.
- **Two tabs: last save wins.** Every save bumps a version. A save from a tab with an older version still applies, and the response tells that tab to show the latest state.
- **Overlapping blocks merge** (server and browser) instead of being rejected, with a note.
- **The availability grid is hourly, 6 AM to midnight.** At 360 px each cell is about 41 × 44 px; the exact-times editor keeps 30-minute precision and earlier hours. Mouse drags paint several cells; on touch screens cells toggle on tap only, so the page can still scroll.
- **The 30-minute minimum is checked by Postgres**, not SQLite, which can't evaluate time arithmetic in a constraint; the API checks it everywhere. End-after-start, the profile ranges and the email constraint work on both.
- **Default sass level for new students is 2.** Seeded demo students keep 3 so the demo script's "Tone it down" step still goes 3 to 2.
- **SQLite stays for the no-Docker quick start only.** Docker, CI and production run on Postgres.
- **New addresses.** Onboarding is `/onboarding` (outside the app shell), Today is `/pulse/today` (`/pulse` redirects), and Settings is `/settings` for every role. Old `/pulse/onboarding` and `/pulse/settings` links redirect.
- **Instructors and admins go to Learning Hub**; admins also get Django admin in the navigation.
- **Students choose their weekly study hours (2–40, default 10), and it's a hard cap.** The solver never places more than that in a calendar week (Monday to Sunday, the student's time zone), counting sessions already done or scheduled earlier in the week. If work doesn't fit, the overload report says so and, when the weekly limit is what's full, suggests raising it. Seeded students have limits close to their free time so the demo looks the same.
