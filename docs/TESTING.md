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
tests/                 checks that belong to no app: settings, base layout, theme, deploy
tests/e2e/             Playwright flows; a flow goes through several apps
```

A test of one app lives in that app: if the app is removed, its tests go with it. The level
is in the file docstring (`Unit tests:` …), not in the folder name.

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

## What CI checks

On every pull request ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)); a red
check blocks the merge:

- `ruff check` and `ruff format --check`: lint and formatting
- `pytest --cov`: all tests pass and **coverage ≥ 80 %** of lines **and branches** (every
  `if` must be tested both ways), settings in `pyproject.toml`
- `interrogate`: **≥ 80 %** of functions and classes have a docstring
- the Allure report is built from the results: tests grouped by milestone and story,
  the report of `main` at <https://andrewkchn.github.io/BauHelfer/>

## How tests are named and described

- File docstring starts with the level: `Unit tests:`, `Integration tests:`, `E2E tests:`.
- `pytestmark = [pytest.mark.story(N)]`: the GitHub issue the tests belong to. A test added
  later by another ticket gets its own `@pytest.mark.story(M)`.
- Test name says the behaviour: `test_form_without_the_box_is_invalid`.
- Test docstring: a short title line (shown in the Allure report), then numbered steps,
  the checks start with `Expect: …`.
- A test without a story or a docstring stops the run (`tests/story_labels.py`).

## Techniques we use

- **Breaking the code on purpose.** A new test must fail once: delete the line it guards,
  see it red, put the line back. A test that never failed may test nothing.
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
- **Screen sizes in E2E.** The worker flow runs on a 360 px phone and checks that no page
  scrolls sideways; the employer flow runs on a laptop screen.
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

## Manual testing

Before the defense a full manual scenario on the live site: #49.
