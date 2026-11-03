# Spec: email verification at signup (#81)

Status: **agreed** for iteration 1. I decided D1–D4 on 2026-11-03 (my criteria: fake
accounts should not be possible where the demo does not need it, and emails must keep
arriving: bounces and complaints harm the sender's reputation). D5–D9 are Claude's defaults,
which I accepted on 2026-11-03, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted.

## Goal

Today anyone can sign up with any address, a made-up one or someone else's, and is logged
in at once. Since #27 emails go only to confirmed addresses (`User.email_verified_at`,
notifications.md D13), but nothing fills that field except Django admin. This ticket makes a
new account inactive until its owner clicks a link sent to the address; the click confirms
the address and logs them in.

Three iterations in one branch and one PR:

1. The link: signup → inactive account → email → confirm → logged in; a hint at login.
2. "Send the email again".
3. The demo switch `SiteSettings.email_verification_required`.

No screen of this ticket is in `docs/mockups/`.

### Out of scope

- Deleting accounts that are never confirmed (known limitation).
- Rate limiting of login, signup and "send again": #91.
- Hiding whether an address is registered at signup (D3).
- The translations themselves: #30 (M5). Every string is wrapped in `gettext`.

## Iteration 1: the link

### Requirements

R1. Signup (`RegisterView`) saves the user with `is_active=False` and does not log them in.
    It sends the confirmation email (R3) and redirects to `/accounts/register/done/`.
R2. `/accounts/register/done/` says: "We sent a link to <address>. Open it to activate your
    account." The address comes from the session, set by R1 (D7); without it the page shows
    the text without an address.
R3. The email: plain text, `templates/emails/verify_email_subject.txt` and `_body.txt`, in
    the language of the signup page (D8). The body has the absolute link (R5), says it works
    for 3 days and once, and "If you did not create an account, ignore this email: without
    the link nothing happens." A failed send is logged (user id and exception class only, as
    notifications.md D10); the account stays, the page is the same (D9).
R4. `accounts/tokens.py`: `EmailVerificationTokenGenerator`, a subclass of Django's
    `PasswordResetTokenGenerator` with its own `key_salt` and `email_verified_at` added to
    the hash value (D5). One shared instance, `email_verification_token`.
R5. `/accounts/verify/<uidb64>/<token>/`:
    - GET with a valid link: a page with a "Confirm email" button (a form that POSTs to the
      same address) (D6). Nothing changes on GET.
    - POST with a valid link: `is_active=True`, `email_verified_at=now`, saved; the user is
      logged in, sees "Your email is confirmed." and goes to the role choice (#10).
    - An unknown user, a wrong, used or expired token (GET or POST): a page "This link is
      invalid or has expired" with a link to log in (from iteration 2: to "send again").
      Nothing changes.
R6. Login (`LoginForm`): when the email and password are right but the account is inactive
    and its address not confirmed, the error is "Please confirm your email first. We sent
    you a link when you signed up." (D2). Every other failure, an inactive account with a
    confirmed address included (blocked by an admin), keeps "Wrong email or password."
R7. Accounts created by `createsuperuser` or in Django admin stay active, as now.

### Acceptance criteria

AC1. After signup the user exists, is inactive, unconfirmed, not logged in, and one email
     went to their address with a link to R5.
AC2. The "done" page shows the address.
AC3. GET on a valid link changes nothing and shows the button.
AC4. POST on a valid link activates, confirms, logs in, redirects to the role choice.
AC5. The same link a second time: "invalid" page, nothing changes.
AC6. A link older than `PASSWORD_RESET_TIMEOUT`: "invalid" page.
AC7. A password reset token for the same user does not work as a confirmation link.
AC8. Login of an unconfirmed inactive account with the right password: the R6 hint; with a
     wrong password: "Wrong email or password."
AC9. Login of an inactive account with a confirmed address: "Wrong email or password."
AC10. A failed email is logged without the address; the "done" page is shown.

## Iteration 2: "Send the email again" (to be specified)

A page with an email field, the same answer for every address (as password reset), sending
only to inactive unconfirmed accounts. Linked from the "done" page, the R6 hint and the
"invalid link" page. Open question: how to stop it from being used to send many emails to
one address before #91.

## Iteration 3: the demo switch (to be specified)

`SiteSettings` with `email_verification_required` (one row, default on), in Django admin for
superusers only. Off: signup works as before #81 — active, logged in, no email, unconfirmed.

## Decisions

D1. **Confirmation is required, as the issue says** (mine, 2026-11-03; criterion: no fake
    accounts where the demo does not need them). Rejected: "continue without confirming"
    (my first idea, for the demo) and a soft variant where only applying and posting need a
    confirmed address. The demo works without them: Gmail "+" addresses (my idea:
    `…+demo1@gmail.com` lands in the project mailbox) for a live signup and for prepared
    accounts; if the email is late or in spam, the switch (iteration 3) is turned off in
    admin.
D2. **The login hint is our own check in `LoginForm`** (mine, 2026-11-03, Claude's
    recommendation). Django's `ModelBackend` refuses inactive users, so the form only sees
    "wrong email or password". Rejected: `AllowAllUsersModelBackend` — it also keeps the
    sessions of inactive users, so an account blocked by an admin would stay logged in.
    The hint needs the right password, so it does not show which addresses are registered.
D3. **Signup with a taken address still says so** (mine, 2026-11-03; criterion: emails must
    keep arriving). Rejected: the same "check your email" page for every address with an
    email to the owner (anyone could make us email a real person again and again: complaints
    harm the sender) or without one (an owner who forgot their account waits for nothing).
    `docs/SECURITY.md` still says #81 fixes this: a comment in #96. **Revisit when** #91
    limits requests.
D4. **No migration for existing accounts** (mine, 2026-11-03): production has only test
    users. I delete them in Django admin after the merge (in the PR's "How to test").
D5. **The token is Django's reset token with its own salt** (Claude's default, accepted): nothing is
    stored. The hash covers the password hash, `last_login`, the email and
    `email_verified_at`; after the click the last two change, so the link works once. The
    own `key_salt` makes a reset link useless here and the other way round. It expires
    after `PASSWORD_RESET_TIMEOUT` (Django's 3 days), shared with password reset.
D6. **A button, not the link alone** (Claude's default, accepted): mail scanners open links in emails;
    if GET activated and logged in, the scanner would get the session and the user a used
    link. Django's password reset works the same way. Cost: one click more.
D7. **The "done" page shows the address** (Claude's default, accepted): a typo is seen at once, before
    an email bounces.
D8. **The email in the page's language** (Claude's default, accepted): a new account's
    `preferred_language` is still the default, the page language is what the person reads.
D9. **A failed send keeps the account** (Claude's default, accepted): as notifications.md D10; the
    user can ask again (iteration 2).

## Known limitations (→ docs/SECURITY.md)

- Signup shows that an address is registered (D3).
- An account that is never confirmed stays in the database, inactive.
- One email goes to every address typed at signup, made-up ones included; Brevo blocks an
  address after a hard bounce (to check on the contact's record in Brevo once).
- The owner of an address someone else typed gets one email they did not ask for.
