# Spec: email notifications (#27)

Status: **agreed**. I decided D1–D5 on 2026-11-01 (my criterion: the emails must really
arrive in production). D6–D12 are Claude's defaults, which I accepted on 2026-11-01, before
any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted.

## Goal

A worker learns that they were accepted only if they open "My applications"; an employer
sees a new application only on the job page. This ticket sends three emails: a new
application to the employer, "accepted" and "rejected" to the worker. Each user can turn
them off. In production they go out through Brevo, which also makes the password reset
email work there: until now it was only printed to the Render logs.

Three iterations in one branch and one PR:

1. The three emails, in the recipient's language.
2. The "Email notifications" checkbox and the link to it in every email.
3. Real sending in production through Brevo's HTTP API.

### Out of scope

- Emails when a job is filled, an accepted worker is cancelled or a worker withdraws (D6).
- HTML emails (D7).
- One-click unsubscribe without logging in (D4).
- Email verification at signup: #81.
- The translations themselves: M5 (#30). This ticket only renders each email in the
  recipient's language, so the translations will apply without code changes.

## Iteration 1: the three emails

### Requirements

R1. `jobs/notifications.py` has the functions that send them; the views call them (D5):
    - `notify_new_application(request, application)` — from `JobApplyView`, after
      `form.save()`;
    - `notify_decision(request, application)` — from `ApplicationAcceptView` and
      `ApplicationRejectView`, after `accept()` / `reject()` returned. Accepted or rejected
      is read from `application.status`.
    The views call them only on success: a form with errors, a second click
    (`ApplicationStateError`) and every refused case send nothing.
R2. Recipients: a new application → the job's employer; accepted / rejected → the worker.
R3. Subject and body are rendered with the recipient's language active
    (`translation.override(recipient.preferred_language)`), not the language of the person
    who clicked (D8). The request's own language is the same afterwards.
R4. Plain-text templates in `templates/emails/`, as the password reset email (D7):
    `<kind>_subject.txt` and `<kind>_body.txt` for `new_application`, `application_accepted`,
    `application_rejected`. Every string through `{% translate %}` / `{% blocktranslate %}`.
    The subject is one line (Django refuses a header with a line break).
R5. What each email says (D9). A job has no title: it is named by its type and date, as on
    the cards ("Demolition, 15 March 2027"; the date in the recipient's `DATE_FORMAT`).
    - new application: subject "New application: <job type>, <date>"; body: <worker name>
      applied with <N> worker(s); a link to the job page at the application
      (`#application-<id>`, as `back_to()`).
    - accepted: subject "You are accepted: <job type>, <date>"; body: the start time and how
      many of the crew were taken; a link to "My applications", where the employer's contact
      and the address are.
    - rejected: subject "Application not accepted: <job type>, <date>"; body: a link to the
      job list.
    No phone, no address, no message text, no email address in any email (D9).
R6. Links are absolute, built from the request (`request.build_absolute_uri`): on Render
    they start with `https://` (`SECURE_PROXY_SSL_HEADER`).
R7. If sending raises, the action stays done and its success message is shown; the error is
    logged as `Notification failed: kind=… application_id=… error=<exception class>`, with
    ids only (D10). A sent email is logged as `Notification sent: kind=… application_id=…`
    (#124 style).
R8. Sent in the same request, no queue (D11).

### Acceptance criteria (→ tests)

AC1. Applying sends one email to the employer, none to anyone else.
AC2. Accepting sends one email to the worker; rejecting sends one; each says the right
     outcome.
AC3. A form with errors, applying twice, deciding an already decided application send
     nothing.
AC4. The email is rendered in the recipient's language, also when the person who clicked
     uses another one; the request's language is unchanged afterwards.
AC5. Each email has its absolute link (R5, R6), and none has the worker's or employer's
     phone, address, message or email address in the body.
AC6. Every subject is a single line.
AC7. When sending raises, the application is still saved / accepted / rejected, the success
     message is shown, and the log has the failure line with ids only.
AC8. Closing by "filled", cancelling and withdrawing send nothing (D6).

## Iteration 2: turning them off

### Requirements

R9.  `User.email_notifications`: a BooleanField, default True; the migration sets it True for
     existing users (D3).
R10. The checkbox "Email notifications" is in the name-and-phone form both roles use
     (`NameAndPhoneForm`), so it is in the profile form at onboarding and when editing (D4).
     Help text: which emails it covers and that password emails are always sent.
R11. The profile pages of both roles show "Email notifications: on / off".
R12. The `notify_…` functions send nothing when the recipient's checkbox is off (nothing is
     logged either).
R13. Every notification email ends with a line "To turn these emails off:" and an absolute
     link to the recipient's profile form (`get_profile_url()`; login first if needed) (D4).
R14. The password reset email does not depend on the checkbox.

### Acceptance criteria (→ tests)

AC9.  A new user has the checkbox on; existing users have it on after the migration.
AC10. The form shows it at onboarding and when editing, for a worker and an employer;
      unticking and saving turns it off.
AC11. With the recipient's checkbox off, applying / accepting / rejecting send nothing; the
      action still works.
AC12. Each notification email has the link to the recipient's own profile form.
AC13. Password reset still sends its email with the checkbox off.
AC14. The profile page shows on / off.

## Iteration 3: Brevo in production

### Requirements

R15. New dependency `django-anymail` (mine, 2026-11-01; D1), used only in `production.py`:
     `EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"`, the key from the env variable
     `BREVO_API_KEY`, `DEFAULT_FROM_EMAIL` from the env (D2). `local.py` keeps the console
     backend, tests keep locmem.
R16. `render.yaml` lists `BREVO_API_KEY` and `DEFAULT_FROM_EMAIL` as variables set in the
     dashboard (not in the file). Both are set on Render before the merge, with a separate
     production key.
R17. Production refuses to start without `BREVO_API_KEY` rather than send nothing (D12).
R18. One manual check against the real Brevo with the local key `bauhelfer-local` (deleted
     afterwards): its result goes into the PR's "How to test".

### Acceptance criteria (→ tests)

AC15. Production settings use Brevo's anymail backend and read the key and the sender from
      the env.
AC16. Local and test settings send nothing outside (console / locmem).

## Decisions

D1. **Brevo's HTTP API through `django-anymail`** (mine, 2026-11-01; option A, criterion:
    the emails really arrive in production). Render's free plan blocks the SMTP ports 25,
    465 and 587 since 2025-09-26; HTTPS (443) is not blocked. Rejected: our own backend on
    `urllib` (B: no dependency, but timeouts and error answers are ours to get right); SMTP
    on port 2525 (C: no code, but whether Render lets it through is known only in
    production). Brevo over Mailjet: both free without a card and in the EU (300 / day vs.
    200 / day); Brevo is known to work without our own domain (D2), Mailjet was not checked.
    **Revisit when** the project gets a paid Render plan or its own domain.
D2. **The sender is "BauHelfer" with a project Gmail address that has "bauhelfer" in it**
    (mine, 2026-11-01). We have no domain of our own, and Gmail and Yahoo require an
    authenticated sender domain since 2024, so Brevo replaces the domain part with its own:
    recipients see `BauHelfer <bauhelfer…@….brevosend.com>`. A separate mailbox, not a
    personal one: everyone who gets an email sees it. **Revisit when** the project has a
    domain (then authenticate it in Brevo).
D3. **Users can turn the emails off, with one checkbox, on by default** (mine, 2026-11-01:
    the idea to turn them off; one checkbox was Claude's default, which I accepted). Three
    emails do not need three checkboxes.
D4. **The checkbox is in the profile form; every email links to it** (mine, 2026-11-01;
    option B). The profile form opens right after the role choice, so it is also "at
    signup". Rejected: the checkbox only (A: no way from the email); a one-click link
    without login (C: a signed token, a view, a confirm button against mail scanners, more
    tests). **Revisit when** many users ask for one-click unsubscribe.
D5. **The views call the sending, after the change is saved** (mine, 2026-11-01; option A):
    the path button → view → model → email reads top-down in one place, next to the #124
    log lines. `accept()` / `reject()` commit their own transaction, so the change is in the
    database when the view goes on. Rejected: inside the model methods (B: the model knows
    about email; a new application has no method of its own) and a `post_save` signal (C:
    does not know the old status; `.update()` sends no signal; hidden from the view).
    Costs: a change made in Django admin sends no email. **Revisit when** applications can
    be decided another way than the buttons.
D6. **Only the three emails of the ticket** (Claude's default, accepted). Filled, cancelled and
    withdrawn send nothing. **Revisit when** users ask for them.
D7. **Plain text only** (Claude's default, accepted), like the password reset email: no layout
    to test in mail clients.
D8. **The recipient's language, not the clicker's** (Claude's default, accepted): the employer
    may use German and the worker Polish. Django renders in the language of the current
    request, so only the code that sends can switch to the recipient's; the translations of M5
    (#30) then apply without touching it. Already visible now: Django ships its own month
    names, so the date reads "15 marca" for a Polish worker. The test checks the language by
    that date.
D9. **Short emails with a link, no contact data** (Claude's default, accepted): the email says
    what happened and where to look. The worker's name is in the employer's email (the employer
    sees it on the job page anyway); phones, addresses and messages stay on the site behind
    login. The job type is one of our choices, so M5 translates it as well.
D10. **A failed email does not undo the action** (Claude's default, accepted): the application
     is saved and the decision made; the email is the extra. The log has ids and the exception
     class only: a provider's error text can contain the address.
D11. **Sent in the request, no queue** (Claude's default, accepted): one HTTPS call; no Celery
     or worker process on the free plan. **Revisit when** users notice the delay.
D12. **Production fails at start without the key** (Claude's default, accepted): a missing
     variable shows up at the deploy, not as emails that silently never arrive.

## Open questions

- Brevo's "Authorised IPs" may block calls from Render. The local key worked from home
  (HTTP 200 on 2026-11-01). Decided in iteration 3, after the first call from Render.

## Known limitations (→ docs/SECURITY.md)

- Brevo's free plan sends 300 emails a day; above that, sending fails and is only logged
  (D10).
- The sender address is on brevosend.com (D2); some emails may land in spam.
- A change made in Django admin sends no email (D5).
- Turning the emails off needs logging in (D4).
- Until this ticket, password reset links were printed to the Render logs; now they are sent.

## Differences from the mockups

| Mockup | App | Why |
|---|---|---|
| "My applications": green banner "… accepted your application" | no banner; an email instead | D6, #27 |
