# Testing

How BauHelfer is tested: which kinds of tests exist, where they live, how to run them and
what CI checks before a pull request can be merged.

## Test levels

| Level | What it checks | Speed | Example |
|---|---|---|---|
| **Unit** | One piece alone: a model method, a form, a validator | milliseconds | [`test_email_is_stored_lowercase`](../accounts/tests/test_models.py): `Anna@Example.COM` is saved as `anna@example.com` |
| **Integration** | One request through the whole stack with the Django test client: URL, middleware, view, form, template, database | ~10 ms | [`test_signup_leads_to_the_role_choice`](../accounts/tests/test_onboarding_views.py): after signup the user lands on "Who are you?" |
| **E2E** | A whole user flow in a real browser (Chromium via Playwright) against a running server | ~2 s | [`test_user_logs_out_and_logs_in_again`](../tests/e2e/test_account_flows.py): log in, log out with the header menu, log in again |

Most tests are unit and integration tests: they are fast and point at the broken line.
E2E tests are few and slow, but they catch what the test client cannot see: a missing
`{% csrf_token %}` in a form, a button outside its `<form>`, a menu that does not open.

Order in a feature ticket: unit tests first, committed failing ("Add failing tests for …"),
then the code, then integration tests. E2E tests are written once per milestone, in the
milestone test tickets (#14, #21, #28, #40), together with a coverage review.

## Where tests live

```
accounts/tests/        unit + integration tests of the accounts app (one folder per app)
jobs/tests/            the same for the jobs app
tests/                 checks that belong to no app: settings, base layout, theme, deploy,
                       migrations, media storage, mockups
tests/e2e/             Playwright flows; a flow goes through several apps
tests/e2e/helpers.py   shared E2E helpers: PHONE, LAPTOP, log_in(), assert_fits_the_screen()
tests/e2e/built_screenshots.py   not a test (no test_ prefix, run by path): saves
                       docs/mockups/built/*.png
conftest.py            fixtures for every test: fast_password_hasher, in_memory_file_storage
```

A test of one app lives in that app: if the app is removed, its tests go with it. The level
is in the file docstring (`Unit tests:` …), not in the folder name.

`tests/test_migrations.py` fails when a model changes without a migration
(`makemigrations --check`).

## How to run

```bash
docker compose up -d                  # PostgreSQL; the tests create their own test database
uv run playwright install chromium    # once per clone, for tests/e2e/
uv run pytest                         # everything, E2E included (~30 s)
uv run pytest accounts/tests/test_models.py              # one file
uv run pytest -k password_reset                          # tests whose name matches
uv run pytest tests/e2e                                  # only the E2E tests
uv run pytest tests/e2e --headed --slowmo 500            # watch the browser click
PWDEBUG=1 uv run pytest tests/e2e -k logs_out            # step through one test
uv run pytest tests/e2e --tracing on                     # record every step, then:
uv run playwright show-trace test-results/<test>/trace.zip   # replay it
uv run pytest --cov                                      # with the coverage table
```

The Allure report of a pull request is only an artifact (GitHub Pages shows `main`). Opening
its `index.html` from disk shows nothing, because the browser blocks loading `data/` from
`file://`, so serve it:

```bash
gh run download <run-id> -n allure-report -D allure-report-pr
uv run python -m http.server 8000 -d allure-report-pr   # then open http://localhost:8000
```

## What CI checks

On every pull request ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)); a red
check blocks the merge:

- `ruff check` and `ruff format --check`: lint and formatting
- `pytest --cov`: all tests pass and **coverage ≥ 80 %** of lines **and branches** (every
  `if` must be tested both ways), settings in `pyproject.toml`
- `interrogate`: **≥ 80 %** of functions and classes have a docstring
- the Allure report is built from the results: tests grouped by milestone and story,
  the report of `main` at <https://andrewkchn.github.io/BauHelfer/>
