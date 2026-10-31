# Spec: worker dashboard "My applications" (#26)

Status: **agreed**. I decided D1–D6 on 2026-10-31 (my criteria: the same tabs as "My jobs";
the employer must see what happens, and a worker who drops out has dropped out; "Past" is
what is over and did not happen). D7–D20 are Claude's defaults, which I accepted on
2026-10-31, before any tests. D13 I changed and D21 I accepted on 2026-10-31 after seeing
the page.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted.

## Goal

A worker has no page with all their applications: each one is seen only on its own job page.
This ticket adds "My applications": the worker's applications in tabs by status, an accepted
one with the employer's contact and the address, and a "Withdraw" button. "Past" tabs on both
dashboards collect what is over and did not happen.

Three iterations in one branch and one PR:

1. "My applications": tabs, cards, contact box, the worker's "Past" tab, menu link.
2. "Withdraw" and the "Withdrawn" status.
3. The employer's "Past" tab on "My jobs".

### Out of scope

- "Open chat" on an accepted application: #35.
- "Done" and "Rate the employer": #37, #38, #39.
- The green "… accepted your application" banner: there are no notifications; emails are #27.
- An email to the employer when a worker withdraws: #27.
- Edit and cancel views refusing past jobs: #37 (D6; this ticket only hides the links).

## Iteration 1: "My applications"

### Requirements

R1. `Job.is_over` (a property): True from the day after the day the job ends, Munich time
    (contacts.md D4). `Application.shows_contacts` uses it, so the rule stays in one place
    (D8).
R2. `Application.tab` (a property): which tab the application is in (D3, D9, D10):
    - pending, and the job cancelled → "cancelled";
    - pending or "Job filled", and the job `is_over` → "past";
    - otherwise its status.
R3. `jobs/applications/` (`my_applications`): workers only (a guest goes to login, an employer
    gets 403). Only the logged-in worker's own applications, each with its job and the job's
    employer in the same query, the photos in one more (D11).
R4. Tabs in this order, only those that have applications: Accepted, Pending, Job filled,
    Rejected, Cancelled, Past (D12). Each tab has its count. Inside a tab, the soonest job
    first, and the jobs that are over last (D21).
R5. The tabs are the same component as on "My jobs": `templates/_status_tabs.html`, used by
    both pages (D2). "My jobs" looks and works as before.
R6. Each card as on "My jobs": the photo or the placeholder (`jobs/_job_thumbnail.html`) and
    the job summary (`jobs/_job_summary.html`, title links to the job page), no status badge
    (D13). Under them, on the card's full width: how many of the crew, "2 workers", or "1 of 2
    workers" when only part of the crew was taken.
R7. An accepted application that `shows_contacts`: a "Contact" box with the employer's name,
    phone (or "not given") and the job's exact address (D14). The email is never shown
    (contacts.md R5).
R8. A pending application: "Your message: “…”" if there is one (D15).
R9. One short line per closed status (D16):
    - Rejected: "The employer chose other workers."
    - Job filled: "The job was filled by other workers."
    - Cancelled, accepted before: "The employer cancelled your place."
    - Cancelled, the job cancelled: "The employer cancelled the job."
    - Past: "The job is over."
    - Accepted, no longer `shows_contacts`: "The job is over. The contacts are no longer
      shown."
R10. On the job page, a pending application of a cancelled job shows the badge "Job
     cancelled" (D9).
R11. No applications: "You have not applied to any job yet." and a link "Find a job" to the
     job list.
R12. The menu of a worker gets "My applications" after "My profile".
R13. Every new string is wrapped for translation.

### Acceptance criteria (→ tests)

AC1. `Job.is_over`: False on the day the job ends, True the day after; a job that ends after
     midnight is over only the day after that next morning.
AC2. `shows_contacts` keeps its #25 tests green (it now uses `is_over`).
AC3. `Application.tab`: each status of an open job gives its own tab; pending and "Job
     filled" of a job that is over give "past"; accepted, rejected and cancelled of a job
     that is over keep their tab; pending of a cancelled job gives "cancelled".
AC4. A guest is sent to login; an employer gets 403.
AC5. A worker sees only their own applications, never another worker's.
AC6. The tabs come in the order of R4, empty ones left out, each with its count.
AC7. The number of queries does not grow with the number of applications.
AC8. An accepted application of a job today shows the employer's phone and the address; a
     pending one, and an accepted one the day after the job, show neither. No email.
