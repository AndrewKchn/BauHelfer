# Spec: Create / edit / cancel job (#16)

Status: **agreed**. The student decided the open questions on 2026-10-11, before any tests.

## Goal

An employer posts a job through a form, sees their jobs on a "My jobs" page, edits a job while
it is open and cancels it. This is the first ticket that goes through the whole request path:
URL → view → form → model → template. It also replaces the single minimum wage of #15 by a
list of rates with start dates in settings, so a job is checked against the minimum wage of its own day
(this covers #17, see D3).

## Requirements

R1. Minimum wages as a dict in `config/settings/base.py` (code, not the database):
    `MINIMUM_WAGES = {date(2026, 1, 1): Decimal("13.90"), date(2027, 1, 1): Decimal("14.60")}`
    (start date → euros per hour).
R2. `jobs.models.minimum_wage_on(day)` returns the rate of the latest start date on or before
    `day`; for a day before the first start date it returns the first rate.
R3. `MINIMUM_WAGE` in `jobs/models.py` stops being a number of its own: it becomes the lowest
    rate in `MINIMUM_WAGES` (13.90), so the model validator and the migration of #15 stay as
    they are. It is the floor for every job;
    the form checks the rate of the job's date (R7).
R4. `Job.objects.open()` returns only jobs with status `open` (a custom QuerySet). The job
    list (#18) builds on it, so cancelled jobs never show up there (see D4).
R5. URLs under `/jobs/` (new `jobs/urls.py`, included in `config/urls.py`):
    - `jobs/new/` → `job_create`
    - `jobs/mine/` → `my_jobs`
    - `jobs/<pk>/edit/` → `job_edit`
    - `jobs/<pk>/cancel/` → `job_cancel`
R6. `JobForm` (`ModelForm`) with the fields job type, description, original language, address,
    district, date, start time, hours, workers needed, hourly rate. Not in the form: employer,
    status, latitude, longitude, created at (set by the view, the model or later tickets).
R7. `JobForm` checks, besides the model validators:
    - the date is today or later (Munich time, `timezone.localdate()`);
    - the hourly rate is at least `minimum_wage_on(date)`. The error names the rate and says
      it is the minimum wage on that date.
R8. The form fields carry browser limits (idea from #15 in #16's comments): `type="date"` with
    `min` = today, `type="time"`, `hours` and `workers_needed` with `min="1" max="10"`,
    `hourly_rate` with `min` = the lowest rate and `step="0.01"`. The server checks stay the
    real protection; the template keeps `novalidate` like the other forms, so the browser
    still shows the right keyboard or picker.
R9. `original_language` is a visible drop-down; on the create form it starts with the
    employer's `preferred_language` (see D8).
R10. All four pages are for employers only: a guest is sent to login, a worker gets 403
     (`RoleRequiredMixin` from `accounts`, as on the profile pages).
R11. Create: an employer without an employer profile is redirected to the profile form with a
     message (see D1). On save the job gets `employer = request.user` and status `open`;
     then a message "Job posted." and a redirect to "My jobs".
R12. Edit and cancel find the job only among the logged-in employer's own **open** jobs
     (`get_queryset()`). Another employer's job, or a job that is not open, gives 404
     (see D2, D7).
R13. Cancel: GET shows a confirmation page with the job; POST sets status `cancelled` (the row
     stays in the database) and redirects to "My jobs" with a message. There is no link that
     cancels on GET (see D6).
R14. "My jobs" lists only the employer's own jobs, all statuses, by date (soonest first), each
     with type, date, start time, district, workers, rate and status. Open jobs have "Edit" and
     "Cancel" links. An empty list shows a short text and a "Post a job" button.
R15. Header menu, employer branch in `templates/base.html`: "Post a job" and "My jobs".
R16. Every UI string is wrapped in `gettext` / `gettext_lazy` / `{% translate %}`; every page
     extends `base.html`.

## Out of scope

- The public job list and its filters: #18 (it uses `Job.objects.open()` from R4).
- The job detail page and who sees the full address: #19.
- The employer dashboard with applications: #20 turns "My jobs" into it.
- Cancelling a filled job (accepted workers would have to be told): M4, with #24 (see D7).
- Photos: #64. Geocoding the address: #41. Translating the description: #38.
- Checking that the work ends before midnight (start time + hours).

## Acceptance criteria (→ tests)

Unit tests (`jobs/tests/test_minimum_wage.py`, `jobs/tests/test_forms.py`, model tests):

AC1. `minimum_wage_on` gives 13.90 on 2026-01-01 and 2026-12-31, 14.60 on 2027-01-01, and the
     first rate for a day before the table starts.
AC2. `MINIMUM_WAGE` equals the lowest rate in `settings.MINIMUM_WAGES`.
AC3. `Job.objects.open()` returns the open job and none of the filled, done or cancelled ones.
AC4. The form accepts a rate equal to the minimum wage of the job's date and rejects one cent
     less, with an error on `hourly_rate` that names the rate. The same rate is accepted on a
     date before a rise and rejected on a date after it.
AC5. The form rejects yesterday and accepts today.
AC6. The form has no employer, status or coordinate fields.
AC7. The rendered form has `type="date"`, `type="time"`, `min="1" max="10"` on hours and
     workers, and `step="0.01"` on the rate.

Integration tests (Django test client, `jobs/tests/test_views.py`):

AC8. A guest opening any of the four pages is sent to login; a worker gets 403.
AC9. An employer without a profile who opens "Post a job" is redirected to the profile form.
AC10. An employer with a profile posts a valid form: one job is saved with them as employer
      and status `open`, and they land on "My jobs", which shows it.
AC11. An invalid post (rate below the minimum wage) saves nothing and shows the error.
AC12. The create form starts with the employer's preferred language selected.
AC13. The owner edits an open job: the change is saved, the employer stays the same.
AC14. Another employer gets 404 on edit and cancel (GET and POST), and the job is unchanged.
AC15. Edit and cancel of a job that is not open give 404.
AC16. GET on cancel shows the confirmation and changes nothing; POST sets `cancelled` and
      keeps the row.
AC17. "My jobs" shows only the employer's own jobs; "Edit" / "Cancel" only for open ones.
AC18. The header menu of an employer has "Post a job" and "My jobs"; a worker's has neither.

## Decisions (student, 2026-10-11)

Each question was offered with options and a recommendation; the student took every
recommendation.

D1. **An employer profile is required before posting** (open since #12). Workers will see the
    company name on the job (#19). Checked with `hasattr(user, "employer_profile")`, as #22
    will do for workers. Rejected: posting right after choosing the role.
D2. **Another employer's job gives 404, not 403.** `get_queryset()` returns only the user's
    own jobs, so for the view another employer's job does not exist; the answer does not even
    tell that a job with this id exists. Rejected: 403 with a separate owner check.
D3. **Minimum wages as a dict in settings, #17 closed by this ticket.** The rate is now
    needed in two places (the model validator as the floor, the form for the job's date),
    and #17 asked for settings. In #15 AI had put the constant in `jobs/models.py` without
    checking #17; the student asked why and moved it. It stays code, as decided in #15: a new
    rate needs a commit and a redeploy. The 2027 rate is already in the dict, so 1 January
    2027 needs no deploy. The form checks the rate of the job's date (decided in #95 after
    #15). #17's "Done when…" items are covered here; it is closed as done in #16. Rejected:
    a date check here and settings in #17 (two tickets on the same lines); keeping the rates
    in `jobs/models.py` (#17 would have to be rewritten).
D4. **`Job.objects.open()` now, the list in #18.** The "cancelled jobs are hidden" item is
    ticked with the test of AC3; #18 gets a note to build the list on `open()`. Rejected:
    moving the item to #18; a bare list page now that #18 would redo.
D5. **A simple "My jobs" page.** Without it an employer could reach edit and cancel only by
    typing the URL. #20 turns it into the dashboard. Rejected: redirect to the home page.
D6. **Cancel with a confirmation page** (GET asks, POST cancels), the usual Django way (like
    `DeleteView`), works without JavaScript and protects against a slip of the finger on a
    phone. Rejected: one POST button without confirmation.
D7. **Only open jobs can be edited or cancelled.** The ticket says "edit while it is open";
    cancelling a filled job is decided in M4 when there are accepted workers to tell.
    Rejected: cancelling open and filled jobs.
D8. **`original_language` visible, preset to `preferred_language`.** An employer with the
    Russian interface may write the description in German; a hidden field would send a wrong
    source language to the translation (#38). Rejected: a hidden field set automatically.