- a failed run uploads the `playwright-traces` artifact (`test-results/`, #21): download it
  from the run's Summary page and replay with `uv run playwright show-trace trace.zip`

## How tests are named and described

- File docstring starts with the level: `Unit tests:`, `Integration tests:`, `E2E tests:`.
- `pytestmark = [pytest.mark.story(N)]`: the GitHub issue the tests belong to. A test added
  later by another ticket gets its own `@pytest.mark.story(M)`.
- Test name says the behaviour: `test_form_without_the_box_is_invalid`.
- Test docstring: a short title line (shown in the Allure report), then numbered steps,
  the checks start with `Expect: …`.
- A section comment that cites spec items names the issue and the spec file:
  `# Filters, iteration 2 (#18, docs/specs/job-list.md R12-R21; AC15-AC19)` (older files: #133).
- A test without a story or a docstring stops the run (`tests/story_labels.py`).

## Techniques we use

- **Breaking the code on purpose.** Every new test must fail once: delete the line it guards,
  see it red, put the line back. A test that never failed may test nothing. It also finds
  problems in the code: in #64 Django admin's `max_num` only hid extra rows, so a hand-made
  POST saved 6 photos (fixed with `validate_max`); in #19 removing `prefetch_related` changed
  nothing, so it was not needed. Pitfalls we hit:
  - Undo only the file you broke, never a whole folder (in #18 that wiped uncommitted tests).
  - Break only a file without uncommitted changes, or undo the mutation with the reverse
    edit: `git checkout -- <file>` also undoes your own work in it (#21).
  - A broken build input (`tailwind/input.css`): after undoing it, **rebuild
    `static/css/app.css`**, or the next run still reads the broken build (#113).
  - A mutant of the same size in the same second can reuse the cached `.pyc`: run with
    `PYTHONDONTWRITEBYTECODE=1` (#64).
- **A fixed clock.** Tests that depend on the time replace `django.utils.timezone.now` with
  pytest's `monkeypatch` (`frozen_now` in `jobs/tests/test_models.py` and
  `jobs/tests/test_job_filter.py`; one shared fixture: #133). No new dependency.
- **Uploaded files in tests.** `in_memory_file_storage` (root `conftest.py`) keeps photos in
  memory, never in `media/` or the real bucket. `live_server` cannot serve them, so a
  screenshot that must show photos returns a picture with `page.route("**/media/**", …)`;
  E2E checks of the carousel do not need it (#21).
- **Tailwind sees only the files in `@source`** (`tailwind/input.css`), incl. `*/forms.py`
  since #64: a class used only in a widget would otherwise be missing from `app.css`.
- **A fresh database for every test.** pytest-django creates a test database once per run
  and rolls back every test's changes, so tests do not depend on each other or on order.
  E2E tests use `live_server`, which empties the tables after each test instead.
- **The Django test client** for integration tests: a fake browser inside the test
  process, no server, no JavaScript, fast.
- **Real browser + live server** for E2E: `live_server` runs the site in a thread of the
  test process, so the test still sees the test mailbox (`mailoutbox`): the password
  reset test reads the link from the email without sending a real one.
- **A fast password hasher in tests.** Django hashes passwords with a million PBKDF2
  rounds (~0.7 s each), slow on purpose against stolen hashes. The root `conftest.py`
  switches the tests to one MD5 round: the whole run went from ~2 min to ~30 s. A test in
  `tests/test_deploy.py` checks that production still uses PBKDF2.
- **Screen sizes in E2E.** The worker flow and the employer job flow
  ([test_job_flows.py](../tests/e2e/test_job_flows.py), #21) run on a 360 px phone and check
  that no page scrolls sideways; only the employer signup runs on a laptop screen. The
  mockups in `docs/mockups/` are 390 px wide, and so are the built screenshots next to them;
  checks stay at 360 px.
- **Testing a data migration** (`test_migration_keeps_existing_confirmations` in
  [test_work_permit.py](../accounts/tests/test_work_permit.py), #13): Django's
  `MigrationExecutor` moves the test database back to the migration before, the test creates
  data the old way, migrates forward and checks the data survived. No extra library.
- **Coverage is a map, not a goal.** 100 % means every line ran in some test, not that
  every result was checked. The coverage review in each milestone test ticket looks for
  branches nobody tested.

## What the tests do not check

- **Non-text contrast.** `tests/test_theme_contrast.py` checks text colours on their
  backgrounds (WCAG AA, 4.5:1), not input borders or the focus outline (WCAG 1.4.11, 3:1).
  Pages were checked by hand; an automatic check is a candidate for #48.
- **JavaScript coverage.** Coverage measures Python only. The scripts in
  `templates/jobs/job_form.html` and `templates/jobs/job_detail.html` are checked only by the
  E2E tests, and nothing warns when a new script has none. Revisit when the apply form (#22)
  adds JavaScript.
- **The `@override` rule** (`CLAUDE.md`). A one-time script found all 20 overriding methods
  in #125; no test checks new ones. Revisit when we add a type checker (it would flag
  `@override` on mixin methods) or the rule is broken in review.

## Manual testing

Before the defense a full manual scenario on the live site: #49.
