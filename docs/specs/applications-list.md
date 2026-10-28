# Spec: the employer sees the applications to a job (#23)

Status: **agreed**. I decided D1 and D2 on 2026-10-20 (my criteria: easy to use on a phone,
nothing to redo in #20 / #24 / #25 / #38, less code), and two iterations the same day (each
part reviewed on its own; the access rule of the worker page gets its own commits); D3–D10
are Claude's defaults, which I accepted the same day, before any tests. After seeing the
built pages of iteration 2 I asked for the mockup's layout (D11) and only the job's skill on
an application (D12), the same day; D13 and D14 are Claude's defaults offered with them. On
2026-10-25, after using both pages on the local server, I moved the list onto the job page
and removed the separate page (D15, D16, D18); D17 is Claude's default offered with them.
The separate page is kept on the local branch `23-separate-applications-page` for
comparison, not merged.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

Since #22 workers apply to jobs, but the employer cannot see the applications anywhere
except the admin. This ticket shows the applications to a job on the job's own page, to its
employer only, and adds a page with the profile of a worker who applied. Accepting and
rejecting come in #24, contacts in #25.

Two iterations in one branch and one PR:

1. **Applications page:** `/jobs/<pk>/applications/` and the link from "My jobs".
   *Replaced in iteration 2 (D15).*
2. **Worker page and the list on the job page:** `/accounts/workers/<pk>/` for the employers
   the worker applied to; the applications move onto the job page, laid out as on the
   mockup, and the separate page goes.

### Out of scope

- Accept / reject, "Accept 2", "fills the job" hint, the "2 / 3 workers found" bar: #24.
- The number of applications on "My jobs" and grouping by status: #20.
- Phone and email of an accepted worker: #25. Rating and reviews on the profile: #38, #39.
- "· from Ukrainian" and the translated message: #33.

## Iteration 1: the applications page

*Replaced in iteration 2 by R13–R17 (D15): kept here because its commits are in the branch.
R3, R4 and R6 still hold for the list on the job page.*

### Requirements

R1. `/jobs/<pk>/applications/` (URL name `job_applications`) lists the applications to one
    job (D1). Only the job's own employer sees it, in every job status (D3): guests go to
    login, workers get 403, another employer's job and an unknown id give 404 (D4).
R2. The page has the job as a title (job type · date, as on "My jobs"), its status badge, a
    "Back to my jobs" link and the heading "Applications (N)". Without applications:
    "No applications yet." Newest application first (D5).
