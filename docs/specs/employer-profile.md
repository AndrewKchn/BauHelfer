# Spec: employer profile (#12)

Status: **agreed**. The student decided the open questions on 2026-10-07, before any tests.

## Goal

An employer (a company or a private person) says who they are: a name, optionally a company,
and what kind of work they do. Workers will read this on the job page (#19), so they know who
they would work for. It replaces the placeholder page that #10 put after the role choice.

## Requirements

R1. New model `EmployerProfile`, one per employer, linked to `User` with a `OneToOneField`
    (`related_name="employer_profile"`). Deleting the user deletes the profile.
R2. Fields:
    - `company_name`: optional, up to 150 characters. Empty for a private person (see D2).
    - `trades`: one or more values from a fixed list, `Trade` (see D1), stored as a PostgreSQL
      `ArrayField` like `WorkerProfile.skills`: window fitting, drywall, plastering, painting,
      tiling, roofing, bricklaying, carpentry, electrical, plumbing & heating, landscaping,
      demolition, general contractor, private person / own renovation, other.
R3. The profile form also edits `User.name` (required, the contact person) and `User.phone`
    (optional), with the same `NameAndPhoneForm` as the worker profile (#11, D5).
R4. Two pages, only for the logged-in employer's own profile (no id in the URL), see D3:
    - `employer_profile` at `/accounts/profile/employer/` shows all fields read-only, with an
      "Edit" button. Without a profile it redirects to the form.
    - `employer_profile_edit` at `/accounts/profile/employer/edit/` holds the form. It creates
      the profile on the first save and changes the same profile after that. On success it
      redirects to `employer_profile` with the message "Profile saved."
R5. Both pages require login (anonymous → login page) and the employer role. Any other
    logged-in user (a worker, or staff without a role) gets **403 Forbidden**, as decided for
    the worker in #11 (D7). This closes the employer half of the gap from #10.
R6. After the role choice (#10) an employer still goes to `employer_profile_edit`. The menu
    item "My company" now links to `employer_profile`.
R7. The profile page shows the company name if it is set, otherwise the person's name, and
    the trade names. Trades are checkboxes in the form. Everything is usable on a phone.
R8. The read-only block (name, company, trades, no contact details) is a separate template, so
    the job page (#19) can reuse it.
R9. Admin: the user page in /admin/ shows the employer profile inline and can edit it.
R10. The placeholder view and template from #10 are removed.
R11. Every UI string, including the trade names, is wrapped in `gettext_lazy` /
     `{% translate %}`.

## Out of scope

- Letting users add trades to the list: an idea for the "Docs sync — M2" issue (#94), see D1.
- Company address, VAT or registration number: not needed by any feature (data minimisation,
  as in #11 D3). The job has its own address (#15).
- Workers viewing the employer profile: #19. Revealing contacts after acceptance: #25.
- Requiring a profile before posting a job: decided in #16.

## Acceptance criteria (→ tests)

AC1. An employer without a profile who opens `employer_profile` is redirected to
     `employer_profile_edit`.
AC2. Posting a valid form creates one `EmployerProfile` for that employer, saves name and
     phone on the user, and redirects to `employer_profile` with "Profile saved.".
AC3. An employer with a profile sees the form filled with the current values. Posting changes
     the same profile, so there is still exactly one profile.
AC4. No trade selected, or an unknown trade value → form error. Several trades are accepted.
AC5. An empty company name is accepted. An empty name → form error. An empty phone is
     accepted.
AC6. The profile page shows the company name (or the person's name when there is no
     company), the trade names, and the phone.
AC7. A worker gets 403 on both pages. An anonymous visitor is sent to login.
AC8. An employer can only change their own profile: the URL has no id, and extra POST fields
     (for example `user`) are ignored.
AC9. An employer sees "My company" in the menu, linking to `employer_profile`.
AC10. The admin user page shows the employer profile inline.
AC11. The new templates extend `base.html` (already checked for all templates).

## Decisions (student, 2026-10-07)

Each question was offered with options and a recommendation.

D1. **Trades: a fixed list in code (`TextChoices`), several can be chosen, stored as an
    `ArrayField`.** Workers read the site in their own language, and only a fixed list can be
    translated by `.po` files. The list includes "private person / own renovation" for people
    who are not a business, and "other" without a text field: the trade is information only,
    no logic depends on it, so combinations are not checked. Rejected: free text (cannot be
    translated, typos); a list plus a free-text field for "other"; a single trade (many firms
    do two things, e.g. drywall and painting — the student chose several). The student wants
    users to be able to extend the list later (through support or another way): recorded as
    an idea for #94, not built here.
D2. **Company name optional, contact name required.** A private person renovating a flat has
    no company. Rejected: company required; one combined name field.
D3. **Two pages: a read-only profile page and an edit form**, the same pattern as the worker
    profile. Rejected: a single page with only the form.