AC9. The lines of R8–R10 for each case.
AC10. A worker without applications sees the empty text and the link.
AC11. The worker's menu has "My applications"; the employer's has not.
AC12. "My jobs" still passes its tests (#20).

## Iteration 2: "Withdraw"

### Requirements

R14. A new status "withdrawn" ("Withdrawn"): a new choice, a migration without a new column
     (D4).
R15. `Job.has_started` (a property), the part of `accepts_applications` that compares with
     now; `accepts_applications` uses it.
R16. `Application.can_withdraw` (a property): pending, "Job filled" or accepted, the job open or
     filled, and not `has_started` (D5, D17).
R17. `Application.withdraw()` in one transaction, the job row locked (`_lock`, accept-reject.md
     D6): status "withdrawn". If it was accepted and the job filled, the job opens again and
     its "Job filled" applications are pending again, as `cancel()` does (D18). Raises
     `ApplicationStateError`, and changes nothing, unless `can_withdraw`. Returns whether the
     job opened again.
R18. `jobs/applications/<pk>/withdraw/` (`application_withdraw`): POST only, workers only, the
     worker's own application only (any other id: 404). Back to "My applications" with
     "Application withdrawn." or, if it cannot be withdrawn any more, "This application can
     no longer be withdrawn." Logged with ids only (#124).
R19. "Withdraw" button on the card's crew line while `can_withdraw`, only on "My
     applications" (D19); the browser asks "Withdraw your application? This cannot be
     undone." first.
R20. The employer sees the application with the badge "Withdrawn" and no buttons (D4). It
     shows no phone (`shows_contacts` is False).
R21. The worker's tab "Withdrawn" after "Cancelled", before "Past"; its card says "You
     withdrew this application." (D16). Withdrawn is final: the worker cannot apply to that
     job again (the unique constraint, application.md D5).

### Acceptance criteria (→ tests)

AC13. `can_withdraw` for each status, for an open, filled, cancelled job, before and after
      the start.
AC14. `withdraw()` of a pending one: "withdrawn", the job unchanged. Of an accepted one of a
      filled job: the job open, the "Job filled" ones pending. Of a rejected one, or after
      the start: the error, nothing changed.
AC15. POST: the worker's own application withdrawn, the message, the redirect. Another
      worker's application: 404. GET: 405. An employer: 403. A guest: login.
AC16. The button is on the card only while `can_withdraw`.
AC17. The employer's job page shows "Withdrawn" without buttons and without the phone.
AC18. The job page does not offer the apply form after withdrawing.

## Iteration 3: the employer's "Past" tab

### Requirements

R22. On "My jobs", an open job that `is_over` goes into a tab "Past" after "Cancelled" (D6).
     Filled, done and cancelled jobs stay in their tabs.
R23. A job in "Past" shows no "Edit" and "Cancel job" links (D6).

### Acceptance criteria (→ tests)

AC19. An open job the day after it ends is in "Past"; on its day it is in "Open". A filled
      and a cancelled job the day after stay in "Filled" and "Cancelled".
AC20. A job in "Past" has no edit or cancel link.

## Decisions

D1. **Tabs by status, as on "My jobs"** (mine, 2026-10-31; option A). Rejected: headed sections
    on one page (B: no JavaScript, but not like #20); one list with badges as the mockup (C:
    the least code, but not "grouped by status").
D2. **One tab component for both pages** (mine, 2026-10-31): the tab strip, the swipe and the
    script are written once in `templates/_status_tabs.html`; each page passes its groups and
    its card template. Each group brings its colour from the view, since the two pages have
    different statuses. Rejected: a copy of the 70 lines (two places to fix). Costs: "My jobs"
    is reworked in iteration 1, its card moves to `jobs/_my_job_card.html`.
D3. **"Past" is what is over and did not happen** (mine, 2026-10-31; option A): the employer's
    open jobs and the worker's pending and "Job filled" applications whose day is over. A
    filled job and an accepted application stay in their tabs: the work probably happened,
    and #37 marks it done from there. Rejected: everything past except cancelled (B: "Past"
    mixes the expired with what waits for "Done"). **Revisit when** #37 adds "Done".
D4. **Withdrawing sets a status "Withdrawn"; the row stays** (mine, 2026-10-31): the employer
    sees that the worker left, and the worker cannot apply again. Rejected: deleting the row
    (the application disappears from the employer's page without a trace, and the worker
    can apply again); reusing "Cancelled" (the employer cannot tell "I took them off" from
    "they left").
