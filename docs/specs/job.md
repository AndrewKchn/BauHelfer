# Spec: Job model (#15)

Status: **agreed**. The student decided the open questions on 2026-10-10, before any tests.

## Goal

An employer's job posting is stored in the database: what work, where, when, for how many
people and for how much money. This ticket adds only the model, the migration and the admin.
The pages that create, list and show jobs come in #16–#19, and they all build on this model.

## Requirements

R1. New app `jobs` with the model `Job`.
R2. Fields:
    - `employer`: `ForeignKey` to `User`, `related_name="jobs"`. Deleting the user deletes
      their jobs (see D4). In the admin only users with the employer role can be chosen.
    - `job_type`: one value from `accounts.models.Skill`, the same list as the worker skills
      (see D1).
    - `description`: free text, required.
    - `original_language`: the language the description is written in, one of the 7 site
      languages (`User.Language`). Needed for translation (#38). No default: the form in #16
      fills it from the employer's `preferred_language`.
    - `address`: street and number, required, up to 200 characters.
    - `district`: required, one of `District`: the 25 Munich Stadtbezirke plus
      "Munich area (outside the city)" (decided in #11).
    - `latitude`, `longitude`: `DecimalField(max_digits=9, decimal_places=6)`, both may be
      empty (see D3). Filled by geocoding later (#41).
    - `date`, `start_time`, `hours`: the day, the start time and how many hours, 1–10
      (see D2, D8).
    - `workers_needed`: how many workers, 1–10 (see D7).
    - `hourly_rate`: euros per hour, `DecimalField(max_digits=6, decimal_places=2)`, at least
      `MINIMUM_WAGE` (see D5).
    - `status`: open | filled | done | cancelled, default **open**.
    - `created_at`: set automatically when the job is saved the first time.
R3. `MINIMUM_WAGE = Decimal("13.90")` is a constant in `jobs/models.py` (German minimum wage
    from 1 January 2026).
R4. `str(job)` shows the job type and the date, for example "Demolition – 2026-11-03".
R5. Admin: `Job` is registered with a list of type, date, district, workers, rate and status,
    filterable by status, district and job type.
R6. Every label and choice name is wrapped in `gettext_lazy`.

## Out of scope

- Forms and pages for jobs (create #16, list #18, detail #19): integration tests come with
  them (see D6).
- A date in the past: checked by the create form in #16, not by the model (the admin may need
  to edit old jobs).
- Who may see the full address: decided with the job detail page (#19).
- Photos (`JobPhoto`): separate ticket.
- Geocoding the address into coordinates: #41.

## Acceptance criteria (→ unit tests)

AC1. A job created without a status has status `open`.
AC2. A job with only the required fields can be saved; latitude and longitude stay empty.
AC3. `full_clean()` rejects an hourly rate of 13.89 and accepts 13.90.
AC4. `full_clean()` rejects a job type, district or status that is not in its list.
AC5. `workers_needed` and `hours` of 0 or 11 are rejected by `full_clean()`, and by the
     database even without `full_clean()`.
AC6. Deleting the employer deletes their jobs.
AC7. `str(job)` shows the job type name and the date.
AC8. `Job` is registered in the admin.
AC9. `District` has 26 entries: 25 Stadtbezirke plus the "outside the city" entry.
AC10. The migration is in the repo and applied (`makemigrations --check` finds no changes;
      the test database is built from the migrations).

## Decisions (student, 2026-10-10)

Each question was offered with options and a recommendation.

D1. **Job type = `Skill` from the worker profile.** One list, so #18 can show a worker the jobs
    that match their skills. Rejected: a separate `JobType` list.
D2. **`date` + `start_time` + `hours`.** This is how employers describe a day of work: "tomorrow
    from 8:00, 6 hours". Rejected: start and end time; only date and hours (the worker would
    not know when to come).
D3. **Coordinates as two decimal fields, not PostGIS** (proposed by AI, not discussed). Six
    decimal places are about 10 cm. A map needs only a point; PostGIS would add a database
    extension and a system library for no feature we have.
D4. **Deleting an employer deletes their jobs** (`on_delete=CASCADE`, proposed by AI, not
    discussed). The jobs are the employer's data (GDPR). Applications to those jobs (#22) will
    be deleted with them.
D5. **Minimum wage only as a model validator, not a database constraint** (proposed by AI, not
    discussed). The validator runs in forms and the admin. A database constraint would contain
    the number: when the minimum wage rises, old jobs at 13.90 would break the migration.
D6. **No integration tests in this ticket.** There are no pages or forms for jobs yet; they
    come in #16 with its own integration tests. The "Integration tests" item stays unticked
    with this reason. Rejected (AI recommendation): an integration test through the admin
    "add job" page.
D7. **1–10 workers per job**, the same range as `team_size`. Checked by model validators and
    by a database constraint, like `team_size`. Rejected (AI recommendation): 1–20, for an
    employer who needs two crews.
D8. **1–10 hours**, because the Arbeitszeitgesetz allows at most 10 hours of work a day
    (§ 3 ArbZG). Validators and a database constraint, as in D7. Rejected: 1–12.
