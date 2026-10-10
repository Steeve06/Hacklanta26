# Demo script

About 10 minutes. It follows the acceptance criteria in the build brief.

**Before you start:** run `make demo` (or `python manage.py seed_demo`) to reset the data. This also clears any time-travel. Use one normal browser window for students and a private window for the admin and instructor, so you can stay signed in to both. All passwords are `pulse-demo`.

**Optional opener: a new student.** Click **Create an account** on the sign-in page, sign up, and go through the five onboarding steps: courses, study time on the grid, preferences, reminder style with its live sample, then the schedule Leon builds. Press **Looks good** to land on Today. (Or sign in as `casey@pulse.test`, who stopped at step 3.)

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

## 6. A study check keeps the streak going

Sign in as **maya@pulse.test** (6-check streak). Open **Study checks**: a check is open for the chapters she studied today. Open **Leaderboard** to see her rank and XP this week, with her row highlighted among her classmates; the chips narrow it to one course.

- Open it and press **Start**. The 3-minute clock runs at the top right. The four cards mix kinds: pick an option, type the missing term, and, third, match three key terms to their sentences (tap a term, then its sentence). Each card shows right or wrong, why, and the line of the chapter it comes from.
- Three right out of four passes: the streak goes to 7 with the milestone celebration and the XP earned. A failed first try offers **Try again with new cards**. Answering again after it's settled doesn't count twice.
- To show the clock: start a try and wait three minutes. Unanswered cards count as wrong and the try ends.
- To show a missed check: in Demo controls, click **+1 day** twice on Maya's row without passing it. The window closes, her saved freeze is spent, and the next miss resets the streak. Click **Back to now** afterwards.

## 6b. Ask Leon to change the plan

Still as Maya, click **Ask Leon** in the sidebar.

- Send "I'm busy tomorrow evening". The reply shows the change it would make ("Keep ... free (Busy)"). Nothing has moved yet: check **Week**.
- Press **Confirm**. The chat closes and opens **Week** at that day; within a few seconds the evening is empty and its sessions have moved to other free time.
- Send "Keep Sundays free", then **Not now**: nothing changes. **Start over** clears the chat.

## 6c. Class times shape the plan

Still as Maya, open **Week** and switch to **Course calendar**: CS 201 meets Monday and Wednesday 10:00–11:15, PSY 101 Tuesday and Thursday 11:00–12:15, BUS 210 Tuesday and Thursday 15:30–16:45. Switch back to **Study plan**: no study session overlaps a class. The same times are listed on each course card in **Courses** and in each syllabus.

## 7. An instructor extension

In the private window, sign in as **prof.okafor@pulse.test**. Open **CS 201 > Assignments > Problem Set 2: Stacks and queues**.

- In the roster, click **Extend** on Jordan's row, pick a date a week later and **Save extension**.
- Jordan's plan re-plans within a few seconds (at most 60 s): open his **Week** view and the Problem Set 2 sessions after the next 24 hours have moved later. Sessions in the next 24 hours stay put on purpose, so the plan doesn't jump around.
