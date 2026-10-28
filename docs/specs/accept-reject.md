# Spec: the employer accepts or rejects applications; the job fills itself (#24)

Status: **agreed**. I decided D1–D3 and the three iterations on 2026-10-28 (my criteria: easy
to use on a phone, simple code, the mockup is only a draft), and D15 the same day after asking
why the extra applications should stay rejected; D4–D14 and D16–D20 are Claude's defaults,
which I accepted the same day, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

Since #23 the employer sees the applications on the job page but can only read them. This
ticket lets them accept or reject each one. When the accepted workers reach the number the
job needs, the job becomes "filled" by itself and the other pending applications are
closed ("Job filled"). If an accepted worker drops out, the employer can remove them, the job
opens again and the closed applications are pending again.

Three iterations in one branch and one PR:

1. **Accept and reject:** the buttons, accepting part of a crew, the job fills itself.
2. **Workers found:** "1 of 3 workers found" on the job page, the places left on the job
   list and in the apply form.
3. **Remove an accepted worker:** the application becomes "Cancelled", a filled job opens
   again, the closed applications are pending again.

### Out of scope

- Choosing how many of a crew to accept (a number field): a Stretch idea (D1).
- The worker withdraws their own application: proposed for #26 (D2).
- Phone and address of an accepted worker: #25. Emails about the decision: #27.
- "Workers found 2 / 3" on the "My jobs" cards: not now (features before polish), D19.
- Cancelling a job that has accepted workers: stays as it is (D18).

## Iteration 1: accept and reject

### Requirements

R0. Two new application statuses: "closed" ("Job filled", D15) and, in iteration 3,
    "cancelled" ("Cancelled", D13).
R1. `Application.workers_accepted` (new field, 0 until accepted): how many of the crew the
    employer took. Never more than `workers_offered` (a database check).
R2. `Job.workers_found()`: the sum of `workers_accepted` over its accepted applications (D4).
R3. `Application.accept()` in one transaction (D6): lock the job row, check that the job is
    open and the application pending, set `workers_accepted` = the smaller of
    `workers_offered` and the places left (D1), status "accepted". If the job now has
    enough workers: job status "filled" and every other pending application of the job
    "closed", shown as "Job filled" (D15). If the job is not open or the application not
    pending, nothing is changed and an error is raised.
R4. `Application.reject()`: pending → rejected, only on an open job, the same lock.
R5. POST `/jobs/applications/<pk>/accept/` (`application_accept`) and
    `/jobs/applications/<pk>/reject/` (`application_reject`). Only the employer of the job,
    only for a pending application of an open job (D5): guests go to login, workers get
    403, anything else 404 (as Edit / Cancel, job-form.md D2). GET gives 405.
R6. After the POST: back to the job page at this application (`#application-<pk>`) with a
    message (D3, D8): "Accepted: 2 workers from Andrii Petrenko." / "Rejected: Andrii
    Petrenko." and, when the job fills, "The job is filled. The other pending applications
    were closed." If the application was decided meanwhile (another tab):
    "This application was already decided." and nothing changes.
R7. On the job page, under each pending application of an open job: a green
    "Accept 2" and an outlined "Reject" button side by side (D7). When the crew is bigger
    than the places left, the button says "Accept 1 of 2" (D1).
R8. When accepting it would fill the job, a line under the buttons: "Accepting fills the
    job: the other pending applications will be closed." (D9).
R9. An accepted application shows "Accepted" and, if only part of the crew was taken,
    "1 of 2 workers" in place of "2 workers" (D22).
