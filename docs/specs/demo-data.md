# Spec: demo data and the "test data only" footer (#47)

Status: **agreed**. I decided D1–D3 and D15–D17 on 2026-11-27 (my criteria: the demo must
not fail in front of the jury, simple code, no secrets or personal data in the chat or the
repo). D4–D14 are Claude's defaults, which I accepted on 2026-11-27, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

For the defense on 2026-12-01 the live site needs to look used: a list of open jobs in
several districts and languages, workers and crews with ratings and reviews. A management
command `seed_demo` creates this background data and can be run again to reset it. The real
heroes of the demo are my own accounts on the project's Gmail, registered through the site,
so the notification emails arrive live (D2).

The second part comes from #45 (via #43): a footer line on every page, "Student project with
test data only. Please do not enter real personal data." The site is public, and nothing
tells a visitor today that it is a student project.

No screen of `docs/mockups/` has a footer, so there is nothing to compare.

### Out of scope

- Job photos in the live demo data (D7, D17). I add one or two through the site to my own
  jobs.
- Chat messages and applications between demo accounts: nobody logs in as them in the demo.
- Cleaning up old test data of my own accounts: done by hand in Django admin in #49.
- The demo logins in the README: #50 (D12).
- Impressum and privacy policy pages: #43 (Stretch).

## Requirements

### The command

R1. `python manage.py seed_demo` in `accounts/management/commands/seed_demo.py` (D11).
R2. Every demo account has an address `<name>@demo.example` (D10). The command first deletes
    every user with such an address; their profiles, jobs, applications to their jobs,
    applications they made, chat messages and reviews go with them (`on_delete=CASCADE`).
    No other user is touched: not my real accounts, not the superuser, not the local dev
    users on `@example.com` (D3).
R3. It then creates (D4):
    - 3 employers: a private person (no company name), a small renovation firm, a demolition
      company; each with trades and a German phone number of the fake range
      `+49 151 0000 0xxx`.
    - 5 workers in different languages (DE, UK, PL, RO, TR), one of them a crew
      (`team_size` 3), each with skills, spoken languages, a legal status and a confirmed
      work permit.
    - About 8 open jobs from the 3 employers, in different districts and job types, dated
      from tomorrow to 7 days ahead, with descriptions in different languages and
      `original_language` set to match.
    - 3–4 jobs done yesterday or a few days ago, each with accepted applications and reviews
      in both directions, so the workers' pages show a rating and review tags (#39).
R4. All dates are relative to the day the command runs (Munich time): open jobs in the
    future, done jobs in the past within the 14-day review window (D8).
