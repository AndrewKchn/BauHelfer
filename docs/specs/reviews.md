# Spec: reviews in both directions (#38)

Status: **agreed**. I decided D1–D5 on 2026-11-12 (my criteria: easy to use, simple code,
and honest reviews: in #37 I wrote that reviews are the only check that the work happened).
D6–D14 are Claude's defaults, which I accepted on 2026-11-12, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

After a job is done (#37), its employer and each accepted worker rate each other: 1–5 stars
and, optionally, a few positive tags such as "On time" or "Paid in full and on time". A
review stays hidden until the other side has rated too, or until the 14 days for reviews
are over, so nobody rates in revenge. This ticket stores the reviews; #39 shows them on the
profiles and the job page.

Two iterations in one branch:

1. The review and its page (R1–R9, D1–D4, D6–D13).
2. The "Rate" buttons and the email when a job is done (R10–R14, D5, D14).

### Out of scope

- Showing the average rating, the tags and the reviews: #39 (and how to count the tags, see
  "Open questions").
- Rating a cancelled job (D1): only done jobs are rated.
- Removing a review that breaks the rules: the admin panel, #45.

## Requirements

### Iteration 1: the review and its page

R1. A new app `reviews` (as in the plan) with the model `Review`: `application` (the accepted
    application the review is about; deleted with it), `author` (the user who wrote it),
    `rating` (1–5), `tags` (a list of tag values, may be empty), `created_at`. One review per
    author and application: a unique constraint in the database, not only in the form
    (D8). The rating 1–5 is checked by the database too.
R2. Two fixed tag lists, `TextChoices` like `Skill`, so the .po files translate them (D2):
    - about a worker (`WorkerTag`): On time, Careful work, Hard-working, Left the site clean,
      Followed safety rules;
    - about an employer (`EmployerTag`): Paid in full and on time, Job as described, Safe
      workplace, Clear instructions, Respectful.
    A review has only tags of its own list: the worker's review of the employer only
    `EmployerTag`, the employer's review of the worker only `WorkerTag`.
R3. `Job.done_at`: when the job was marked done; set by `mark_done()` in the same save
    (D9). Empty for every other job.
R4. `Application.review_deadline`: `done_at` + 14 days (D3); None when the job is not done.
R5. `Application.can_review(user)`: True only when the application is accepted, its job is
    done, the deadline has not passed, `user` is the application's worker or the job's
    employer, and `user` has not reviewed this application yet.
R6. `Review.is_visible`: True when the other side has reviewed the same application too, or
    when the application's review deadline has passed (D3). Computed when read, no
    scheduled job. #39 uses it; in this ticket only the tests read it.
R7. `ReviewCreateView`, `GET` and `POST /applications/<pk>/review/` (D4), logged in only:
    an application where the user is neither the worker nor the employer gives 404, and so
    does one where `can_review` is false (D10). A guest goes to the login page.
R8. The page: who and what is rated ("Rate <name> · <job type>, <date>"), five stars (one
    choice, required), the tags of the right list as checkboxes under "What went well?
    (optional)", the hint "Your review will be shown when <name> rates you too, or on
    <deadline date>. It cannot be changed." (D3, D6), and "Publish review". After it: the
    message "Review published." and back: the worker to "My applications", "Done" tab; the
    employer to the job page (D4).
R9. Two quick POSTs (two tabs) save one review: the second gets 404, not an error 500 (D8).

### Iteration 2: the buttons and the email

R10. "My applications", "Done" tab: a card that `can_review` shows "Rate the employer"
     (`btn-primary`), as on the mockup; one already reviewed by the worker shows "Rated ★4"
     instead; after the deadline neither (D11).
R11. The job page, the owner's list of accepted workers of a done job: "Rate" next to each
     worker that `can_review`, "Rated ★4" after it (D4, D11).
R12. Both pages ask no extra query per card or per worker for the buttons (the reviews
     are loaded with the applications).
R13. `mark_done()`'s view emails every accepted worker of the job (D5): subject
     "Rate the employer: <job type>, <date>"; the body says the employer marked the job
     done, that the worker can rate them until <deadline date>, and links to the review
     page. Through `send()` of #27: in the worker's language, not to an unconfirmed address
     or a worker who turned the emails off; a failed email never undoes "done".
R14. Every new string is wrapped for translation and translated into all 7 languages (the
     tags included).

## Acceptance criteria (→ tests)

### Iteration 1

AC1. `Review`: a second review by the same author on the same application raises
     `IntegrityError`; the worker's and the employer's review of one application can both
     be saved. A rating 0 or 6 is refused by the database.
AC2. `mark_done()` sets `done_at` to now; `cancel()` does not.
AC3. `can_review`: True for the worker and for the employer of an accepted application of
     a done job; False for a stranger, for another worker of the same job, for a pending
     or cancelled application, for a job that is filled but not done, a minute after the
     deadline, and after the user's own review.
AC4. `is_visible`: False with one side only; True when both sides reviewed; True with one
     side a minute after the deadline.
AC5. GET by the worker: the employer's tags, not the worker's; by the employer: the
     worker's tags. A stranger, and a user whose `can_review` is false: 404. A guest: the
     login page.
AC6. POST by the worker with 4 stars and two tags: one review saved with them, the
     message, redirect to "My applications". By the employer: redirect to the job page.
     Without stars: the form again, nothing saved. A tag of the other list: refused.
AC7. A second POST by the same user: 404, still one review.

### Iteration 2

AC8. "My applications": "Rate the employer" on a done card the worker can review;
     "Rated ★4" after the review; nothing after the deadline.
AC9. The job page: "Rate" next to an accepted worker of the owner's done job, "Rated ★4"
     after it; none on a filled job that is not done.
AC10. Same number of queries for 1 and for 3 cards / workers with the buttons.
AC11. Marking a job with two accepted workers done sends two emails, in each worker's
      language, with the link to each one's review page; a worker with emails off gets
      none. A failing mail backend: the job is still done, the error logged.

## Decisions

D1. **Only a done job is rated** (mine, 2026-11-12; option A): as in the issue. Rejected:
    letting a worker rate an employer who cancelled less than 24 hours before the start
    (B), which I liked more but did not do for lack of time: it needs a `cancelled_at`, a
    one-way review and, to be fair, the same for a worker who withdraws an accepted
    application late; rating every cancelled place (C) punishes an employer who cancels a
    week ahead. **Revisit when** there is time after M7, or late cancellations become a
    real problem: option B.
D2. **One star rating plus optional positive tags, no comment** (mine, 2026-11-12; option
    4): a review takes two clicks; tags are translated by gettext like the rest of the
    page, so no AI translation and no moderation of free text. Positive tags only: a
    negative one ("Did not pay") is a public charge nobody can check; the stars say what
    went wrong. Five tags per side (R2). Rejected: stars only (1: a 3★ says nothing about
    why); a comment only the rated person sees (2); a public comment as on the mockup (3,
    Claude's recommendation: needs AI translation and moderation in #39); stars per tag (like
    Booking: slow to fill in on a phone). Changes the issue text ("with a short comment").
    **Revisit when** users ask to explain a low rating in their own words.
D3. **Hidden until both sides rated or 14 days after "done"** (mine, 2026-11-12; option
    B), as on Airbnb: nobody sees the other's rating before giving their own, so no rating
    in revenge. After 14 days the form closes; an old review says little. Rejected: shown at
    once (A). **Revisit when** 14 days turn out too short or too long.
D4. **One review page for both sides, per application** (mine, 2026-11-12; option A):
    `/applications/<id>/review/`, reached from "Rate the employer" on the worker's "Done"
    card and from "Rate" next to each accepted worker on the employer's job page. One view;
    always clear which job is rated, also when a worker worked for the same employer twice.
    Rejected: the form in the worker's profile, as on the mockup (B: two places with a form,
    and the profile would need to know which job).
