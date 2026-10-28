# Spec: the employer dashboard "My jobs" (#20)

Status: **agreed**. I decided D1–D4 on 2026-10-28 (my criteria: easy to use on a phone,
simple code, the mockup is only a draft), and D6, D7 and D9 the same day after seeing an
experiment of the page at 360 px in both themes; D5, D8 and D10–D15 are Claude's defaults,
which I accepted the same day, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

Since #16 "My jobs" is a plain list of the employer's jobs with "Edit · Cancel job". This
ticket turns it into the employer's dashboard: the jobs grouped by status in swipeable
groups, each card with its photo, address and number of applications, and the employer
lands on it after logging in.

Two iterations in one branch and one PR:

1. **The dashboard:** groups by status, the application count, photo and address.
2. **After login:** an employer lands on "My jobs".

### Out of scope

- The applications themselves: on the job page since #23 (applications-list.md D15).
- Accept / reject and the "Workers found 2 / 3" bar: #24. "Mark as done": #37.
- The status colours of D7 on the job page (job_detail.html still shows Filled, Done and
  Cancelled in grey): D8.

## Iteration 1: the dashboard

### Requirements

R1. "My jobs" (`/jobs/mine/`, `my_jobs`) still lists only the logged-in employer's own jobs,
    every status (job-form.md R14); guests go to login, workers get 403 (unchanged).
R2. The jobs are grouped by status in the order Open, Filled, Done, Cancelled (the order of
    `Job.Status`); inside a group soonest first, as before (D5). A status without jobs has no
    group (D10).
R3. Above the groups one badge per group: the status and its number of jobs, "Open 3" (D2,
    D6). The groups lie side by side in a strip that is swiped sideways (CSS scroll-snap,
    as the photos on the job page, job-detail.md D7); a tap on a badge moves to its group.
    The badge of the group on screen is filled with its status colour, the others are
    outlined (D7). On load the first group is shown (D11).
R4. The badges share one line at 360 px; if they do not fit (longer translations, M5), the
    line scrolls sideways and does not wrap (D12).
R5. Each card: the photo square of the job list (the first photo with "3 photos", or the
    hard-hat placeholder, job-photos.md R29); job type, and the date on a line of its own
    below (D9); start time · hours · workers · rate; the address, then the district below
    it (D3). No status badge on the card: the group says it (D13).
R6. Under it, on the card's full width: "3 applications", a link to the job page at its list
    of applications (`#applications`), or "No applications yet" as plain text (D14); then,
    for open jobs only, "Edit · Cancel job" as before (job-form.md D7).
R7. The number counts all the job's applications, whatever their status (D15).
R8. The page needs the same number of database queries for 1 job as for 10: the count comes
    with the jobs (`annotate(Count("applications"))`), the photos in one more query
    (`prefetch_related("photos")`).
R9. The address is shown only here, on the employer's own page; the job list and the job
    page keep their rules (job-list.md R7, job-detail.md R5).
R10. Every new string is wrapped for translation.

### Acceptance criteria

AC1. An employer with an open, a filled, a done and a cancelled job sees four badges in the
     order "Open 1", "Filled 1", "Done 1", "Cancelled 1", and each job inside its own group.
AC2. An employer with only open jobs sees only the "Open" badge.
AC3. A job with 3 applications shows a link "3 applications" to `job_detail` + `#applications`;
     one with 1 application "1 application"; one without "No applications yet" and no link.
AC4. Another employer's applications are not counted, and another employer's jobs are not
     listed (R1).
AC5. The card shows the job's address and district, and the first photo's thumbnail (or the
     placeholder).
AC6. "Edit" and "Cancel job" only on open jobs (unchanged).
AC7. The number of queries is the same with 1 and with 3 jobs that have photos and
     applications.