R10. One log line per accept / reject / filled job, ids only (#124).
R11. Every new string is wrapped for translation.
R11a. After seeing the page (D21-D25): each application status and the job's own status
     in its colour; under the worker's name only how many people come; the rest on the
     box's full width; no crew size and no work-permit line, except a red "Work permit
     not confirmed" chip when it is missing. This changes applications-list.md R3 and R10.

### Acceptance criteria (→ tests)

AC1. `workers_found()` sums `workers_accepted` of accepted applications only; pending,
     rejected and other jobs' applications do not count.
AC2. Accepting a crew of 2 on a job that needs 3 → accepted, `workers_accepted` 2, job
     still open, other applications unchanged.
AC3. Accepting the last places → job "filled", every other pending application "closed",
     an already accepted or rejected one stays as it was.
AC4. Accepting a crew of 2 when 1 place is left → `workers_accepted` 1, job filled (D1).
AC5. `accept()` / `reject()` on an application that is not pending, or of a job that is not
     open, raise an error and change nothing.
AC6. The owner's POST to accept / reject changes the status and redirects to
     `job_detail` + `#application-<pk>` with the message.
AC7. A guest is sent to login; a worker gets 403; another employer gets 404; an unknown id,
     a decided application and a filled or cancelled job give 404; GET gives 405.
AC8. The owner's job page shows "Accept 2" and "Reject" forms for a pending application of
     an open job; "Accept 1 of 2" when 1 place is left; no buttons on an accepted or
     rejected application and on a filled job; the "fills the job" line only when it would.
AC9. A database check stops `workers_accepted` above `workers_offered`.
AC9a. Badges: Pending `badge-warning`, Accepted `badge-success`, Job filled `badge-info`,
      Rejected `badge-error`, also on the worker's own application; the job's Filled
      `badge-info`, Done `badge-secondary`, Cancelled `badge-error`. An application shows
      "2 workers" and neither the crew size nor "Work permit"; "Work permit not
      confirmed" only when it is missing.

## Iteration 2: workers found

### Requirements

R12. On the job page, while workers can apply: "1 of 3 workers found" instead of "Needs 3
     workers" once someone is accepted; with nobody accepted it stays "Needs 3 workers"
     (D10). For every viewer, as on the mockup.
R13. Above the owner's list of applications: "Workers found 2 / 3" with a bar, as on the
     "My jobs" mockup (D11).
R14. The job list card says how many are still needed: "Needs 1 worker" for a job that
     needs 3 and has 2 (job-list.md: deferred to #24).
R15. The apply form allows at most the places left (application.md D4: was the workers
     needed).
R16. The job list and the guest's job page keep their number of queries: the number found
     comes with the jobs (`annotate`), not one query per job (D12).

### Acceptance criteria (→ tests)

AC10. With 2 of 3 found: the job page shows "2 of 3 workers found"; with none "Needs 3
      workers".
AC11. The owner's job page shows "Workers found 2 / 3" and a bar with value 2, max 3.
AC12. The job list card shows "Needs 1 worker" for that job.
AC13. A crew of 3 applying to that job gets at most 1 in the form (no field: 1 is the only
      choice); a POST with 2 is an error.
AC14. The job list and the guest's job page make the same number of queries as before.

## Iteration 3: remove an accepted worker

### Requirements

R17. The status "cancelled" from R0 is used (D13).
R18. `Application.remove()`: accepted → cancelled, on an open or filled job, the same lock.
     A filled job becomes open again (D14) and its closed applications pending again (D15);
     the rejected ones stay rejected.
R19. POST `/jobs/applications/<pk>/remove/` (`application_remove`), the same access rules
     as R5 but for an accepted application of an open or filled job.
R20. On the job page an accepted application has an outlined "Remove" button (D16), and
     the message after it: "Removed: Andrii Petrenko. The job is open again." (the second
     sentence only if it was filled).
R21. The worker sees "Cancelled" on their application on the job page (as the other
     statuses, #22).

### Acceptance criteria (→ tests)

AC15. Removing an accepted application → "cancelled"; `workers_found()` no longer counts it.
AC16. Removing one from a filled job → the job is open again, its closed applications are
      pending, the rejected ones stay rejected.
AC17. `remove()` on a pending, rejected or cancelled application, or on a cancelled or done
      job, raises an error and changes nothing.
AC18. Access as AC7 for `application_remove`.
AC19. The owner's page shows "Remove" only on accepted applications of an open or filled
      job.

## Decisions

D1. **Accept part of a crew, automatically** (mine, 2026-10-28; option C1): "Accept" takes
    as many of the crew as places are left, the crew decides who comes. Maybe it is the only
    application, so blocking would leave the employer stuck. Cost: a new field
    `workers_accepted` and a migration. Rejected: blocking a crew bigger than the places
    (A); accepting more than needed (B); a number field to choose how many (C2: one more
    element on every application on a phone) — kept as a Stretch idea. **Revisit when**
    employers ask to take fewer of a crew than places are left.
D2. **The employer can remove an accepted worker** (mine, 2026-10-28; option B): a worker
    may drop out on the phone (#25) or in the chat (#35), and without this the job stays
    filled for ever. Rejected: final decisions (A); everything reversible (C: rejected
    workers hope in vain); the worker
    withdraws themselves (D): proposed as a comment in #26, where the worker's own page is
    built. **Revisit when** #26 adds "Withdraw".
D3. **Plain POST forms, the page reloads** (mine, 2026-10-28; option A): one view per
    action, a redirect back, tests with the Django test client. Rejected: HTMX (when the job
    fills, every application and the counter change, so the whole section would be swapped;
    a partial template, a CSRF header and JS checked only by E2E). **Revisit when** the
    reload annoys; HTMX can be put on top of the same forms.
D4. **Workers found = the sum of accepted workers, not the number of accepted
    applications** (Claude's default): a crew of 2 is two workers.
D5. **Decisions only on an open job** (Claude's default): a filled job has no pending
    applications left; done and cancelled jobs are history. Removing (R19) also works on a
    filled job, that is its point.
D6. **One transaction with the job row locked** (`select_for_update`, Claude's default): two
    clicks at the same instant (two tabs, a double tap) would otherwise both see "1 place
    left" and accept 2 workers. The second waits for the first and then sees the job filled.
D7. **The rules live in model methods** (`accept()`, `reject()`, `remove()`, Claude's
    default): the views stay short, the unit tests call the methods without HTTP, and the
    admin or a future API cannot skip the rule. Not a signal: a signal hides what happens on
    save.
D8. **Back to the same application** (`#application-<pk>`, Claude's default): after the
    reload the employer does not have to scroll down again.
D9. **A warning line instead of a confirmation page** (Claude's default): accepting the last
    places closes the others, so the employer is told before the tap. No confirmation page
    for Reject either, as on the mockup. **Revisit when** someone rejects by mistake.
D10. **"Needs 3 workers" until someone is accepted** (Claude's default): "0 of 3 workers
     found" sounds bad on a fresh job.
D11. **The bar only on the owner's job page** (Claude's default), daisyUI `progress`, as on
     the "My jobs" mockup.
D12. **The number found comes with the jobs** (`annotate(Sum(...))`, Claude's default) on
     the job list and job page; `accept()` counts again under the lock, because only that
     number is safe from a second click.
D13. **"Cancelled", not "Rejected", after a removal** (Claude's default): the worker should
     see that they were accepted and then taken off, not refused at once.
D14. **A filled job opens again after a removal** (Claude's default): it goes back to the job
     list (if it has not started) and new workers can apply.
D15. **The extra applications are "closed" ("Job filled"), not rejected, and come back as
     pending when the job opens again** (mine, 2026-10-28): nobody refused these workers,
     they were just not needed. A status of their own keeps them apart from the ones the
     employer rejected, the worker sees the true reason, and #27 can say "the job is filled".
     Cost: one more status value. Rejected: "rejected" and never back (Claude's first
     default: they could not apply again, one application per job, #22); leaving them
     pending on a filled job (the worker waits in vain). This changes the issue's "Done
     when…" item "Remaining pending applications are rejected when filled". **Revisit when**
     a job opens again days later and the returning workers are mostly no longer free.
D16. **"Remove" without a confirmation page** (Claude's default), as Reject (D9).
D17. **No admin changes** (Claude's default): a status changed in the admin skips the rules
     (no filling, no closing); the admin is for fixing data by hand.
D18. **Cancelling a job with accepted workers stays as it is** (Claude's default; job-form.md
     D7 left it to M4): only open jobs can be cancelled, filled ones not; the accepted
     workers are not told until #27. Raised in "Docs sync — M4" (#96).
D19. **No bar on "My jobs"** (Claude's default): features before polish.
D20. **Existing data is not migrated** (Claude's default): `workers_accepted` starts at 0;
     before this ticket nothing could accept an application except the admin.
D21. **Status badges in colour** (mine, 2026-10-29, after using iteration 1 on the local
     server: "Rejected" and "Job filled" looked like plain text): the colours of the job
     statuses on "My jobs" (my-jobs.md D7) — Pending yellow, Accepted green, Job filled
     blue (as a filled job), Rejected red (as a cancelled one). One shared
     `_application_status_badge.html`, so the worker's own application has them too.
D22. **One number of workers, bold, under the name** (mine, 2026-10-29): "2 workers", or
     "1 of 2 workers" when part of a crew was taken. I found the number lost in "Crew of 3
     · brings 2 workers", and three formats with "of" ("crew of 10", "2 of 3") confusing.
     The crew's size is on the worker page: the rest of a crew cannot be taken anyway.
     Rejected: "1 worker · 2 offered" for a partial crew (Claude's recommendation); the
     crew's size when bigger than the offer.
D23. **The mockup's compact box** (mine, 2026-10-29: "on the mockup everything is so
     concise"): avatar, name with the number and the badge in one head, the rest on the
     full width with nothing under the avatar; the job's skill and the legal status as two
     chips that wrap whole. No "Work permit confirmed": nobody can apply without it (#22),
     so it was the same on every application. A red "Work permit not confirmed" chip only
     when an admin removed it after applying (Claude's default, accepted the same day: after
     a complaint the employer must not hire someone without the right to work).
D24. **The job's own status in colour on its page** (mine, 2026-10-29): Filled blue, Done
     slate, Cancelled red, as on "My jobs"; "Past" stays grey. my-jobs.md D8 left this
     until #24 makes filled jobs common.
D25. **The message after a decision may be out of view** (mine, 2026-10-29, Claude's
     recommendation): the page comes back at the application (D8), the messages are at the
     top of the page. The changed badges show the result. Rejected: back to the top
     without the anchor (scrolling down after every tap); messages as a toast fixed on the
     screen (every page changes, a small JS) — a polish idea for M8. **Revisit when**
     employers miss what happened.

## Differences from the mockups

| Mockup | App | Why |
|---|---|---|
| "My jobs": Accept / Reject inside the job card | on the job page, in the owner's list | applications-list.md D15 |
| "My jobs": "Accept 2" | "Accept 2", or "Accept 1 of 2" when fewer places are left | D1 |
| "My jobs": "Accepting 2 fills the job: you need only 1 more." | "Accepting fills the job: the other pending applications will be closed." | D9: the closing is what the employer must know |
| "My jobs": "Workers found 2 / 3" bar in the card | the bar on the owner's job page | D11, D19 |
| "My jobs": "Pending" / "Accepted" badges | also "Rejected", "Job filled" and "Cancelled" | D13, D15 |
| "My jobs": "Crew of 2 · ★ 4,7 (9) · work permit ✓" | "2 workers" in bold; the skill and legal status as chips; no work permit | D22, D23 |
| "Job detail": "1 of 3 workers found" | the same once someone is accepted, "Needs 3 workers" before | D10 |
| No way to take back an acceptance | "Remove" on an accepted application | D2 |
