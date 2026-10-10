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
