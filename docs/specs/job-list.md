# Spec: job list on the home page (#18)

Status: **agreed**. Iteration 1: the student decided D1–D7 on 2026-10-14, before any tests,
and D8 on 2026-10-16. Iteration 2: D9–D12 on 2026-10-16, before its tests, and D13 after
looking at the page on a laptop.

## Goal

Workers find jobs. Today employers can post, edit and cancel jobs (#16), but nobody else can
see them anywhere. The ticket comes in two iterations:

1. **The list:** everyone sees the open jobs that have not started yet, 20 per page, soonest
   first, on the home page.
2. **Filters:** date, job type, district (see "Iteration 2" below).

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
    the district on the second, cut with "…" if it does not fit (D8); date · start–end time
    on the third; a badge "Needs 3 workers". No address, no description, no employer name
    (D1).
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
D8. **The district has a line of its own and is cut with "…" if it is too long; date and time
    are on the next line** (the student's change after looking at the page in the browser,
    2026-10-16). With district, date and time on one line, long district names wrapped
    differently in every card. The full name is on the job page (#19). Rejected: one line that
    wraps (the first version, as in the mockup); the "Needs 3 workers" badge on the right of
    the district or the date line (measured at 360 px: about 130 px free, the badge needs
    146 px in English and up to 199 px in Polish).

## Differences from the mockup (docs/mockups/jobs-list.png)

| Mockup | App | Why |
|---|---|---|
| "List / Map" switch, "1,2 km" | not shown | #42 |
| Photos on the cards | not shown | #64 |
| "EN" in the header | not shown | #29 |
| Filters | not in iteration 1 | iteration 2 |
| "16,50 €/h" | "16.50 €/h" | M5 (decided in #16) |
| "Schwabing-West · Thu 22 Oct · 07:00–15:00" on one line | district, then date and time on the next line | D8 |

## Iteration 2: filters

### Requirements

R12. Above the list, a GET form with three drop-downs and a "Show" button (D9, D10): "Date"
     (Any day / Next 7 days / Next 30 days), "Job type" (All types + the job types),
     "District" (All districts + the districts). Date and job type share the first row,
     district and the button the second (D11).
R13. "Show" reloads the page with the choice in the address, e.g.
     `/?date=7&job_type=demolition&district=sendling`. Without JavaScript the same happens.
R14. "Next 7 days" is today and the 6 days after it; "Next 30 days" today and the 29 after it
     (D12). Together with R3: a job today that has started is still not shown.
R15. The filters live in one place: `JobFilterForm` in `jobs/forms.py`, with a method that
     narrows a queryset. `JobListView` only calls it; the map (#42) will call it too (D10).
R16. A value that is not in a list (`?district=moon`) is ignored: the list is shown without that
     filter. No error message.
R17. The drop-downs show what is chosen after the reload. The count ("5 open") counts the
     filtered jobs. Page links keep the filters (`?page=2&district=sendling`), using Django's
     `{% querystring %}` tag.
R18. Nothing found with a filter chosen: "No jobs match these filters." Without filters the
     text stays "No open jobs right now."
R19. With at least one filter chosen, a "Reset filters" link to the home page without
     parameters is shown under the form.
R20. The "Need workers? Post a job" line for guests moves under the form.
R21. From `lg` (1024 px) the page is wider (`max-w-6xl` instead of the `max-w-3xl` of other
     pages, via a `main_width` block in `base.html`): the filters, "Reset filters" and the line
     for guests are a 16rem column on the left that stays in place while the list scrolls;
     the fields are one under the other, "Show" as wide as the column (D13). The phone layout
     does not change.

### Out of scope (iteration 2)

- Updating the list without a reload (HTMX): rejected in D9, may come back (see "Revisit").
- "Near me" and the distance: #42. A date picker for one exact day.

### Acceptance criteria (→ tests)

AC12. The form is valid when empty and with any listed value; a value that is not listed
      makes only that field invalid.
AC13. Job type and district filters keep only matching jobs; both together keep jobs that
      match both.
AC14. "Next 7 days" keeps jobs today (not started) up to today + 6 and drops today + 7;
      "Next 30 days" keeps today + 29 and drops today + 30 (the clock is fixed in the test).
AC15. `?district=moon` shows the same list as no filter.
AC16. After `?district=sendling` the district drop-down has "Sendling" selected and the count
      counts only Sendling jobs.
AC17. With 21 Sendling jobs and `?district=sendling`, the "Next" link keeps
      `district=sendling`.
AC18. No match: "No jobs match these filters." and a "Reset filters" link to `/`. No filter:
      no "Reset filters".
AC19. The form uses GET (no CSRF token needed, the address can be shared) and has a "Show"
      button.

### Decisions (student, 2026-10-16)

D9. **A plain GET form with a "Show" button; the whole page reloads (option 1), no HTMX.**
    Three options were compared: 1) GET form + reload; 2) HTMX swaps only the list, no
    button; 3) GET form + HTMX on top. The student's criteria: 1) simple code, 2) the map
    (#42) coming later, 3) the browser's "Back" button. An experiment with option 2 (district
    only, not committed) showed the cost: the template split into page + part, a second
    template in the view (`get_template_names`), the count moved into the part, and a bug:
    after "Back" the list showed Laim but the drop-down "All districts", because HTMX restores
    a saved copy of the HTML without the chosen `<select>` value. Leaflet (#42) draws the map
    with JavaScript, which conflicts with swapping parts of the page; with a reload the map
    is simply drawn again. The student also corrected my assumption that workers search on
    the building site with a slow connection ("people work there, they do not look for jobs").
    This changes the ticket's "Filters update the list via HTMX". Rejected: options 2 and 3.
    **Revisit when** building the map (#42), or if users find the reload annoying: HTMX can
    be added on top of the GET form without changing the view's filter.
D10. **The filter lives in one place, `JobFilterForm`** (the student's condition for D9). A
     Django form checks the values against the lists and draws the drop-downs. Rejected:
     reading `request.GET` in the view (no check, the map would need a copy).
D11. **Layout A: the button next to the district** (the student's idea, compared at 360 px with
     a full-width button under the form). One row shorter; a very long district is cut in the
     drop-down. Rejected: layout B (full-width button).
D12. **"Next 7 / 30 days" counted from today**, not "this week / this month" by the calendar:
     on a Sunday "this week" would be one day. "Any day" is the default. Rejected: calendar
     week and month; a date picker.
D13. **On laptops the filters are a column on the left that stays in place** (the student's
     idea, 2026-10-16, after the prototype at 1280 px). From `lg` (1024 px), not `md`: the
     student does not expect workers to use tablets. Sticky, so a filter can be changed
     without scrolling back up through 20 cards. The page is made wider only here, through a
     new `main_width` block in `base.html`; other pages keep 768 px. Rejected: filters above
     the list on every screen; switching from `md`; two cards per row on laptops (offered,
     not taken). The mockups are phone-only, so this adds to them rather than differs.