R3. Each application shows (D6): the worker's name, the team ("Individual" / "Crew of 3")
    and how many workers they bring, the skills, the legal status, "Work permit confirmed"
    or "Work permit not confirmed", the message in quotes (if any), the status badge
    ("Pending" / "Accepted" / "Rejected") and the date it was sent. No phone, no email
    (#25).
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

## Iteration 2: the worker page and the list on the job page

### Requirements

R7. `/accounts/workers/<pk>/` (URL name `worker_detail`, `pk` = the worker's user id) shows
    a worker's profile to an employer (D2): "Worker profile" as the title (D14) and
    `accounts/_worker_profile_card.html`, no contacts. Only an employer who has at least one
    application from this worker to one of their own jobs (any status) sees it. Guests go to
    login, workers get 403 (D10), every other employer and an unknown id give 404 (D4).
R8. In the list of applications (R13) the worker's name is a link to `worker_detail`.
R9. Every UI string is wrapped in `{% translate %}` / `gettext_lazy`.
R10. Each application is a tinted box as on the mockup (D11): avatar, name, status badge,
     "Crew of 2 · brings 2 workers", legal status · work permit, the job's skill, the
     message, the date (R3).
R11. Each application has an avatar with the worker's initials (`User.initials()`, D13).
R12. Instead of all skills, an application shows only the job's own skill (D12):
     a green badge "✓ Demolition" when the worker has it, the same badge grey with an
     outline, "− Demolition", when not (a screen reader hears "No skill: Demolition").
R13. On the job page (`job_detail`) the job's own employer sees, instead of the employer
     card, a section "Applications (N)" (`id="applications"`) with every application to the
     job, newest first, in every job status; "No applications yet." without any (D15, D16).
R14. Everyone else (guests, workers, also one who applied, other employers) sees the job
     page as before: the employer card and no list (D16).
R15. The link at the top of the job page is "← My jobs" for the job's employer and "← Jobs"
     for everyone else (D17).
R16. The owner's job page makes the same number of queries for 1 and for 3 applications; a
     guest's page keeps its 2 queries (#19 AC14, #22 AC11).
R17. The separate page `/jobs/<pk>/applications/` and its "Applications" link on "My jobs"
     are removed (D15, D18).

### Acceptance criteria (→ tests)

AC8. The owner of a job the worker applied to sees the card (name, team, skills, languages,
     legal status, work permit) and no phone or email; also after the job was cancelled.
AC9. Another employer, one the worker never applied to, gets 404; a guest goes to login; a
     worker gets 403, also for their own id; an unknown id and an employer's id give 404.
AC10. In the list on the job page each worker's name links to `worker_detail` of that
      worker.
AC11. `initials()`: "Andrii Petrenko" → "AP", "Maria del Carmen García López" → "ML",
      "Mehmet" → "M", "Іван Петренко" → "ІП", extra spaces and small letters → "IP",
      an empty name → "".
AC12. An application shows the worker's initials in its avatar.
AC13. A worker with the job's skill and others gets "✓ Demolition" and none of the other
      skills; a worker without it gets the grey "− Demolition" with the hidden "No skill:".
AC14. The owner's job page has "Applications (N)" with each application's name, team,
      workers offered, legal status, work-permit line, message, status and date, newest
      first; an application to another job is not on it; without applications "No
      applications yet."; a cancelled job's page has its list too.
AC15. A guest, a worker who applied and another employer see the employer card and none of
      the applications.
AC16. The owner's job page never shows a worker's phone or email.
AC17. The owner's job page makes the same number of queries for 1 and for 3 applications.
AC18. The top link is "← My jobs" to `my_jobs` for the owner and "← Jobs" to the job list
      for a guest.
AC19. The worker page's title is "Worker profile".
AC20. `/jobs/<pk>/applications/` gives 404; "My jobs" has no "Applications" link.

## Decisions

D1. *Replaced by D15.* **A separate page per job, `/jobs/<pk>/applications/`** (mine,
    2026-10-20, also Claude's recommendation). On a phone it shows only one job's
    applications; #20 adds a link with the count ("quick links to … view applications"), #24
    puts its buttons on this page and comes back to it. Rejected: inside the "My jobs" cards
    as on the mockup (with #20's groups the page grows long and would need folding later); a
    block on the job page for the owner (a public page gets private parts, and #24 / #25 add
    more conditions to it). **Revisit when** employers have one job at a time and the extra
    tap annoys them.
D2. **The worker page only for an employer the worker applied to** (mine, 2026-10-20, also
    Claude's recommendation). The worker shows their data only to whom they wrote; one
    filter in the queryset. Rejected: every logged-in employer (walking `/workers/1`,
    `/workers/2`, … collects every worker's name and legal status); the full profile inside
    the application, no page (the "Link to each worker's profile" item changes and #38 / #39
    need the page anyway). **Revisit when** employers should look for workers themselves
    (search, invitations).
D3. **Every job status** (Claude's default, accepted): a cancelled or filled job's
    applications are still the employer's history, so the view uses the employer's own jobs,
    not `OwnOpenJobMixin`.
D4. **404, not 403, for another employer** (Claude's default, accepted, as Edit / Cancel in
    #16): the queryset holds only what this employer may see, so the page does not even tell
    that the job or the worker exists. Since D15 only the worker page; the job page is
    public anyway.
D5. **Newest first** (Claude's default, accepted): the employer opens the page to see what
    is new. #24 may sort by status.
D6. **The application card repeats the profile fields** the issue names (team, skills, legal
    status) plus the work permit, but not the languages (Claude's default, accepted): enough
    to choose on the list, the rest is one tap away on the profile. *The skills part was
    changed by D12.*
D7. **One query for the applications with their workers and profiles**
    (`select_related("worker__worker_profile")`, Claude's default, accepted). Skills are a
    PostgreSQL array in the profile row, so they need no extra query.
D8. *Replaced by D18.* **The link on "My jobs" for every job, without a count** (Claude's
    default, accepted): #20 adds the count and the groups.
D9. **The worker page shows no list of their applications** (Claude's default, accepted):
    the employer comes from the job page and goes back there with the browser's Back.
D10. **A worker gets 403 on the worker page, also for their own id** (Claude's default,
     accepted, `RoleRequiredMixin` with the employer role): their own page is
     `worker_profile`.
D11. **Applications look like the "My jobs" mockup** (mine, 2026-10-20, after seeing
     iteration 2): tinted boxes inside one card, each with an avatar. Rejected: the first
     layout (separate application cards). Since D15 the card is the job page's section.
D12. **Only the job's own skill on an application** (mine, 2026-10-20): a crew with 8 of the
     10 skills filled the card with badges, and the employer only asks "can they do this
     job?". `job.job_type` comes from the same `Skill` list as the worker's skills, so the
     template checks `job.job_type in profile.skills`. All skills stay on the worker page,
     which gives that page a use. Rejected: all skills (noise); the job's skill first plus
     "+5 more" (more code, little gain); "All skills" when all 10 are chosen (helps only
     that case); the line "No Demolition in skills" (I want the two cases to look the same,
     only colour and sign differ). **Revisit when** jobs can need several skills.
D13. **Initials: the first letter of the first and of the last word** (Claude's default,
     accepted, after I asked about one-word and five-word names): "Maria del Carmen García
     López" → "ML", not "MD"; "Mehmet" → "M". No picture: no upload and no Gravatar (it
     would send a hash of the worker's email to another server).
D14. **"Worker profile" as the worker page's title** (Claude's default, accepted): the card
     already shows the name, as "My profile" on the worker's own page.
D15. **The list on the job page, no separate page** (mine, 2026-10-25, after using both on
     the local server): the separate page with the applicants was not handy, and the job
     page showed the employer things they do not need, so I joined the two into one; I find
     that handier. `JobDetailView` loads the applications only for the owner, in one query
     (D7). Rejected: the separate page (D1); a short "Applications (N)" block with a button
     to it (Claude's recommendation: shorter job page, one list for #24). Cost: the job page
     grows with every application, and #24 puts Accept / Reject on the public job page's
     owner part. **Revisit when** jobs get many applications and the page gets long (fold
     the list, or bring the separate page back from `23-separate-applications-page`).
D16. **The owner sees the list instead of the employer card** (mine, 2026-10-25): the
     employer knows their own company. Everyone else keeps the card and never sees the list:
     a worker who applied must not see the other applicants.
D17. **"← My jobs" at the top for the owner** (Claude's default, accepted, 2026-10-25): the
     owner comes from "My jobs" and goes back there.
D18. **No "Applications" link on "My jobs"** (mine, 2026-10-25): the card's title already
     opens the job page with the list. #20 adds the number of applications.

## Differences from the mockup (docs/mockups/my-jobs.png)

| Mockup | App | Why |
|---|---|---|
| Applications inside the job's card on "My jobs" | on the job page, for its employer, instead of the employer card | D15, D16 |
| "Applications (3)" on "My jobs" | no count yet | #20 |
| "Edit · Cancel job" under the applications | the job page's "Edit" button, as in #19 | D15 |
| "★ 4,7 (9)", "new, no reviews" | not shown | #39 |
| "· from Ukrainian" | not shown | #33 |
| "Accept 2" / "Reject", "fills the job" hint, "Workers found 2 / 3" | not shown | #24 |
| "Crew of 2 · work permit ✓" on one line | "Crew of 2 · brings 2 workers", then the legal status and "Work permit confirmed" in words | the issue asks for the legal status too (D6); words translate better than "✓" |
| No skills on the card | the job's own skill: "✓ Demolition" (green) or "− Demolition" (grey) | the issue asks for skills; D12 |