D5. **Every application that is still in play can be withdrawn: pending, "Job filled",
    accepted** (mine, 2026-10-31). Proposed in #24 (accept-reject.md D2).
D6. **The employer gets a "Past" tab too, computed, without cron** (mine, 2026-10-31): a
    status changed at a set time needs a scheduled task (contacts.md D4); a tab chosen when
    the page is shown does not. Edit and cancel links are hidden there; the views still
    accept a past open job. **Revisit when** #37 (posted to #96).
D7. **The order of the work: three iterations** (Claude's default, accepted): the worker's
    page first, since the other two build on it.
D8. **`Job.is_over` is the one "the day is over" rule** (Claude's default, accepted):
    contacts and both "Past" tabs ask it, so they can never disagree.
D9. **A pending application of a cancelled job is in "Cancelled", with the badge "Job
    cancelled"** (Claude's default, accepted): it was left open by #25 (contacts.md D9).
    "Pending" would promise an answer that will never come.
D10. **The tab is a property of the application, not computed in the template** (Claude's
     default, accepted): the rule is tested without HTTP, as `shows_contacts`.
D11. **One query for the list** (Claude's default, accepted): `select_related` brings the job
     and the employer with each application; the tabs are made in Python from that list, as
     on "My jobs".
D12. **Accepted first** (Claude's default, accepted): what the worker has to act on (call,
     go to work) comes first; then what waits, then what is closed.
D13. **The card looks like a "My jobs" card: photo, summary, no status badge** (mine,
     2026-10-31, after seeing the page; option A). My criteria: one style with "My jobs", and
     less space. The tab already says the status; the line of R9 explains the special cases.
     Costs one more query for the photos, not one per card. Rejected: the summary next to a
     status badge, without a photo (Claude's first default: the badge took the width, the
     lines wrapped and left empty space, and it looked unlike "My jobs"); the badge under the
     title (B: more compact, but still unlike "My jobs"). **Revisit when** status badges on
     the cards of both dashboards are tried (I want to try them for the employer too).
D14. **The contact box: name, phone, address, as on the mockup** (Claude's default,
     accepted). The company name is not in it: the title links to the job page, which has
     the whole employer card.
D15. **The worker's own message only while pending** (Claude's default, accepted), as on the
     mockup: after a decision it no longer matters.
D16. **One short line saying why it is closed** (Claude's default, accepted): the mockup's
     "the employer chose another crew". Neutral words, no blame.
D17. **Withdraw until the job starts** (Claude's default, accepted): the same moment the job
     stops taking applications (`has_started`). After it, leaving is not withdrawing.
D18. **Withdrawing an accepted worker works like the employer's "Cancel"** (Claude's default,
     accepted): the place is free again, the job opens, the closed applications are pending
     again (accept-reject.md D13–D15). The code is shared with `cancel()`.
D19. **"Withdraw" only on "My applications"** (Claude's default, accepted): one place for the
     button; the job page keeps its "You applied" card. On the crew line, so it takes no line
     of its own (accepted after seeing the page).
D20. **Colours** (Claude's default, accepted): the tabs of "My applications" in the colours of
     `_application_status_badge.html`; "Withdrawn" and "Past" a quiet grey (`bg-base-300`):
     nothing to do there. Tried after seeing the page: `badge-neutral`, the first default, is
     dark blue in the light theme and was the loudest badge on the employer's card;
     `badge-ghost` has the card's own background, so the badge and the active tab looked like
     plain text. **Revisit when** the buttons get the colours of their statuses (my idea,
     posted to #96): the colours of all statuses are decided there together.
D21. **Jobs that are over go to the end of their tab** (Claude's default, accepted after
     seeing the page): soonest first put yesterday's accepted job above tomorrow's, the one
     the worker opens the page for.

## Known limitations (→ docs/SECURITY.md)

- The edit and cancel views accept a past open job (only the links are hidden): #37.
- The employer learns about a withdrawal only on the job page; emails are #27.

## Differences from the mockups

| Mockup | App | Why |
|---|---|---|
| One list with badges | tabs by status, as "My jobs"; no badge on the card, a photo instead | D1, D13 |
| "Open chat" | none | #35 |
| "Done" and "Rate the employer" | none; accepted stays "Accepted" | #37–#39, D3 |
| Green banner "… accepted your application" | none | no notifications; #27 |
| Contact: name, phone, address | the same | D14 |
| — | "Withdraw" button | D5, D19 |
| — | "Past" tab | D3 |
