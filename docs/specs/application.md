# Spec: apply to a job (#22)

Status: **agreed**. The student decided D1 on 2026-10-20 (criteria: easy to use on a phone,
less code) and accepted the defaults D2–D9 the same day, before any tests.

## Goal

A worker applies to a job with a short message and the number of people they bring. Today the
"Apply" button on the job page (#19) posts to a stub that says "Applying is not available
yet." This ticket adds the `Application` model and replaces the stub's body; the employer's
side (list, accept, reject) comes in #23–#24.

One iteration: model, form, view and the apply part of the job page.

### Requirements

R1. `Application` (in `jobs/`): `job` and `worker` (foreign keys, deleted with the job or the
    account), `message` (optional, at most 500 characters, checked three times, D3),
    `workers_offered` (1–10),
    `status` pending | accepted | rejected (default pending), `created_at`.
R2. At most one application per worker per job: a `UniqueConstraint` on (job, worker) in the
    database (D5).
R3. `workers_offered` is checked in the database (1–10) and in the form: at most
    `min(team_size, job.workers_needed)` (D4).
R4. The apply form is on the job page, below the employer card (D1). It has the message and
    "Workers I bring" (a number field with `min="1"` and `max=` the limit, starting at the
    largest allowed value), and the button "Send application". A worker who can bring only 1 gets no number field; 1 is saved (D4).
R5. `job_apply` (`/jobs/<pk>/apply/`) keeps everything from #19 R9: only POST (GET gives
    405), workers only (guests go to login, employers get 403), unknown job 404. Its body now:
    - the worker cannot apply (`User.can_apply()` is False): error message, back to the job
      page (D6);
    - the job does not accept applications (`job.accepts_applications`): error message, back
      to the job page (D8);
    - the worker has already applied: info message, back to the job page (D5);
    - the form is valid: the application is saved, a success message, back to the job page;
    - the form is not valid: the job page is shown again with the form and its errors (200),
      scrolled to the form (`#apply`) (D1).
R6. The job page, for a worker, by state (D6, D7):
    - has applied: "You applied · 2 workers · Pending" instead of the form, whatever the job's
      status now;
    - job accepts applications, `can_apply()` False: "Complete your profile to apply" with a
      link to `worker_profile_edit`, no form;
    - job accepts applications, can apply: the form (R4);
    - otherwise: nothing, as in #19.
    Guests and employers see the page as in #19.
R7. A saved application is logged: `Application created: application_id=… job_id=…
    worker_id=…`, ids only, never the message (#124, D9).
R8. Every UI string is wrapped in `{% translate %}` / `gettext_lazy`.

### Out of scope

- The employer sees the applications: #23. Accept / reject, "filled": #24. Contacts: #25.
- "My applications" and withdrawing an application: #26 (withdrawing has no ticket yet).
- Email about a new application: #27. Translating the message: #33.
- HTMX submit without a page reload (D1, rejected for now).

### Acceptance criteria (→ tests)

AC1. A second application by the same worker to the same job is refused by the database
     (`IntegrityError`); the same worker can apply to another job.
AC2. The form refuses `workers_offered` above the team size, and above the job's workers
     needed; accepts the largest allowed value, which is also where the field starts and
     its `max` in the browser; a message of 501 characters is refused, an
     empty one accepted. The message field is a textarea with `maxlength="500"`; the database
     refuses a message of 501 characters saved without the form.
AC3. A worker with team size 1 gets a form without the number field; the saved application
     has `workers_offered` 1.
AC4. POST as a worker who can apply: one application with the message, the number,
     status pending; redirect to the job page with a success message; a log line with the
     ids and without the message.
AC5. POST with an invalid number: no application; 200 with the job page and the form error.
AC6. POST to a cancelled job, and to a job that has started: no application, an error
     message.
AC7. POST by a worker without a profile, and by one without the work-permit confirmation:
     no application, an error message.
AC8. A second POST by the same worker: still one application, an info message.
AC9. #19 AC7 stays: GET gives 405, a guest goes to login, an employer gets 403, an unknown
     job gives 404 (the "not available yet" test is replaced by AC4).
AC10. The job page for a worker who can apply has the form; for one who cannot, the
      "Complete your profile" link and no form; after applying, "You applied" with the
      number and "Pending", and no form; for a guest and an employer, no form.
AC11. A guest's page still makes the same number of queries as in #19 (AC9, AC14).

### Decisions (student, 2026-10-20)

D1. **The form is on the job page, submitted by a normal POST** (the student's criteria:
    easy to use on a phone, less code). `JobApplyView` inherits `JobDetailView`, so a form
    with errors is shown on the same page with the same context; the form's action ends in
    `#apply`, so the browser scrolls to it. The URL, the POST-only rule and the #19 tests stay.
    Rejected: a separate page `/jobs/<pk>/apply/` (one more tap and page load on a slow free
    server; the button becomes a link and #19's tests and D3 change); HTMX (the best feel, but
    a partial template, two kinds of answer and more tests). **Revisit when** a reload after
    an error proves annoying in use: HTMX goes on top of this form, nothing is thrown away.
D2. **Status stored as pending | accepted | rejected** (the plan). #24 changes it.
D3. **The message is optional, at most 500 characters** (default): not every worker writes
    German or English well, a required text would stop them. The limit is checked three
    times (the student asked for a limit in the browser and a check on the server):
    `maxlength="500"` stops typing in the browser, the form refuses a longer text sent around
    it (devtools, curl), and `CharField(max_length=500)` makes the column `varchar(500)`, so
    the admin or code without the form cannot save more. A `CharField` with a `Textarea`
    widget, not a `TextField`: a `TextField` has no limit in PostgreSQL. No "123 / 500"
    counter (JS). **Revisit when** employers complain about empty applications.
D4. **"Workers I bring" is a plain number field, 1 to `min(team_size, workers_needed)`,
    starting at the largest** (default): bringing 4 to a job for 3 makes no sense. No "−" /
    "+" buttons from the mockup (JS for looks). A worker who can bring only 1 gets no field.
    **Revisit when** #24 counts places left: then the limit may become the places still free.
D5. **One application per worker and job: a database constraint, and the view checks first**
    (default). The form cannot check it (job and worker are not form fields). Two tabs
    sending at the same instant would get a 500 from the constraint instead of a message: a
    known limitation, the data stays right. **Revisit when** withdrawing is added (#26 or
    later): a withdrawn application may have to allow a new one.
D6. **`can_apply()` is checked in the view, the page shows "Complete your profile to apply"**
    (default, #94 note to this issue): a worker without a profile or work-permit confirmation
    sees why and where to fix it; a POST around the page gets an error message.
D7. **After applying the page shows "You applied" instead of the form** (default), also when
    the job is no longer open: the worker sees what they sent.
D8. **`job.accepts_applications` is checked in the view** (default, #19 note to this issue):
    the stub did not, so a cancelled or past job could be posted to.
D9. **Logged with ids only** (default, #124): the message may hold personal data.

D10. **An employer cannot apply to their own job without extra code** (default):
     `WorkerRequiredMixin` already gives every employer 403.

### Differences from the mockup (docs/mockups/job-detail.png)

| Mockup | App | Why |
|---|---|---|
| "Workers I bring" with "−" / "+" buttons | a number field | D4 |
| The form for every visitor | the form only for a worker who can apply; others see a link, "You applied" or nothing | D6, D7 |
| "The address and phone number are shown after the employer accepts you." under the button | the line about the address stays where #19 put it | #25 changes it |