D5. **An email to every accepted worker when the job is done** (mine, 2026-11-12; option
    B): a worker who does not open the site would miss the 14 days, and reviews of
    employers would be few. The employer marked the job done themselves and sees the
    buttons; no email to the employer. Rejected: no email (A). Changes job-done.md D7.
D6. **A review cannot be changed or deleted by its author** (Claude's default, accepted): simpler,
    and a review that can be rewritten after seeing the other one undoes D3.
D7. **A crew's application gets one review** (Claude's default, accepted): an application with 2
    workers is one account (`team_size`, plan), so one rating for the crew.
D8. **One review per side also in the database** (Claude's default, accepted): the unique constraint
    of R1 holds even when two tabs post at the same moment; the view turns the clash into
    404 (R9).
D9. **`Job.done_at`, a new field** (Claude's default, accepted): the 14 days count from "done", not
    from the end of the work; an employer who marks it done on day 13 would otherwise leave
    the workers one day. Jobs marked done before this ticket have none and get no review
    (only test data so far).
D10. **404 for a review that is not allowed** (Claude's default, accepted), as the other pages of
     jobs: a stranger does not learn that the application exists.
D11. **"Rated ★4" instead of the button after a review** (Claude's default, accepted): the author sees
     their own rating, also while it is hidden from the other side; nothing after the
     deadline.
D12. **The stars are daisyUI's `rating`: five radio buttons** (Claude's default, accepted): no
     JavaScript, works with the keyboard, looks like the mockup.
D13. **Reviews in a new app `reviews`** (Claude's default, accepted), as planned in `docs/PLAN.md`.
D14. **The email is sent by the view, after the save** (Claude's default, accepted), as the
     cancellation email of #37.

## Open questions

- For #39: how to show the tags. "On time ×7" may mislead: an unticked tag does not mean
  the opposite. Options: "×7 of 9", a percentage, a tag shown only when at least half of
  the reviews have it.

## Known limitations (→ docs/SECURITY.md)

- A late cancellation, by either side, leaves no trace in the ratings (D1).
- The app cannot know whether the work happened: an employer can mark done work that did
  not take place (#37). Its workers' reviews are the only check, and only if they write one.
- Two users who know each other can give each other 5★ for work that did not happen; one
  account per email address makes it a little harder, nothing more.

## Differences from the mockups

| Mockup | App | Why |
|---|---|---|
| Worker profile: "Rate the work on 12 Oct" form with a comment | a separate review page with stars and tags, no comment | D2, D4 |
| Worker profile: average rating and the "Reviews" list | not shown until #39 | out of scope |
| My applications: "★ Rate the employer" in orange | "Rate the employer", `btn-primary` as the other card buttons; "Rated ★4" after | R10, D11 |