AC8. E2E (#28, the M4 test ticket, not here): a swipe and a tap on a badge change the group and
     the filled badge; the page fits 360 px.

## Iteration 2: after login

### Requirements

R11. After logging in, an employer lands on "My jobs"; a worker, and a user without a role
     (then sent on to the role choice by `OnboardingMiddleware`), land on the home page as
     before (D4).
R12. A `?next=` address still wins: an employer sent to login from another page goes back
     there (Django's `LoginView`, unchanged).
R13. A logged-in employer who opens the login page goes to "My jobs" too
     (`redirect_authenticated_user`, the same method).

### Acceptance criteria

AC9. An employer logs in from the login page → redirected to `my_jobs`.
AC10. A worker logs in → redirected to `home`.
AC11. An employer logs in with `?next=/jobs/new/` → redirected to `/jobs/new/`.

## Decisions

D1. **Groups as swipeable tabs, not sections one under another** (mine, 2026-10-28): on a
    phone I see one group at a time and change it with a swipe. Three ways compared: links
    `?status=open` with a reload (no swipe), a scroll-snap strip (chosen, Claude's
    recommendation: the swipe is the browser's own scrolling and works without JavaScript;
    about 20 lines of JS only make a tap smooth and keep the badge and the height in step),
    a JavaScript swipe gesture that reloads the page (a reload per swipe, more JS). Cost: all
    groups are on the page at once, and the JS is checked only by E2E tests. **Revisit when**
    an employer has so many jobs that loading every group at once is slow (then links with
    `?status=` and pagination).
D2. **Badges instead of tabs** (mine, 2026-10-28, after seeing the experiment with daisyUI
    tabs): the badges carry the status colour, so the active group is seen at once.
D3. **The address and the district** (mine, 2026-10-28): the employer recognises their own
    job by its address (two jobs can be in the same district). I first chose the district
    only, then changed it: only the employer sees this page, so the address is safe here
    (R9). Rejected: the district only (#16); the address instead of the district.
D4. **An employer lands on "My jobs" after login** (mine, 2026-10-28, my idea from #23): I
    care about my own jobs first. A subclass of Django's `LoginView` picks the page by role
    in `get_default_redirect_url()`, so `?next=` still wins. Added to the issue's "Done
    when…" the same day.
D5. **Soonest first in every group** (Claude's default, accepted), as before. **Revisit
    when** the Done group gets long and the newest done job should be on top.
D6. **The number of jobs on each badge** (Claude's default, accepted): the employer sees how
    many jobs wait in each group without swiping.
D7. **Status colours of the active badge** (mine, 2026-10-28; colours Claude's default,
    accepted): Open green (`success`, as everywhere), Filled blue (`info`), Done slate
    (`secondary`), Cancelled red (`error`, as "Cancel job"). Done was `neutral` first, but in
    the dark theme it almost disappeared on the page.
D8. **The job page keeps its grey badges for now** (mine, 2026-10-28): an employer who opens a
    filled job from its group sees it blue here and grey on the job page. Rare enough to
    leave (features before polish); recorded for later in "Docs sync — M4" (#96). **Revisit
    when** #24 makes filled jobs common, or in the M8 polish.
D9. **The date on a line of its own** (mine, 2026-10-28, after seeing the experiment): next to
    a long job type it broke in the middle ("Fri 30 / Oct"), and gluing it whole still left
    a line starting with "·". The card is one line taller, and the same in every card.
    Shared `_job_summary.html`, so the cancel page changes too.
D10. **No badge for an empty status** (Claude's default, accepted): nothing to swipe through.
D11. **The first group is shown on load** (Claude's default, accepted): Open if there are open
     jobs, the next one if not.
D12. **The badge line scrolls instead of wrapping** (Claude's default, accepted): two lines of
     badges pushed the cards down. To fit 360 px the badges are a bit narrower (`px-2`,
     `font-medium`, 6 px gaps): 19 px to spare in English.
D13. **No status badge on the card** (Claude's default, accepted): the filled badge above says
     it, and the details get the card's full width.
D14. **"No applications yet" without a link** (Claude's default, accepted): there is nothing
     to look at; the job type still links to the job page.
D15. **All applications counted** (Claude's default, accepted): until #24 they are all
     pending. **Revisit in** #24: maybe "3 applications · 1 new".
D16. **The photo square is shared** (Claude's default, accepted): moved out of
     `_job_card.html` into `_job_thumbnail.html`, so the job list and "My jobs" show it with
     the same code.

## Differences from the mockup (docs/mockups/my-jobs.png)

| Mockup | App | Why |
|---|---|---|
| One list, no groups | swipeable groups with status badges | the issue asks for groups; D1, D2 |
| Status badge on the card | none; the badge above | D13 |
| "Demolition · Thu 22 Oct" on one line | the date on the line below | D9 |
| No photo on the card | the photo square of the job list | my idea from #23 |
| The district | the address, then the district | D3 |
| "Applications (3)" with the list in the card | "3 applications", a link to the job page | applications-list.md D15 |
| "Workers found 2 / 3", "Mark as done" | not shown | #24, #37 |