R5. Every demo account is active (`is_active=True`) with `email_verified_at` empty, so no
    notification email is ever sent to it (#27, notifications.md D13) (D6).
R6. The password of all demo accounts comes from the option `--password`; without it the
    command asks for it without showing it (`getpass`). It is not in the repo (D5).
R7. Everything runs in one transaction: if anything fails, the database stays as before (D9).
R8. The command creates rows with the ORM and never calls `translate()`, so no translation
    is cached by the local fake translator; the live site translates with Claude on the
    first view (D13).
R9. At the end it prints what it deleted and created, the list of demo logins (addresses
    and roles, not the password), and the next step: register an employer and a worker
    through the site and follow the scenario of #49 (D15).

R11. When the database is on this computer (host `localhost`, `127.0.0.1` or empty), some open
     jobs get drawn photos (a coloured picture of a house, as in
     `tests/e2e/built_screenshots.py`), saved through `JobPhoto`, so thumbnails are made too.
     With any other host no photo is made, and the report says "Photos skipped" (D17).

### The footer

R10. `base.html` shows under the copyright line: "Student project with test data only.
     Please do not enter real personal data." Wrapped in `{% translate %}`, translated into
     all 7 languages, fits 360 px.

### How it is run on the live site (D1)

From my own computer, with the production database address typed into my own terminal (never
into the chat):

    DATABASE_URL='<Supabase URL>' uv run python manage.py seed_demo

Once after this ticket is merged, and again on the morning of 2026-12-01, after a `pg_dump`
backup (#46).

## Acceptance criteria (→ tests)

AC1. After `seed_demo` there are demo employers and workers, open jobs all dated after today,
     a done job, and a demo worker whose rating counts at least one review (D16).
AC2, AC3. Merged into AC1: the exact numbers, districts and languages of R3 are checked by
     looking at the site in #49, not by tests (D16).
AC4. Running the command twice gives the same numbers as running it once (no duplicates).
AC5. A real user, a superuser, an `@example.com` user with their own job, and a user on
     `@olddemo.example` (the same ending without the `@`) still exist after the command, and
     so does that job.
AC6. Every demo account can log in with the given password; `email_verified_at` is empty and
     `is_active` is True.
AC7. No email is sent and no `Translation` row is created by the command.
AC8. When creating fails half-way, no demo account is left (old ones deleted, none created
     → the transaction is rolled back to the state before).
AC9. Without `--password` the command asks for the password (`getpass` is called).
AC10. The footer line is on a page built on `base.html`, in English and in German.
AC11. With the test database (localhost) some open demo jobs have photos whose image and
      thumbnail files exist; with the host set to a Supabase address the jobs have no photos
      and the report says the photos were skipped (D17).
AC12. The report of the command lists every demo address and not the password (R9, D12).

Tests: `accounts/tests/test_seed_demo.py` (AC1, AC4-AC9, AC11, AC12) and
`tests/test_base_layout.py` (AC10).

## Limitations

- Anyone who knows the demo password can log in as a demo account and change the demo
  data. The password is not in the repo; running the command again resets everything.
- The demo accounts have no confirmed address, so they never get emails. The demo shows
  emails only between my real accounts.
- Run from my computer, the command uses the local settings: that is why it must not upload
  photos or translate (R8, D7).

## Decisions

D1. **Run from my own computer against the Supabase database** (mine, 2026-11-27). The free
    Render plan has no Shell and no pre-deploy command. Rejected: running it in the Render
    `startCommand` (runs on every wake-up; an error there could stop the server just before
    the defense); filling the site by hand (slow, cannot be repeated).
D2. **My real accounts on the project's Gmail are the heroes; the demo accounts are
    background** (mine, 2026-11-27). Plus addresses (`+employer1`, `+worker1`, …) all arrive
    in one inbox; two more workers (Ukrainian crew of 3, German individual) show the
    rejection and cancellation emails. They are registered through the site, so their
    addresses are not in the code. Rejected: only demo accounts (no live emails);
    registering live in front of the jury (2–3 minutes of waiting, the riskiest moment).
D3. **Running again deletes only the demo accounts and what hangs on them** (mine,
    2026-11-27). Rejected: wiping the whole database except the superuser (easy to delete
    something by mistake). Same idea as the local `[seed]` marker.
D4. **The content of R3** (Claude's default, accepted 2026-11-27).
D5. **The password is an option or asked for, never in the repo** (Claude's default,
    accepted 2026-11-27). The repo is public: a password in the README would let anyone
    change the demo data before the defense.
D6. **Demo accounts have no confirmed address** (Claude's default, accepted 2026-11-27). No
    code is needed for "no email to them": #27 already sends nothing to an unconfirmed
    address, so Brevo never gets a bounce from a made-up address.
D7. **No photos** (Claude's default, accepted 2026-11-27). Run locally, the command would save
    them on my disk, not in Supabase Storage.
    **Changed by D17:** photos into a local database only.
D8. **Dates relative to today** (Claude's default, accepted 2026-11-27). Seeded on 28
    November with fixed dates, an "upcoming" job could be in the past on 1 December.
D9. **One transaction** (Claude's default, accepted 2026-11-27). A half-seeded live database
    is worse than none.
D10. **Demo addresses on `@demo.example`, not `@example.com`** (Claude's default, accepted
     2026-11-27). Found while writing this spec: the local dev users are on `@example.com`,
     so deleting by that domain would delete them on my computer. `.example` is reserved for
     examples (RFC 2606), like `example.com`, so no mail can ever reach it.
D11. **The command lives in `accounts`** (Claude's default, accepted 2026-11-27). It starts
     from users: it deletes and creates accounts, and everything else hangs on them.
     Rejected: a new `demo` app (one more app for one file).
D12. **Demo logins: printed by the command, listed in the README in #50** (Claude's default,
     accepted 2026-11-27). Docs are not edited in a ticket (`CLAUDE.md`); the "Done when…"
     item changes to "Demo logins documented (password set when running the command, not in
     the repo)".
D13. **No translations while seeding** (Claude's default, accepted 2026-11-27). See R8.
D14. **The texts of the job descriptions** (Claude's default, accepted 2026-11-27). Claude
     drafts them in all seven languages; RU and UK I review, DE / PL / RO / TR are checked by
     back-translation, as for the UI strings (`docs/specs/translations.md`).
D15. **Mentors running the project locally use the same path as the demo** (mine,
     2026-11-27; my idea that mentors need users and a flow to check). `seed_demo` gives the
     background, they register an employer and a worker through the site (the confirmation
     link and every email appear in the `runserver` terminal) and follow the scenario
     written in #49 for both localhost and the live site. Rejected: a `--local-heroes` flag
     creating a ready pair with confirmed addresses (more code, and run against production
     by mistake it would make Brevo send to `@demo.example`); a video only (mentors would
     not check anything themselves).
D16. **Eight tests, not thirteen** (mine, 2026-11-27). Tests guard what can do harm or break
     the demo: deleting other accounts, emails, translations, the transaction, the password.
     The amounts of R3 (how many accounts, districts, languages) I check by eye on the site.
     Rejected: one test per item of R3 (13 tests, they break on every change of the content
     and protect nothing); no tests (the command deletes users on the live database).
D17. **Drawn photos, only into a local database** (mine, 2026-11-27; Claude's recommendation,
     after I asked for photos like the ones in the test data). Mentors running the project
     locally see the gallery and the thumbnails. Run against Supabase with the local
     settings, the files would go to my disk and the live site would show broken pictures,
     so photos are made only when the database host is local. Rejected: no photos at all
     (D7, mentors see no photos); photos on the live site too (it needs the production
     settings, so every production secret on my computer).
