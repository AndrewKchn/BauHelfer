# Spec: ratings on profiles and applications (#39)

Status: **agreed**. I decided D1–D4 and D12 on 2026-11-16 (my criteria: reviews must not
mislead, nobody rates in revenge (reviews.md D3), a worker's name and data only for an
employer they applied to (#23, #25), features over polish); D9 is mine from #30. D5–D8, D10
and D11 are Claude's defaults, which I accepted on 2026-11-16, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

#38 stores the reviews; this ticket shows them. Everyone who decides about someone sees their
average rating, how many reviews it is from, which tags others ticked ("On time · 7 of 9")
and their latest reviews: the employer before accepting a worker, the worker before applying
to a job. Only reviews the other side may already see count (reviews.md D3). An employer gets
a public page of their own, as a worker has one for employers (#23).

Four iterations in one branch:

1. The average and the count: on the profile cards and in the applications list (R1–R6).
2. The tags and the latest reviews on the profiles (R7–R10).
3. The employer's page (R11–R13).
4. Translations into all 7 languages and the built screenshot of the worker profile.

### Out of scope

- A comment in the review: there is none (reviews.md D2).
- A page with all reviews: the latest 5 are shown (D5).
- The employer's other jobs on their page, and a chat with them: #35, later.
- Removing a review that breaks the rules: the admin panel, #45.

## Requirements

### Iteration 1: the average and the count

R1. `Review.objects.visible()`: the reviews the other side may see, with the same rule as
    `Review.is_visible` (reviews.md R6), as one database query: the application's review
    deadline has passed, or the application has a review by the other side (D2). A test
    checks that both give the same answer.
R2. `Review.objects.about(user)`: the reviews of `user` — on an application where `user` is
    the worker or the job's employer, written by someone else.
R3. One function gives a user's rating summary: the average (one decimal), the number of
    reviews and the tag counts, all over `visible().about(user)` (D2).
R4. The worker's profile card (own page and `/accounts/workers/<id>/`) gets the head of the
    mockup: initials, name, "Crew of 2 · Gewerbe" under it, and the rating "★ 4,7 (9
    reviews)" (D9, D10). With no visible review: "No reviews yet" (D7).
R5. The employer's profile card (own page and the job page) gets the same kind of head:
    initials, company or name, the rating (D10).
R6. The applications list on the owner's job page: "★ 4,7 (9)" or "No reviews yet" on a
    line under "2 workers" (next to it, it broke at 360 px); one query for the whole list,
    not one per application (D8).

### Iteration 2: the tags and the latest reviews

R7. Under the rating, the tags that at least one visible review has, most often first, as
    "On time · 7 of 9" (D1); a tag nobody ticked is not shown.
R8. "Reviews" on the worker's profile (own page and `/accounts/workers/<id>/`) and on the
    employer's own page: the latest 5 visible reviews, newest first (D5).
R9. One review: who wrote it (D3), "★ 4", its tags, and "<job type> · <job date>".
    - A review by an employer: the company, or the employer's name without one.
    - A review by a worker: "Worker", or "Crew of N" for a crew, never the name.
R10. Hidden reviews do not appear anywhere, also not on the rated person's own page (D2).

### Iteration 3: the employer's page

R11. `EmployerDetailView`, `GET /accounts/employers/<id>/`: the employer's card, the tag
     summary and the latest 5 reviews (D4). Open to everyone, guests too, as the job page
     (D11). An id that is not an employer with a profile gives 404.
R12. The job page's employer card: the rating and a link "12 reviews →" to that page; with
     no review, "No reviews yet" and no link (D4).
R13. The employer's own page shows the same reviews as the public page, plus the private
     parts it has now (contacts, email settings, "Edit").

## Decisions

D1. **Tags as "On time · 7 of 9"** (mine, 2026-11-16; option A): the tag together with the
    number of reviews it is counted from, so an unticked tag does not read as the
    opposite. Rejected: a percentage (B: "100%" from one review sounds bigger than it is);
    only tags of at least half the reviews (C: a rare tag disappears, the rule needs
    explaining); the top 3 without numbers (D: hides whether it is one review or twenty).
    **Revisit when** profiles have so many reviews that "of 120" means little.
D2. **Only visible reviews count, everywhere** (mine, 2026-11-16; option A): the average,
    the count, the tags and the list. Otherwise a hidden 1★ shows as a drop of the average,
    and the rated person knows what the other side gave before rating back (reviews.md D3).
    Rejected: hidden only from the rated person (B: different numbers on different pages,
    and an employer who rated can still work the hidden one out). Counted in the database
    (R1), not with `is_visible` one review at a time. **Revisit when** the 14 days of
    reviews.md D3 change.
D3. **The author's name only over an employer's review** (mine, 2026-11-16; option A): the
    employer's card is public on the job page, so a worker's name over their review of an
    employer would tell any guest where they worked. Rejected: the name for everyone (B);
    first name and initial (C: still public, a rare name is easy to find). An employer's
    name is public on their jobs anyway. **Revisit when** workers want to sign their
    reviews.
D4. **A public page for the employer** (mine, 2026-11-16; option C): a worker decides
    whether to go to work by the employer's latest reviews: an average of 4,7 from twelve
    hides that the last two were 1★ without "Paid in full and on time". The same pattern as
    the worker's page of #23. Rejected: only the summary in the job page's card (A: the
    trend is not visible, and only the employer would see their own reviews).
    Changes the issue's "Done when…" (a new item). **Revisit when** employers ask to hide
    the page.
D5. **The latest 5 reviews, no page with all** (Claude's default, accepted): the newest say most; a
    page with all needs pagination.
D6. **The average with one decimal, in the page's language** (Claude's default, accepted): "4,7" in
    German, "4.7" in English, with `floatformat:1`, as the mockup.
D7. **"No reviews yet" for nobody's reviews** (Claude's default, accepted): the mockup has "new, no
    reviews"; "new" is not true of a worker who has been here a year but was never rated.
D8. **The applications list asks for all ratings at once** (Claude's default, accepted): one query
    grouped by worker for the whole list, so ten applications are not ten queries.
D9. **The worker's card as on the mockup** (mine, 2026-11-07, in #30): the head with
    initials, name and "Crew of 2 · Gewerbe" next to the rating; small uppercase labels;
    the languages as text separated by commas; a green "✓ Confirmed: allowed to work in
    Germany" instead of the "Work permit" row (when not confirmed: "Not confirmed" in
    grey). The name and legal status move into the head. Its wording: D12.
D10. **One star and a number, not five stars** (Claude's default, accepted): "★ 4,7 (9 reviews)"
     everywhere, as on the job page and "My jobs" mockups; five stars with a half one need
     more code and say the same. Differs from the worker profile mockup.
D11. **The employer's page is open to everyone** (Claude's default, accepted): it shows the same as
     the card on the public job page, plus reviews without workers' names (D3).
D12. **"✓ Allowed to work in Germany (confirmed by the worker)"** (mine, 2026-11-16;
     option B): the green line of D9, but it says who confirmed it. The site checks no
     document; "Confirmed: allowed to work in Germany" (A, the mockup) reads as if
     BauHelfer had checked, and an employer might not ask for the residence permit.
     Without a confirmation: "Work permit not confirmed" in grey, the words of the
     applications list. Rejected: the mockup's words (A); the old "Work permit" row (C).
     Keeps work-permit.md D6 (no date for employers). On the worker's own page the old
     "Allowed to work in Germany — confirmed on <date>." repeated the line; it is now
     "You confirmed it on <date>." right under it (mine, 2026-11-16). **Revisit when** the site checks
     documents itself.

## Open questions

- None yet.

## Known limitations (→ docs/SECURITY.md)

- A new review shows up only when both sides have rated, or 14 days after "done" (D2): the
  rating lags behind.
- The employer's page is public (D11): anyone can see a company's latest ratings, with the
  job types and dates of its done jobs.

## Differences from the mockups

| Mockup | App | Why |
|---|---|---|
| Worker profile: five stars "★★★★★ 4,7 (9 reviews)" | "★ 4,7 (9 reviews)" | D10 |
| Worker profile: a review with "Fast and reliable, we will book them again." | stars and tags, no comment | reviews.md D2 |
| Worker profile: "Rate the work on 12 Oct" form | none: the review page of #38 | reviews.md D4 |
| Job detail: employer card "Window fitter · ★ 4,8 (12 reviews)" | the card with the trades, the rating and a link to the employer's page | D4 |
| My jobs: "new, no reviews" | "No reviews yet" | D7 |
| My jobs: "Crew of 2 · ★ 4,7 (9) · work permit ✓" | "2 workers", "★ 4,7 (9)" on the next line; the permit only when missing, as now | R6, applications-list.md |
| Worker profile: "✓ Confirmed: allowed to work in Germany" | "✓ Allowed to work in Germany (confirmed by the worker)" | D12 |
| — | an employer's page with the latest reviews | D4 |
