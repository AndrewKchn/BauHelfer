# Spec: mark a job as done; cancel a filled job (#37)

Status: **agreed**. I decided D1, D2, D10 and D11 on 2026-11-12 (my criteria: easy to use,
simple code, and a review only of work that really happened, for #38). D3–D9, D12 and D13 are
Claude's defaults, which I accepted on 2026-11-12, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

A job ends today in "Filled", or in "Past" when not every place was taken, and stays there.
This ticket lets the employer mark it "done" once the work is over; "done" unlocks the
reviews of #38. It also closes two questions earlier tickets left here (#96 comments on this
issue): the edit and cancel pages refuse a job that is over, and a filled job can be
cancelled, with an email to every worker who loses their place.

Two iterations in one branch:

1. Mark as done (R1–R9, D1–D9).
2. Cancel a filled job, and the cancellation email (R10–R15, D10–D13).

### Out of scope

- Reviews and "Rate the employer": #38, #39.
- A reason the employer writes when cancelling, and a cancellation message in the chat: #35
  (D11).
- Rating a cancelled job, so a late cancellation shows in the employer's rating: #38 (D10).

## Requirements

### Iteration 1: mark as done

R1. `Job.can_mark_done` (a property): True only when the job is open or filled, at least one
    worker is accepted (`workers_found`), and the work is over: `ends_at` has passed, Munich
    time (D1, D2). Uses `accepted_workers` when the job was loaded with
    `with_workers_found()`, as `places_left`.
