# Spec: job list on the home page (#18)

Status: **iteration 1 agreed** (the student decided D1–D7 on 2026-10-14, before any tests).
Iteration 2 (filters) is decided later in this file.

## Goal

Workers find jobs. Today employers can post, edit and cancel jobs (#16), but nobody else can
see them anywhere. The ticket comes in two iterations:

1. **The list:** everyone sees the open jobs that have not started yet, 20 per page, soonest
   first, on the home page.
2. **Filters:** date, job type, district (later in this file).

## Requirements (iteration 1)

R1. The home page `/` (URL name `home`, unchanged) shows the job list (D4). The "Coming soon"
    text and `templates/home.html` go.
R2. Everyone sees the list: guests, workers, employers, staff (D1). A logged-in user without a
    role is still sent to the role choice first (`OnboardingMiddleware`, unchanged).
R3. Only jobs that are **open** (`Job.objects.open()`, #16) and **have not started yet**:
    the date is after today, or it is today and the start time is later than now, Munich time
    (D2). A new `JobQuerySet.upcoming()` does the time part. The job status is not changed.
R4. Order: date, then start time, soonest first (D3).
R5. 20 jobs per page (D3); links "Previous" / "Next" and "Page 2 of 3" when there is more
    than one page. A page number that does not exist gives Django's 404.
R6. Above the list: the title "Jobs in Munich" and the number of jobs found on all pages,
    "14 open" (D5).
R7. One card per job, as in the mockup (D6): job type and hourly rate on the first line;
    district · date · start–end time on the second; a badge "Needs 3 workers". No address,
    no description, no employer name (D1).
R8. `Job.end_time` = start time + hours. A shift that ends after midnight shows the next day's
    time ("20:00–06:00").
R9. Guests see one line above the list: "Need workers? Post a job", linking to the signup
    page (D4). Logged-in users do not see it.
R10. No job at all: "No open jobs right now."
R11. Every UI string is wrapped in `{% translate %}` / `gettext_lazy`.

## Out of scope (iteration 1)

- Filters: iteration 2 of this ticket.
- Job detail page and the address: #19. Map, "near me" and the distance in km: #41, #42.
  Photos: #64. Language switcher "EN": #29. The comma in "16,50 €/h": M5 (decided in #16).
- "Needs 3 workers" minus workers already accepted: #24 (no applications yet).
- The employer's "My jobs" page and its card do not change (D6).

## Acceptance criteria (→ tests)

AC1. `upcoming()` keeps a job tomorrow and a job today that starts later, and drops a job
     yesterday and a job today that has already started (the clock is fixed in the test).
AC2. `end_time`: 08:00 + 6 h = 14:00; 20:00 + 10 h = 06:00.
AC3. The home page shows an open upcoming job; it does not show a cancelled, filled, done or
     past job.
AC4. Jobs appear soonest first, also when they were created in another order.
AC5. 21 jobs: page 1 shows 20, page 2 shows 1; "21 open" on both pages.
AC6. `/?page=99` gives 404.
AC7. A guest, a worker and an employer all get the list (status 200).
AC8. The card shows type, rate, district, date, "08:00–14:00" and "Needs 2 workers"; it does
     not show the address or the description.
AC9. A guest sees "Post a job" linking to signup; a logged-in worker does not.
AC10. No jobs: "No open jobs right now."
AC11. A logged-in user without a role is still redirected to the role choice (existing test,
      must stay green).

## Decisions (student, 2026-10-14)

Each question was offered with options and a recommendation, or the student answered first.

D1. **Everyone sees the list, guests included.** A worker sees real jobs and rates before
    signing up; search engines find the page. The card shows only the district, never the
    address; who sees the address is decided in #19. Rejected: logged-in users only, workers
    only (the site looks empty to a newcomer, and the rates are not secret).
D2. **A job that has started disappears from the list by a filter, not by a status change.**
    Changing the status needs a scheduled task (cron), which is paid on Render; the filter
    needs nothing and is always exact. The student's answer: "it becomes inactive".
D3. **20 jobs per page, soonest first.** About 5 cards fit on a 360 px phone screen, so both
    10 and 20 need scrolling; scrolling is easy on a phone, hitting a small "Next" button is
    not, and a text-only page is light. Rejected: 10.
D4. **The list is the home page** (the student's idea). Most visitors are workers; the mockups
    have no landing page, their first worker screen is "Jobs in Munich". Employers get the
    line "Need workers? Post a job". Rejected: a landing page with a "Find jobs" button (one
    more page to write and translate, one more click); a "Jobs" link in the header (too
    tight next to "Log in" / "Register" at 360 px).
D5. **Title "Jobs in Munich" and the count "14 open"**, as in the mockup. The count comes from
    `ListView`'s paginator, no extra query code.
D6. **A new card for the list, as in the mockup; "My jobs" keeps its own.** The worker cares
    about type, rate, place, time and how many people are needed; the employer card shows the
    status and edit links. Changing the shared `_job_summary.html` would change a page that
    works. Rejected: one shared card for both pages.
D7. **The end time is shown ("07:00–15:00"), computed from start time + hours** (`Job.end_time`):
    a worker needs to know when the shift ends. Not stored, so it cannot disagree with hours.

## Differences from the mockup (docs/mockups/jobs-list.png)

| Mockup | App | Why |
|---|---|---|
| "List / Map" switch, "1,2 km" | not shown | #42 |
| Photos on the cards | not shown | #64 |
| "EN" in the header | not shown | #29 |
| Filters | not in iteration 1 | iteration 2 |
| "16,50 €/h" | "16.50 €/h" | M5 (decided in #16) |
