# Demo script

About 10 minutes. It follows the acceptance criteria in the build brief.

**Before you start:** run `make demo` (or `python manage.py seed_demo`) to reset the data. This also clears any time-travel. Use one normal browser window for students and a private window for the admin and instructor, so you can stay signed in to both. All passwords are `pulse-demo`.

**Optional opener: a new student.** Click **Create an account** on the sign-in page, sign up, and go through the five onboarding steps: courses, study time on the grid, preferences, reminder style with its live sample, then the schedule Pulse builds. Press **Looks good** to land on Today. (Or sign in as `casey@pulse.test`, who stopped at step 3.)

## 1. A student who is badly behind

Sign in as **jordan@pulse.test**.

- Today shows the mascot in the **Falling behind** state with three reasons (missed sessions, hours short, a missed paper).
- The **Not everything fits** panel lists what can't be finished on time, how many hours are missing, and what would help: add study blocks on specific days, or ask for an extension.

## 2. Add study time

Click **Add study time** (it opens Settings). In the weekly grid, tap a few evening hours on Monday and Wednesday, then **Save study time**.

- The schedule re-plans in the background (a few seconds with the worker running).
- Back on Today, the shortfall drops from about 27 hours to under 10, and the week view shows the new sessions. Add a Saturday block too if you want the overload to shrink further.

## 3. Reminders

In the private window, sign in as **admin@pulse.test**. You land on **Demo controls**.

- Click **Run notification scan for everyone**. "Send now even during quiet hours" is ticked, so nothing waits for the morning.
- In Jordan's window the bell shows a new reminder. Open it: the copy depends on the trigger and sass level (for example "The deadline passed. The late window closes in 17 h. I believe in redemption arcs.").
- For browser push, click **Turn on push** in Jordan's inbox first and allow notifications, then run the scan again.
- More triggers fire closer to deadlines. On Sam's row click **+1 day** four times, then **Scan**: Sam gets due-soon and falling-behind reminders such as "Three days until Problem Set 2: Stacks and queues. I'm sure you've started. I'm sure." Caps (5 a day, 2 per assignment) and the 14-day no-repeat rule apply. Click **Back to now** before step 5.

## 4. Tone it down

In Jordan's inbox, click **Tone it down**. A toast confirms the new sass level (3 to 2), and the next reminders use the gentler copy. Five taps in a row switch on supportive mode, which shows a banner and can be turned off in Settings.

## 5. Submit work in Learning Hub

Sign in as **sam@pulse.test**. Go to **Courses > CS 201 > Assignments > Problem Set 2: Stacks and queues**, type a short answer and **Submit**.

- Open **Today**: confetti and the celebrate animation play once, and the sessions planned for Problem Set 2 are gone from Today and Week.

## 6. Today's flashcards keep the streak going

Sign in as **maya@pulse.test** (6-day streak). Open **Quiz**; the week strip shows the last six days done and today still open, and today's deck says which upcoming deadline it's prepping for.

- **Start today's flashcards**. For each of the five cards, **Show answer** (or tap the card), then **Got it** or **Still learning**.
- The result reads "Counted for your streak: 7 days in a row. That's a 7-day milestone." with confetti. Opening the deck again doesn't count the day twice, and cards marked "Still learning" come back in the next decks.
- To show a missed day: in Demo controls, click **+1 day** twice on Maya's row without doing the deck. The first missed day spends her saved freeze; the second resets the streak and sends a "streak reset" reminder. Click **Back to now** afterwards.

## 7. An instructor extension

In the private window, sign in as **prof.okafor@pulse.test**. Open **CS 201 > Assignments > Problem Set 2: Stacks and queues**.

- In the roster, click **Extend** on Jordan's row, pick a date a week later and **Save extension**.
- Jordan's plan re-plans within a few seconds (at most 60 s): open his **Week** view and the Problem Set 2 sessions after the next 24 hours have moved later. Sessions in the next 24 hours stay put on purpose, so the plan doesn't jump around.
