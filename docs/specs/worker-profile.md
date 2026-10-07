# Spec: worker profile (#11)

Status: **agreed**. The student decided the open questions on 2026-10-07, before any tests.

## Goal

A worker (or the leader of a small crew) describes themselves once: how many people come, what
they can do, which languages they speak and on what legal basis they work. Employers will read
this when they look at applications (#23). Workers can look at jobs without a profile, but
they need one to apply (#22).

## Requirements

R1. New model `WorkerProfile`, one per worker, linked to `User` with a `OneToOneField`
    (`related_name="worker_profile"`). Deleting the user deletes the profile.
R2. Fields:
    - `team_size`: 1 = individual, 2-10 = crew. Must be between 1 and 10. The model validators
      check this for forms, and a database `CheckConstraint` rejects it even without a form.
    - `skills`: one or more values from a fixed list, `Skill` (see D1):
      demolition, debris clearing, carrying materials, earthworks / digging, site cleaning,
      scaffolding helper, drywall / plastering helper, painting helper.
    - `languages`: one or more spoken languages from a fixed list, `SpokenLanguage` (see D2):
      German, English, Russian, Ukrainian, Polish, Romanian, Turkish, Bulgarian, Croatian,
      Serbian, Bosnian, Hungarian, Albanian, Arabic, Italian. These are separate from
      `User.preferred_language`, which is the language of the site.
    - `legal_status`: required, one of Gewerbe (self-employed), Minijob, employed.
R3. The profile form also edits `User.name` (required) and `User.phone` (optional), see D5.
R4. Two pages, only for the logged-in worker's own profile (no id in the URL):
    - `worker_profile` at `/accounts/profile/worker/` shows all fields read-only, with an
      "Edit" button. Without a profile it redirects to the form.
    - `worker_profile_edit` at `/accounts/profile/worker/edit/` holds the form. It creates the
      profile on the first save and changes the same profile after that. On success it
      redirects to `worker_profile` with the message "Profile saved."
R5. Both pages require login (anonymous → login page) and the worker role. Any other logged-in
    user (an employer, or staff without a role) gets **403 Forbidden** (see D7).
R6. After the role choice (#10) a worker still goes to `worker_profile_edit`. The menu item
    "My profile" now links to `worker_profile`.
R7. Skills and languages are shown as checkboxes, legal status as radio buttons. Team size is a
    number input. Everything is usable on a phone.
R8. Admin: the user page in /admin/ shows the worker profile inline and can edit it.
R9. Every UI string, including the skill and language names, is wrapped in `gettext_lazy` /
    `{% translate %}`.

## Out of scope

- District: not stored for workers (see D3). The list of Munich districts moves to the job
  (#15), together with the decision on it: the 25 Stadtbezirke plus one entry
  "Munich area (outside the city)".
- Requiring a profile before applying: checked in #22, which is blocked by this ticket.
- Employers viewing a worker's profile: #23 (the read-only profile block is a separate
  template so #23 can reuse it).
- Employer profile: #12 (its placeholder page stays).
- Real crews with member accounts: stretch #52.

## Acceptance criteria (→ tests)

AC1. A worker without a profile who opens `worker_profile` is redirected to
     `worker_profile_edit`.
AC2. Posting a valid form creates one `WorkerProfile` for that worker, saves name and phone on
     the user, and redirects to `worker_profile` with "Profile saved.".
AC3. A worker with a profile sees the form filled with the current values. Posting changes the
     same profile, so there is still exactly one profile.
AC4. Team size 0 or 11 shows a form error. Saving such a value without the form is rejected
     by the database.
AC5. No skill selected, or an unknown skill value → form error. The same for languages.
AC6. No legal status, or an unknown value → form error.
AC7. An empty name → form error. An empty phone is accepted.
AC8. The profile page shows every field in readable form: name, phone, "Individual" or
     "Crew of N", skill names, language names, legal status.
AC9. An employer gets 403 on both pages. An anonymous visitor is sent to login.
AC10. A worker can only change their own profile: the URL has no id, and extra POST fields
      (for example `user`) are ignored.
AC11. A worker sees "My profile" in the menu, linking to `worker_profile`.
AC12. The admin user page shows the worker profile inline.
AC13. The new templates extend `base.html` (already checked for all templates).

## Decisions (student, 2026-10-07)

Each question was offered with options and a recommendation.

D1. **Skills: a fixed list in code (`TextChoices`), stored as a PostgreSQL `ArrayField`.**
    The names are translated by `.po` files like the rest of the UI, and the same list can
    become the job types in #15. Rejected: `Skill` / `Language` tables with ManyToMany. An admin
    could add skills without a deploy, but the names would sit in the database where `.po`
    files cannot translate them.
D2. **Spoken languages: the 7 UI languages plus 8 common among Munich construction workers**
    (Bulgarian, Croatian, Serbian, Bosnian, Hungarian, Albanian, Arabic, Italian). The
    mechanism is the same as D1. Rejected: only the 7 UI languages.
D3. **No district in the worker profile.** The student asked what it would be used for: a
    worker who applies has already decided the trip is fine, and employers do not search for
    workers. No feature uses it, so it is not collected (GDPR data minimisation, Art. 5(1)(c)).
    This changes `docs/PLAN.md` (data model) in the M2 docs sync. Rejected: keeping it as an
    optional field. For the job (#15): the 25 Stadtbezirke plus one "outside Munich" entry
    (rejected: free text, postal code, a longer list with the surrounding Landkreise). Maps
    (#41, #42) use the job's coordinates, not the district.
D4. **The profile is needed only to apply (#22).** Workers can browse jobs first. Rejected:
    middleware that forces the profile before any page, like the role in #10.
D5. **Name required, phone optional.** Employers need to know who applied. The phone is
    useful after acceptance (#25), but email and chat (#35) exist too, so it is not forced
    (less personal data). Rejected: both required; not in this form.
D6. **Team size 1-10**, checked by model validators and by a database constraint. Rejected:
    only a minimum; 1-20.
D7. **Wrong role → 403 Forbidden** (`UserPassesTestMixin`). This closes the worker half of
    the known gap from #10, where any user could open either profile page. #12 closes the
    employer half. Rejected: a silent redirect to the user's own profile.
D8. **Two pages: a read-only profile page and an edit form.** The read-only block is reused by
    #23. Rejected: a single page with only the form.
