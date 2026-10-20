# Spec: the employer sees the applications to a job (#23)

Status: **agreed**. The student decided D1 and D2 on 2026-10-20 (criteria: easy to use on a
phone, nothing to redo in #20 / #24 / #25 / #38, less code), and two iterations the same day
(each part reviewed on its own; the access rule of the worker page gets its own commits);
D3–D10 are defaults offered with them and accepted the same day, before any tests.

## Goal

Since #22 workers apply to jobs, but the employer cannot see the applications anywhere except
the admin. This ticket adds a page with the applications to one job, and a page with the
profile of a worker who applied. Accepting and rejecting come in #24, contacts in #25.

Two iterations in one branch and one PR:

1. **Applications page:** `/jobs/<pk>/applications/` and the link from "My jobs".
2. **Worker page:** `/accounts/workers/<pk>/` for the employers the worker applied to, and
   the worker's name on the applications page becomes a link to it.

### Out of scope

- Accept / reject, "Accept 2", "fills the job" hint, the "2 / 3 workers found" bar: #24.
- The number of applications on "My jobs" and grouping by status: #20.
- Phone and email of an accepted worker: #25. Rating and reviews on the profile: #38, #39.
- "· from Ukrainian" and the translated message: #33.

## Iteration 1: the applications page

### Requirements

R1. `/jobs/<pk>/applications/` (URL name `job_applications`) lists the applications to one
    job (D1). Only the job's own employer sees it, in every job status (D3): guests go to
    login, workers get 403, another employer's job and an unknown id give 404 (D4).
R2. The page has the job as a title (job type · date, as on "My jobs"), its status badge, a
    "Back to my jobs" link and the heading "Applications (N)". Without applications:
    "No applications yet." Newest application first (D5).
R3. Each application shows (D6): the worker's name, the team ("Individual" / "Crew of 3") and
    how many workers they bring, the skills, the legal status, "Work permit confirmed" or
    "Work permit not confirmed", the message in quotes (if any), the status badge ("Pending" /
    "Accepted" / "Rejected") and the date it was sent. No phone, no email (#25).
R4. The page makes the same number of queries for 1 and for 10 applications (D7).
R5. "My jobs" gets an "Applications" link on every job card, in every status, next to
    "Edit" / "Cancel job" (D8).
R6. Every UI string is wrapped in `{% translate %}` / `gettext_lazy`.

### Acceptance criteria (→ tests)

AC1. The owner sees the page with every application to the job and its worker's name, team,
     workers offered, skills, legal status, work-permit line, message and status; an
     application to another job is not on it.
AC2. Newest first; without applications "No applications yet."
AC3. A cancelled job's page also opens for the owner.
AC4. A guest goes to login; a worker gets 403; another employer gets 404; an unknown job
     gives 404.
AC5. The page never shows the worker's phone or email.
AC6. The number of queries is the same for 1 and for 3 applications.
AC7. "My jobs" has an "Applications" link to `job_applications` for an open and for a
     cancelled job.

## Iteration 2: the worker page

### Requirements

R7. `/accounts/workers/<pk>/` (URL name `worker_detail`, `pk` = the worker's user id) shows a
    worker's profile to an employer (D2): the name as the title and
    `accounts/_worker_profile_card.html`, no contacts. Only an employer who has at least one
    application from this worker to one of their own jobs (any status) sees it. Guests go to
    login, workers get 403 (D10), every other employer and an unknown id give 404 (D4).
R8. On the applications page (R3) the worker's name is a link to `worker_detail`.
R9. Every UI string is wrapped in `{% translate %}` / `gettext_lazy`.

### Acceptance criteria (→ tests)

AC8. The owner of a job the worker applied to sees the card (name, team, skills, languages,
     legal status, work permit) and no phone or email; also after the job was cancelled.
AC9. Another employer, one the worker never applied to, gets 404; a guest goes to login; a
     worker gets 403, also for their own id; an unknown id and an employer's id give 404.
AC10. On the applications page each worker's name links to `worker_detail` of that worker.

## Decisions

D1. **A separate page per job, `/jobs/<pk>/applications/`** (student, 2026-10-20). On a phone
    it shows only one job's applications; #20 adds a link with the count ("quick links to …
    view applications"), #24 puts its buttons on this page and comes back to it. Rejected:
    inside the "My jobs" cards as on the mockup (with #20's groups the page grows long and
    would need folding later); a block on the job page for the owner (a public page gets
    private parts, and #24 / #25 add more conditions to it). **Revisit when** employers have
    one job at a time and the extra tap annoys them.
D2. **The worker page only for an employer the worker applied to** (student, 2026-10-20). The
    worker shows their data only to whom they wrote; one filter in the queryset. Rejected:
    every logged-in employer (walking `/workers/1`, `/workers/2`, … collects every worker's
    name and legal status); the full profile inside the application, no page (the
    "Link to each worker's profile" item changes and #38 / #39 need the page anyway).
    **Revisit when** employers should look for workers themselves (search, invitations).
D3. **Every job status** (default): a cancelled or filled job's applications are still the
    employer's history, so the view uses the employer's own jobs, not `OwnOpenJobMixin`.
D4. **404, not 403, for another employer** (default, as Edit / Cancel in #16): the queryset
    holds only what this employer may see, so the page does not even tell that the job or
    the worker exists.
D5. **Newest first** (default): the employer opens the page to see what is new. #24 may sort
    by status.
D6. **The application card repeats the profile fields** the issue names (team, skills, legal
    status) plus the work permit, but not the languages (default): enough to choose on the
    list, the rest is one tap away on the profile.
D7. **One query for the applications with their workers and profiles**
    (`select_related("worker__worker_profile")`, default). Skills are a PostgreSQL array in
    the profile row, so they need no extra query.
D8. **The link on "My jobs" for every job, without a count** (default): #20 adds the count and
    the groups.
D9. **The worker page shows no list of their applications** (default): the employer comes
    from the applications page and goes back there with the browser's Back.
D10. **A worker gets 403 on the worker page, also for their own id** (default,
     `EmployerRequiredMixin`): their own page is `worker_profile`.

## Differences from the mockup (docs/mockups/my-jobs.png)

| Mockup | App | Why |
|---|---|---|
| Applications inside the job's card on "My jobs" | a separate page per job; "My jobs" links to it | D1 |
| "Applications (3)" on "My jobs" | "Applications" link without a count | D8, #20 |
| Avatar with initials | no avatar | less code; the name is the link |
| "★ 4,7 (9)", "new, no reviews" | not shown | #39 |
| "· from Ukrainian" | not shown | #33 |
| "Accept 2" / "Reject", "fills the job" hint, "Workers found 2 / 3" | not shown | #24 |
| "Crew of 2 · work permit ✓" on one line | team · workers offered, skills, legal status and work permit as separate lines | the issue asks for skills and legal status too (D6) |
