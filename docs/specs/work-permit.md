# Spec: work-permit confirmation (#13)

Status: **agreed**. The student decided all questions on 2026-10-08, before any tests.

## Goal

Before a worker can apply to a job, they confirm "I am allowed to work in Germany". We store
when they confirmed it. This is the worker's own statement, not a check of documents: under
German law the employer still has to check the papers (see Limitations).

## Requirements

R1. `User.work_permit_confirmed` (a boolean) is replaced by
    `User.work_permit_confirmed_at = DateTimeField(null=True, blank=True)`. Empty = not
    confirmed (D2). One migration does the change and keeps existing confirmations (D7).
R2. The worker profile form (#11) gets a required checkbox "I am allowed to work in Germany"
    (D1), defined in a `WorkerUserForm` (D4). The profile cannot be saved without it, so
    every profile saved from now on has a confirmation.
R3. The first time the box is saved ticked, `work_permit_confirmed_at` is set to the current
    time. Later saves keep that date (D5).
R4. The checkbox lives only in the worker form. The employer profile form (#12) and the signup
    form (#9) do not change.
R5. `User.can_apply()` returns `True` only for a worker with a worker profile and a
    confirmation. #22 uses it in the apply view; this ticket only adds and tests the method
    (D3).
R6. Admin: the user page shows `work_permit_confirmed_at` instead of the old checkbox. An admin
    can clear it (for example after a complaint), which makes `can_apply()` false.
R7. The worker's own profile page shows the date; the profile card that employers will see
    (#23) shows only "Confirmed by the worker", or "Not confirmed" (D6).
R8. Every UI string is wrapped in `gettext_lazy` / `{% translate %}`.

## Out of scope

- The apply view and its "cannot apply" check: #22 (it calls `can_apply()`).
- Checking documents or uploading a permit: not planned (personal data we do not want).
- A checkbox at signup: there is no role yet at signup (#10), so it moved to the worker
  profile (D1). The issue title stays as it is; AI_LOG and the M2 docs sync record the change.

## Acceptance criteria (→ tests)

AC1. A new user has `work_permit_confirmed_at = None`.
AC2. Posting the worker profile form without the checkbox shows a form error and saves
     nothing (no profile, no date).
AC3. Posting it with the checkbox saves the profile and sets `work_permit_confirmed_at` to
     about now.
AC4. Saving the profile again keeps the first date.
AC5. A worker who has confirmed sees the checkbox already ticked in the form.
AC6. `can_apply()`: `True` for a worker with profile and confirmation; `False` for a worker
     without profile, a worker without confirmation, an employer, and a user without a role.
AC7. The employer profile form has no work-permit checkbox.
AC8. The admin can see and clear `work_permit_confirmed_at`.
AC9. The worker's own profile page shows the confirmation date. The profile card shows
     "Confirmed by the worker" without the date, or "Not confirmed".
AC10. The migration gives users who had `work_permit_confirmed = True` a date and leaves the
      others empty.

## Limitations (for docs/SECURITY.md)

- A ticked box proves nothing: anyone can tick it. It only records that the worker said so,
  and when.
- Employers stay responsible for checking documents before hiring (SchwarzArbG,
  AufenthG § 4a). BauHelfer does not tell them otherwise.

## Decisions (student, 2026-10-08)

Each question was offered with options and a recommendation.

D1. **The checkbox is in the worker profile form, not in signup.** At signup the role is not
    known yet (#10), and a checkbox for everyone would ask employers about a work permit.
    The profile is already needed to apply (#11, spec D4), so one rule covers both: "to apply,
    fill in your profile and confirm". Rejected: in signup for everyone; on the role page,
    shown only when "Worker" is chosen (needs JS / HTMX).
D2. **One field `work_permit_confirmed_at` (date and time, empty = not confirmed)** replaces
    the boolean. Two fields could disagree (`True` without a date, a date with `False`).
    Rejected: keep the boolean and add a date next to it.
D3. **This ticket adds `User.can_apply()` with unit tests; #22 calls it.** There is no apply
    view yet (M4), so the "Done when" item "workers without confirmation cannot apply" is met
    at model level now and in the view in #22. Rejected: moving the item to #22.
D4. **The checkbox is a field of `WorkerUserForm`, a subclass of `NameAndPhoneForm`; its
    `save()` sets the date.** The profile edit view gets a `user_form_class` attribute, so the
    employer view keeps the plain `NameAndPhoneForm`. Everything about the User stays in a
    User form. Rejected: a non-model field on `WorkerProfileForm` that the view copies to the
    user (mixes User and profile data); a third form on the page (more view code for one box).
D5. **The first confirmation date is kept.** Re-saving the profile does not change it, so the
    date answers "since when has the worker said so". Rejected: the date of the latest save
    (it would change when the worker edits their phone number).
D6. **The worker sees the date on their own page; the card for employers (#23) shows only
    "Confirmed by the worker".** Employers need to know that the worker said so, not when.
    Rejected: only the worker sees it; everyone sees the date.
D7. **A data migration keeps existing confirmations:** users with
    `work_permit_confirmed = True` get the migration time as their date, then the boolean is
    removed. Rejected: just dropping the boolean (on the live site only an admin could have
    set it, so probably nobody has it, but nobody should silently lose a confirmation).
