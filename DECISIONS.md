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
- **Chapter quizzes are sessions in the solver.** After placement, one 10-minute `chapter_quiz` session goes after the last study session of the chapters finishing that day, or on the next day, so it always sits inside the quiz window.
- **OR-Tools is optional.** `SOLVER=cpsat` is accepted but falls back to the greedy solver (with a log line) unless `ortools` is installed; the greedy + local search meets every budget on its own.

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