R2. `Job.mark_done()` in one transaction, the job row locked, as `Job.cancel()`: checks R1
    again on the locked row and sets the status "done". Raises `JobStateError`, and changes
    nothing, otherwise. The applications keep their statuses: the accepted ones stay
    "accepted" (#38 asks them who may review).
R3. `JobDoneView`, `POST /jobs/<pk>/done/`, employers only: only the logged-in employer's own
    jobs; another employer's job gives 404. A job for which `mark_done()` raises gives 404
    too, as `JobCancelView`. On success: the message "Job marked as done." and back to
    "My jobs". GET is not allowed (405).
R4. "My jobs": a job that `can_mark_done` shows a "Mark as done" button on its card (D3, D8);
    the browser asks "Mark this job as done? This cannot be undone." first (D4).
R5. "My jobs" loads the jobs with `with_workers_found()`, so the button costs no query per
    card.
R6. A done job is in the "Done" tab of "My jobs" (exists since #20). An open job that is over
    stays in "Past" (#26), now with the button when someone was accepted (D5).
R7. "My applications": an accepted application of a done job is in a new tab "Done", right
    after "Accepted", in the colour of the done jobs (`badge-secondary`) (D6).
R8. No email when a job is marked done (D7).
R9. Edit, cancel, adding and deleting a photo take only open jobs that are not over
    (`is_over`); one that is over gives 404 (D9).

### Iteration 2: cancel a filled job, the cancellation email

R10. `Job.cancel()` takes an open or a filled job (D10); the rest as before (#25): the job and
     its accepted applications "cancelled".
R11. The "Cancel job" link and page for the employer's open and filled jobs that are not over
     (R9); "Edit" and the photos stay for open ones only.
R12. A pending or "Job filled" application of a cancelled job is in the "Cancelled" tab of
     "My applications" (D13; pending ones are there since #26, D9).
R13. Cancelling a job emails every worker whose accepted application it cancelled; cancelling
     one accepted worker (#24) emails that worker (D10, D12). Through `send()` of #27: in the
     worker's language, not to an unconfirmed address or a worker who turned the emails off,
     a failed email never undoes the cancel.
R14. The email (D11), one template for both cases: subject "Cancelled: <job type>,
     <date>"; the body says who cancelled what ("The employer cancelled the job …" / "The
     employer cancelled your place on …"), that the worker has nothing to do, and links to
     "My applications".
R15. Every new string is wrapped for translation and translated into all 7 languages.

## Acceptance criteria (→ tests)

### Iteration 1

AC1. `can_mark_done`: True for a filled job a minute after `ends_at`; False a minute before.
     True for an open job with one accepted worker after `ends_at`; False for an open job
     with none. False for a done and a cancelled job. A night shift: False before the next
     morning's end, True after.
AC2. `mark_done()` sets "done" and leaves the applications as they were; on a job that
     cannot be marked done it raises and changes nothing. With the R5 annotation and without
     it, the same answer.
AC3. POST by the owner after the end: status "done", redirect to "My jobs", the message.
     Before the end: 404, still filled. Another employer: 404. A worker: 403 (as the other
     employer pages). GET: 405.
AC4. "My jobs": the button with its confirm text on a job that can be marked done; none on
     one that cannot (before the end, nobody accepted). A done job in the "Done" tab.
AC5. "My jobs" makes the same number of queries for 1 and for 3 jobs that can be marked
     done.
AC6. "My applications": an accepted application of a done job is in the "Done" tab, right
     after "Accepted".
AC7. Edit, cancel, add-photo and delete-photo of the owner's open job the day after it
     ends: 404; on its day they still work.

### Iteration 2

AC8. `Job.cancel()` on a filled job: the job and its accepted applications "cancelled", the
     "Job filled" ones unchanged. On a done or cancelled job it raises and changes nothing.
AC9. The owner's POST to cancel a filled job cancels it; the card of a filled job shows
     "Cancel job", not "Edit".
AC10. `Application.tab` of a pending and of a "Job filled" application of a cancelled job:
      "cancelled".
AC11. Cancelling a job with two accepted workers sends two emails, one each, in each
      worker's language; a worker with emails off gets none. Cancelling one worker sends
      one email. A failing mail backend: the cancel is saved, the error logged.
AC12. The email of a cancelled job and of a cancelled place: the subject, the right body
      line, the link to "My applications".

## Decisions

D1. **"Mark as done" only after the work is over** (mine, 2026-11-12; option C): from
    `ends_at` (start + hours), Munich time. Done unlocks the reviews of #38, and a review of
    work that has not happened yet makes no sense; the mockup says "finished". Rejected: from
    the work date (A, the issue's first text: before the work starts); from the start (B: the
    work is still going on). Cost: work that ends early waits until the planned end.
    **Revisit when** employers ask to close a job that ended early.
D2. **A filled job, or an open one with at least one accepted worker** (mine, 2026-11-12;
    option B): "found 2 of 3 and worked" is common, and those workers should get reviews too.
    Rejected: filled jobs only (A, the issue's first text: incomplete crews never get a
    review); any job that is over (C: "done" with nobody to rate). Changes the meaning of
    "Past" (my-applications.md D3): an open job that is over can have happened; it waits
    there for "Done".
D3. **The button only on the "My jobs" card** (Claude's default, accepted): as on the mockup;
    the job page stays as it is. **Revisit when** #38 shows the reviews on the job page.
D4. **The browser asks first** (Claude's default, accepted), as before Cancel and Reject: done
    cannot be undone and opens the reviews.
D5. **No new tab for jobs waiting for "Done"** (Claude's default, accepted): a filled job stays
    in "Filled", an open one with accepted workers in "Past", both with the button.
D6. **The worker gets a "Done" tab** (Claude's default, accepted): "Rate the employer" of #38
    goes there, as on the mockup of "My applications". After "Accepted": done is the next
    step of an accepted application.
D7. **No email when a job is done** (Claude's default, accepted): the worker has nothing to do
    until #38. **Revisit when** #38 asks the worker for a review.
D8. **The button: `btn-primary`, right of the card's links** (Claude's default, accepted), as
    on the mockup.
D9. **Edit, cancel and photos refuse a job that is over** (Claude's default, accepted; asked
    for in #96): #26 only hid the links (my-applications.md D6). `is_over`, the rule of the
    "Past" tab, so the links and the views agree.
D10. **A filled job can be cancelled, and every worker who loses their place gets an email**
     (mine, 2026-11-12; option C): a worker who does not know may come to the site for
     nothing, and it would hurt the ratings of #38. Rejected: leaving it (A, Claude's
     recommendation: two clicks round it, but no email); cancelling without an email (B).
     The chat message about it and rating a cancelled job are ideas for #35 and #38.
     Changes accept-reject.md D18.
D11. **A fixed text, without a reason** (mine, 2026-11-12; option a): two templates, no form.
     Rejected for now: a reason the employer writes (b: a form field, stored, translated
     by Claude); kept as an improvement for the chat, #35.
D12. **The same email when one accepted worker is cancelled** (Claude's default,
     accepted): for the worker it is the same event, and until now they were not told
     either.
D13. **Pending and "Job filled" applications of a cancelled job show as "Cancelled"**
     (Claude's default, accepted): nobody will answer them; pending ones since #26 (D9),
     "Job filled" ones now that a filled job can be cancelled. No email for them: they were
     never promised the work.

## Known limitations (→ docs/SECURITY.md)

- The app cannot know whether the work happened: an employer can mark done work that did not
  take place. #38's reviews would show it.
- A filled job whose work did not happen and was not cancelled before the day ended stays in
  "Filled" for ever: it can be neither marked done (no work) nor cancelled (over, D9).

## Differences from the mockups

| Mockup | App | Why |
|---|---|---|
| "My jobs": "Cleanup · Mon 12 Oct / 2 workers · finished" with "Mark as done" | the usual card (photo, summary, links) with the button; no "finished" line | D3, D8 |
| "My applications": "Done" badge on the card | a "Done" tab; "Rate the employer" with #38 | D6 |
