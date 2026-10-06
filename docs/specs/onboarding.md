# Spec: role selection and onboarding (#10)

Status: **agreed** — open questions decided by the student on 2026-10-06, before any tests.

## Goal

Right after registration every new user says who they are — "I need workers" (employer) or
"I am looking for work" (worker) — and is then sent to the profile form for that role. The rest
of the site (jobs, applications, chat) depends on the role, so nobody may use it without one.

## Requirements

R1. A logged-in user without a role is sent to the role selection page from every other page
    (see Q1 for how), except: the role selection page itself, logout, and the admin.
R2. Staff and superusers (admins) are never sent there: admins have no role (see the comment on
    `User.role`).
R3. Anonymous visitors are not affected: they see the public pages as before.
R4. The role selection page shows two choices, each one tap on a phone:
    "I need workers" → employer, "I am looking for work" → worker.
R5. Choosing saves `User.role` and redirects to the profile form of that role:
    worker → `worker_profile_edit`, employer → `employer_profile_edit` (see Q3).
R6. The role is chosen once. A user who already has a role and opens the role selection page is
    redirected to their profile form; a POST cannot change the role (see Q2).
R7. A value other than `employer` / `worker` is rejected (form error, role stays empty).
R8. After registration the user lands on the role selection page (`RegisterView.success_url`).
R9. The navigation bar differs by role (see Q4):
    - worker: "My profile" → `worker_profile_edit`
    - employer: "My company" → `employer_profile_edit`
    - no role yet: no role links, only "Log out"
    The user's email is also shown on phones (today it is hidden below `sm`).
R10. The role selection page requires login: an anonymous visitor goes to the login page.
R11. Every UI string is wrapped in `{% translate %}` / `gettext_lazy`.

## Out of scope

- The profile forms themselves: worker profile is #11, employer profile is #12. This ticket only
  adds placeholder pages under their final URL names, which #11 / #12 replace.
- Forcing users to fill in the profile before using the site (decided in #11 / #12).
- The work-permit checkbox (#13).
- Changing the role later by the user (only an admin can, in /admin/).
- Menu items for pages that do not exist yet ("Post a job" #16, "Find jobs" #18, "My jobs" #20):
  each of those tickets adds its own link to the role menu.

## Acceptance criteria (→ tests)

AC1. A new user who registers is redirected to the role selection page.
AC2. A logged-in user without a role who opens `/` is redirected to the role selection page.
AC3. The same user can still open the role selection page and log out.
AC4. A staff user without a role can open `/` and `/admin/` (no redirect).
AC5. An anonymous visitor can open `/` (no redirect); opening the role selection page sends them
     to login.
AC6. Choosing "worker" saves `role="worker"` and redirects to `worker_profile_edit`;
     choosing "employer" saves `role="employer"` and redirects to `employer_profile_edit`.
AC7. Posting an invalid role value shows the form again with an error; the role stays empty.
AC8. A user with a role who opens the role selection page (GET) is redirected to their profile
     form; a POST with the other role does not change it.
AC9. A worker sees "My profile" in the menu and not "My company"; an employer the opposite;
     a user without a role sees neither.
AC10. The role selection page extends `base.html` (already checked for all templates).

## Decisions (student, 2026-10-06)

Each question was offered with options and a recommendation; the student chose the
recommended option every time.

D1. **Middleware, not a per-view check.** Deny by default: every page added from M3 on is
    protected without extra code. Allow-list: the role selection page, logout, `/admin/`;
    staff users are skipped. Rejected: a mixin per view (one forgotten view = a hole).
D2. **The role is chosen once.** The view checks in `dispatch` that the role is still empty, so
    neither GET nor POST can change it; only an admin can, in /admin/. Rejected: a "change role"
    page (jobs and applications of the old role would be left behind).
D3. **Placeholder profile pages under their final URL names** (`worker_profile_edit`,
    `employer_profile_edit`), replaced by #11 / #12. Rejected: redirect to `/` and change it later.
D4. **The role menu links only to pages that exist** (the profile link). #16, #18, #20 each add
    their own item. Rejected: disabled links to future pages.
D5. **Two large submit buttons** with `name="role"` in one form: one tap on a phone. The form
    field is required even though `User.role` is `blank=True` (admins have no role).
    Rejected: radio buttons plus "Continue".
