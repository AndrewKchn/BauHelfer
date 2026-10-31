# Spec: contacts are revealed to both sides after acceptance (#25)

Status: **agreed**. I decided D1–D4 on 2026-10-29 and 2026-10-30 (my criterion: as little
personal data on the site as possible, but the two sides must be able to reach each other on
the day of the job); D5–D10 are Claude's defaults, which I accepted on 2026-10-31, before any
tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

Since #24 the employer can accept a worker, but neither side can reach the other: the job's
exact address is shown only to its employer, and nobody sees a phone. This ticket shows an
accepted worker the job's address and the employer's phone, and the employer the worker's
phone, from the acceptance until the day of the job is over. A cancelled application shows
nothing, and cancelling a job now cancels its accepted applications.

One iteration.

### Out of scope

- The "My applications" page with the contact box of the mockup: #26 (it reuses R1).
- Emails about the decision: #27. The chat: #35 (D1).
- Pending and "Job filled" applications of a cancelled job: stay as they are (D9).

## Requirements

R1. `Application.shows_contacts` (a property): True only when the application is accepted and
    the day the job ends has not passed yet, in Munich time (D2, D4). A job that runs past
    midnight ends the next day (`Job.end_time`), so its contacts stay until that day is over.
R2. `Job.cancel()` in one transaction, the job row locked (as `Application._lock`,
    accept-reject.md D6): only an open job; status "cancelled" and every accepted
    application of it "cancelled" (D3). Pending, closed and rejected ones stay as they are
    (D9). Raises an error, and changes nothing, unless the job is open.
    `JobCancelView` calls it instead of setting the status itself.
R3. The job page, for a worker whose application `shows_contacts`:
    - the address line shows the exact address (`show_address`, job-detail.md R5);
    - the "You applied" card gets a "Contact" part: the employer's phone, or "not given"
      (D1, D7). The contact person's name is already on the employer card below.
R4. The job page, for the owner: an application that `shows_contacts` shows the worker's phone,
    or "not given" (D6). Other applications show no phone.
R5. The email of either side is never shown on any page (D1).
R6. The "The exact address is shown after the employer accepts you." line only for someone
    who can still be accepted: a guest, a worker without an application or with a pending
    or "Job filled" one, or another employer (D8). A rejected, cancelled or past accepted
    application gets no address line.
R7. Under the phone field on both profile forms: "Optional. Shown only to the people you
    work with, until the day of the job is over." (D10).
R8. Every new string is wrapped for translation.

## Acceptance criteria (→ tests)

AC1. `shows_contacts` is True for an accepted application of a job today or later; False for
     pending, rejected, closed and cancelled ones; False for an accepted one the day after
     the job; True the next morning for a job that ends after midnight, False the day after.
AC2. `Job.cancel()` on an open job: the job and its accepted applications "cancelled";
     pending, closed and rejected ones unchanged. On a filled, done or cancelled job it
     raises the error and changes nothing.
AC3. The owner's POST to cancel the job cancels its accepted applications (integration).
AC4. Job page, worker: with a pending application, neither the employer's phone nor the
     address is in the HTML; with an accepted one both are; with a cancelled one and the day
     after the job neither. The employer's email is never in it.
AC5. Job page, worker with an accepted application, employer without a phone: "not given".
AC6. Job page, owner: an accepted application of a job today shows the worker's phone; a
     pending, rejected, cancelled one and an accepted one the day after the job do not.
     The worker's email is never in it.
AC7. A guest and another worker see neither phone nor address (already true; checked again
     because this ticket changes the rule).
AC8. The address hint line: shown to a guest and a worker with a pending application; not to
     a worker with a rejected or cancelled application.
AC9. Both profile forms show the phone hint (R7).

## Decisions

D1. **The phone only, and only if the person gave one; never the email** (mine, 2026-10-30;
    option C). The phone is optional on the profile, so leaving it empty means "do not
    share". Rejected: phone and email for everyone accepted (A: more data than needed, the
    email was given to sign up, not to be passed on); nothing but the address, everything
    else through the chat (B, my first idea: there is no chat before #35, and the chat of
    #35 is seen only while the page is open, so a worker who is late at 06:50 could not
    reach anyone). **Revisit when** #35 brings the chat: if it can notify, the phone can go.
D2. **A cancelled application shows no contacts** (mine, 2026-10-29): after the employer took
    the worker off, neither side needs them.
D3. **Cancelling a job cancels its accepted applications** (mine, 2026-10-29): otherwise they
    stay "accepted" on a cancelled job and keep showing contacts. This changes
    accept-reject.md D18 ("stays as it is"). Only open jobs can be cancelled (job-form.md
    D7), so a filled job cannot lose its workers this way.
D4. **A past job hides the contacts from the day after it ends, computed, without changing the
    status** (mine, 2026-10-30): on the day itself a late worker must still be able to call.
    "Cancelled" for work that was done would be untrue, and changing a status at a set time
    needs a scheduled task, which the free Render plan does not have. Rejected: hiding when
    the job starts (the "Past" badge: the call at 06:50 fails); N days after (a week of
    data shown for nothing). **Revisit when** #37 adds "done", or a question about payment
    the day after needs the phone (the chat of #35 may answer it).
D5. **One rule in one place: `Application.shows_contacts`** (Claude's default, accepted):
    the job page and #26 ask the same property, and the unit tests check it without HTTP.
    The view decides `show_address`, not the template (job-detail.md D4).
D6. **The employer sees the phone only in the application on the job page** (Claude's
    default, accepted): not on the worker page (`workers/<id>/`), so there is one place to
    check.
D7. **The worker's "Contact" part sits in the "You applied" card** (Claude's default,
    accepted): where the worker already looks for their status. The address stays in its
    own line at the top, as for the owner, so it is not shown twice.
D8. **No "shown after the employer accepts you" for someone who will not be accepted**
    (Claude's default, accepted): a rejected or cancelled worker would read a promise that
    cannot come true.
D9. **Pending applications of a cancelled job are not touched** (Claude's default,
    accepted): they show no contacts anyway; how a worker sees them is #26's question.
D10. **The phone hint is set in the form, not on the model** (Claude's default, accepted):
     a model's help text is part of the migration, the form's is not, and only the profile
     forms show it.

## Known limitations (→ docs/SECURITY.md)

- A phone that was seen cannot be taken back: hiding it stops the site from showing it, it
  does not make anyone forget it.
- Someone who gave a phone before this ticket did not see the hint; the phone was not shown
  to anyone until now.

## Differences from the mockups

| Mockup | App | Why |
|---|---|---|
| "My applications": a "Contact" box with name, phone and address | on the job page: the address line at the top, the phone in "You applied"; the box itself comes with #26 | D7, out of scope |
| "My applications": "Open chat" | none | #35 |
