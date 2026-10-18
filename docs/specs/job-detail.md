# Spec: job detail page (#19)

Status: **agreed**. The student decided D1, D3 and D7 on 2026-10-18, before any tests; the
others are the defaults offered with them and accepted.

## Goal

A worker reads everything about one job before applying: what, where, when, for how much, who
hires, and the photos. Today the job list (#18) shows short cards that lead nowhere. The ticket
comes in two iterations:

1. **The page:** all job fields, the status, the employer, the address only for the owner, the
   "Apply" button, links to the page from the job list and "My jobs".
2. **Photos:** a carousel of the job's photos, or the hard-hat placeholder (#64, D1).

## Iteration 1: the page

### Requirements

R1. `/jobs/<pk>/` (URL name `job_detail`) shows one job. A job id that does not exist gives
    404.
R2. Everyone sees the page: guests, workers, employers (D1). A logged-in user without a role
    is still sent to the role choice first (`OnboardingMiddleware`, unchanged).
R3. Every job is shown, whatever its status (D1). The status is a badge next to the title:
    "Open" (green), "Filled", "Done", "Cancelled". An open job that has already started gets
    "Past" instead of "Open".
R4. The page shows: job type (title) and hourly rate; district · date · start–end time
    (hours); "Needs 3 workers" (only while it takes applications, D10); the description
    with its line breaks; the employer card (R6).
R5. The exact address is shown only to the job's own employer (D4). Everyone else sees the
    district and the line "The exact address is shown after the employer accepts you."
R6. Who hires: the title "Employer" (D10) and `accounts/_employer_profile_card.html`
    (company, contact person, trades) — no phone or email (#94 note, `docs/SECURITY.md`).
    An employer without a profile (possible only via the admin) shows the account's name.
R7. `Job.accepts_applications`: the job is open and has not started yet (the same rule as
    `JobQuerySet.upcoming()`, Munich time).
R8. Below the employer card, by who looks (D3, D5):
    - a worker, job accepts applications: an "Apply" button (POST to `job_apply`, R9);
    - a guest, job accepts applications: "Log in to apply", to the login page with
      `?next=` back to this job;
    - the job's own employer, job open: "Edit" (to `job_edit`);
    - anyone else, or a job that does not accept applications: nothing.
R9. `/jobs/<pk>/apply/` (URL name `job_apply`) is a stub until #22 (D3): only POST (GET gives
    405); workers only (guests go to login, employers get 403); an unknown job gives 404.
    It adds the message "Applying is not available yet." and redirects back to the job page.
R10. The job type on each job list card and on each "My jobs" card links to the job page
     (D6).
R11. A "← Jobs" link at the top goes back to the job list.
R12. The page makes a fixed number of database queries, whatever the job has: the employer
     and their profile come with the job (`select_related`).
R13. Every UI string is wrapped in `{% translate %}` / `gettext_lazy`.

### Out of scope

- The application form, its rules and `can_apply()`: #22. Showing the address after
  acceptance: #25. "1 of 3 workers found": #24.
- Translation of the description and "Show original": #32. Rating and reviews: #39.
- Language switcher "EN": #29. The comma in "16,50 €/h": M5.

### Acceptance criteria (→ tests)

AC1. `accepts_applications`: true for an open job tomorrow; false for an open job that has
     started, and for a cancelled job tomorrow (the clock is fixed in the test).
AC2. A guest, a worker and an employer get the page (200); `/jobs/99999/` gives 404.
AC3. The page shows type, rate, district, date, "08:00–14:00", hours, "Needs 2 workers",
     the description and the employer's display name and trades.
AC4. The address is on the page for the job's employer; not for a guest, a worker or another
     employer, who see the "shown after the employer accepts you" line instead.
AC5. A cancelled job shows "Cancelled"; an open job in the past shows "Past"; neither has
     "Apply".
AC6. A worker sees the "Apply" button on an open upcoming job; a guest sees "Log in to apply"
     with `next=` to the job; another employer sees neither; the owner sees "Edit".
AC7. POST to `job_apply` as a worker redirects to the job page with "Applying is not
     available yet."; GET gives 405; a guest is sent to login; an employer gets 403.
AC8. The job list card and the "My jobs" card link to `job_detail`.
AC9. A guest's page makes one database query: the job, its employer and the profile
     together.
AC10. The page has no phone number or email of the employer.

### Decisions (student, 2026-10-18)

D1. **Every job keeps its page; one that is not open shows its status** (the student: "if it
    disappears, it would be strange"). Links saved by workers, and from the applications of
    #22–#25, keep working. Everyone, guests included, sees it: the job list is public too
    (#18 D1), and the address stays hidden (D4). Rejected: 404 for jobs that are not open.
    **Revisit when** a job's page should vanish after some time (data minimisation, M7).
D2. **An open job that has started shows "Past", computed, not stored** (default): the
    status is not changed, as in the job list (#18 D2: a status change needs a paid cron
    job). `Job.accepts_applications` is the one rule for the badge and the "Apply" button.
    **Revisit when** a scheduled task closes started jobs.
D3. **"Apply" posts to a stub view that says "not available yet" and comes back to the
    page** (the student's idea: "stay on the page, a message appears"). #22 changes only the
    view's body; the URL, the button and the tests of who may post stay. Rejected: a disabled
    button with "Applying opens soon" (cannot be pressed); a JS message (thrown away in #22).
    **Revisit when** #22 starts: the stub becomes the real view.
D4. **Only the job's own employer sees the address** (default). There are no applications
    yet, so "hidden until an application is accepted" means "hidden from everyone else" now;
    #25 adds the accepted worker. Staff see it in the admin. Checked in the view
    (`show_address` in the context), not by the template comparing users.
    **Revisit when** #25 starts.
D5. **The "Apply" button is shown to every worker; `can_apply()` is checked by #22**
    (default): the rule belongs where an application is made. Guests get "Log in to apply".
D6. **The job type on the cards becomes the link** (default); the card stays as it is.
    Rejected: the whole card as a link (a link around a block of text reads badly in a screen
    reader).

D10. **"Needs 3 workers" only while the job takes applications** (found on the screenshots
     at 360 px, 2026-10-18, default accepted): on a cancelled job it read as if people were
     still wanted. Also from the screenshots, layout only: the employer card has the title
     "Employer" (its name was shown twice), the badges of jobs that are not open have a
     soft fill of the text colour, `bg-base-content/10` (a grey badge was invisible on the
     grey page; the student chose this fill over an outline, `badge-neutral` and
     `bg-base-300` on screenshots of both themes), and "07:00–15:00 (8 h)" wraps as a
     whole. **Revisit when** #24 shows "1 of 3 workers found".

### Differences from the mockup (docs/mockups/job-detail.png)

| Mockup | App | Why |
|---|---|---|
| "1 of 3 workers found" | "Needs 3 workers" | #24 (no applications yet) |
| "Translated from German by AI · Show original" | the original description | #32 |
| Initials "FH", "★ 4,8 (12 reviews)" | name, contact person, trades | #39 |
| Application form: message, "Workers I bring", "Send application" | "Apply" button to a stub | #22, D3 |
| "16,50 €/h" | "16.50 €/h" | M5 (decided in #16) |
| "‹" in the header | "← Jobs" above the title | no back button in `base.html` |

## Iteration 2: photos

### Requirements

R14. A job with photos shows them at the top of the page in a carousel (D7): one photo at a
     time, full width, 4 : 3, swiped on a phone (CSS scroll-snap, daisyUI `carousel`).
R15. Each photo carries its own "2 / 3" counter, written by the template, not by JS.
R16. With more than one photo, "‹" and "›" buttons scroll the carousel by one photo
     (a few lines of inline JS, `scrollBy`). With one photo there are no buttons.
R17. The carousel shows the stored photo (`image.url`, 1600 px), not the 300 px thumbnail.
R18. A job without photos shows `jobs/_photo_placeholder.html` in the same 4 : 3 box.
R19. The photos come in one more query, whatever their number (`prefetch_related`).

### Acceptance criteria (→ tests)

AC11. A job with 3 photos: all 3 `image.url`s are on the page, in upload order, with "1 / 3",
      "2 / 3", "3 / 3"; the buttons "Previous photo" / "Next photo" are there.
AC12. A job with 1 photo: "1 / 1", no buttons.
AC13. A job without photos: the "No photo" placeholder, no carousel.
AC14. A guest's page makes two queries, for 1 photo as for 3.

### Decisions (student, 2026-10-18)

D7. **A swipe carousel with "‹ ›" buttons** (the student wanted a carousel; option 3 of 4).
    Swiping is the browser's own (scroll-snap); the buttons are for a mouse on a laptop,
    where a scroll-snap carousel cannot be moved otherwise. Rejected: big photo + thumbnails
    without JS (not a carousel); scroll-snap without buttons (no way to scroll with a mouse);
    daisyUI's `#slide2` anchor buttons (they jump the whole page); a lightbox library (a new
    dependency). **Revisit when** the photos need zoom or full screen.
D8. **The counter is in each slide, not updated by JS** (default): no code to keep in sync.
D9. **The JS is tested in E2E only (#21)** (default): the Django test client does not run
    JS; the integration tests check that the buttons are there.
