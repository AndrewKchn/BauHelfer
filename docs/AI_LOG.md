# AI Log

How AI (Claude Code) was used in this project: what was asked, what was decided and why,
what I reviewed, changed or rejected. One entry per ticket (or per session if a ticket takes
several). Entries are drafted with the `/ai-log` skill from the session and then edited by me.

## Entry format

```markdown
## YYYY-MM-DD · #N Ticket title

**Task given to AI:** what was asked and what context was given.

**AI helped:** what it generated or explained well.

**AI failed:** wrong code, bad suggestions, failing tests, missed edge cases — and how they were found.

**I overruled:** suggestions I rejected or changed, and why.

**Learned:** what I now understand and can explain.
```

Sessions without a ticket (planning, process) use `Planning:` instead of `#N`.

---

## 2026-10-02 · Planning: Project idea

**Task given to AI:** turn the idea into a project description and scope for a 2-month final
project. The idea came from a friend who had this problem himself: construction specialists in
Munich (window fitters, plasterers, etc.) often need general labourers for a day or two and have
no simple way to find them. From the start I wanted the site to work for Russian- and
Ukrainian-speaking workers too, because many of them don't speak German well; I thought this
would be added later.

**AI helped:** described the two user roles (employer, worker) and the core flow: post a job →
workers or small crews apply → employer accepts → chat. Put multilingual support into the plan
as its own milestone (M5): UI in DE, EN, RU, UK, PL, RO, TR and auto-translation of jobs and
messages with the Claude API.

**AI failed:** nothing notable at this stage.

**I overruled:** nothing — the idea, the target users and the need for other languages are mine;
AI structured them into a plan.

**Learned:** how to describe an idea as roles + one main user flow before thinking about code.

## 2026-10-02 · Planning: Stack choice

**Task given to AI:** choose a stack. The school has no stack requirements; I chose Python as the
language. Context given: I am a beginner and don't know Django or frontend.

**AI helped:** compared Django and FastAPI. Explained that Django templates + HTMX let me build
the whole app in one Python project, without a separate frontend (React etc.) and a separate API.
Proposed the rest of the stack: PostgreSQL, Tailwind, Claude API (`claude-haiku-4-5`) for
translations, Leaflet + OpenStreetMap for the map, Render (Frankfurt) for hosting.

**AI failed:** nothing notable at this stage.

**I overruled:** I stopped the plan approval several times to discuss the stack and hosting
first, before any setup was done. I picked Django over FastAPI: I expected I would have to build
backend and frontend separately, and if that can be avoided, it is better to keep things simple
and not create extra complexity for myself.

**Learned:** the difference between a "batteries included" framework (Django: auth, ORM, admin,
forms, i18n built in) and a minimal API framework (FastAPI), and why one project with server
rendered pages is simpler than backend + separate frontend.

## 2026-10-02 · Planning: Project plan & GitHub setup

**Task given to AI:** split the work into milestones and issues and set up GitHub
(see `docs/PLAN.md`).

**AI helped:** wrote the plan: data model, app structure, 8 milestones with weekly due dates +
Stretch, 55 issues with a Description and a "Done when…" checklist. Created the repository,
labels, milestones, issues and the project board with `gh`.

**AI failed:** problems in the plan were found later, while mapping dependencies (see the next
entry).

**I overruled:** nothing yet — I mostly reviewed the backlog and the board.

**Learned:** how a backlog is organised on GitHub: issues, labels, milestones, a project board
with Todo / In Progress / Done.

## 2026-10-02 · Planning: Board & process

**Task given to AI:** make the board usable (sprints, roadmap), review the course grading rubric,
and agree on a workflow for every ticket.

**AI helped:**
- Added an Iteration field "Sprint" matching the milestones, so the Roadmap shows the timeline.
- Reviewed the rubric and suggested that every ticket leaves evidence: tests, an AI_LOG entry,
  an "AI usage" section in the PR.
- Added blocked-by dependencies between issues. While doing this it found problems in its own plan:
  - #2 (PostgreSQL) would run the first `migrate` before the custom User model (#8) exists —
    in Django that is hard to fix later. #8 was moved to M1, and I chose to move #3 to M2 instead.
  - #34 (AI error handling) came after the features that use the AI service → #32, #33, #36 are
    now blocked by #34.
  - Separate "Tests for …" tickets contradicted writing tests as part of each ticket.

**AI failed:** its first instructions for the board view settings were outdated — GitHub had moved
them to the "⚙ View" button. Found because the screens didn't match; fixed with my screenshots.

**I overruled:**
- Testing levels were my idea: unit tests first (committed failing), then the implementation,
  then integration tests; E2E (Playwright) once per milestone. The milestone test tickets
  (#14, #21, #28, #40) were renamed for E2E.
- Translations: AI's plan had one late ticket (#30) for translating the UI. I suggested putting
  translation into each UI ticket instead: strings are wrapped from M2, translated from M5.
- AI_LOG: I asked if I could fill it myself from the session history. We chose a semi-automatic
  `/ai-log` skill (#58): AI drafts, I edit and write the "why". Not fully automatic, because the
  judgment has to be mine.

**Learned:** why the custom User model must exist before the first migration; what TDD is
(failing tests first); how blocked-by dependencies show the real order of work.

## 2026-10-02 · #58 Development guardrails: CLAUDE.md and /ai-log skill

**Task given to AI:** write `CLAUDE.md` (project instructions for Claude Code, under 60 lines)
and an `/ai-log` project skill that drafts AI_LOG entries and the PR "AI usage" section, as
described in #58.

**AI helped:**
- Proposed the structure of `CLAUDE.md`: commands, structure, conventions, testing levels,
  how to work with me, ticket workflow. It moved the ticket workflow from its local memory into
  the repo, so the process is visible to reviewers.
- Designed the skill: it drafts from the current session, the issue and the git diff, leaves
  `TODO` where the reason must come from me, and writes nothing without my confirmation.
- Noticed that pytest-django is installed but not configured, so `uv run pytest` does not run
  yet — this is needed at the start of #8, where the first tests are written.

**AI failed:** it added a "Tests: what is covered, what is not" line to the PR "AI usage"
section, which was not in the issue and is not about AI usage. Found when I read the skill and
asked where the line came from.

**I overruled:**
- Commit order was my addition: tests, then code, then possible fixes, and the AI_LOG entry
  always as a separate last commit. Logging the work with AI is not a feature of the app, so it
  should be kept apart from the code.
- AI suggested moving the tests line into a separate "Testing" section of the PR. I decided
  that test cases don't belong in a PR and had it removed: the PR description should be about
  the feature, tests should live separately.
- I liked the idea of storing test cases somewhere (test names + `docs/TESTING.md`), but
  postponed it — there are no tests yet; it comes back with #8.
- I didn't want to re-read whole files after every AI edit. I chose: AI shows "before → after"
  with links to the changed lines, and I check the diff in VS Code Source Control. I rejected
  approving every single edit — too many clicks.

**Learned:** what CLAUDE.md is and that Claude reads it at the start of every session; how a
project skill in `.claude/skills/` becomes a `/command`.

## 2026-10-02 · Planning: Merge settings

**Task given to AI:** I asked whether we should stop squashing PRs, how the merge commit should
be named, and to delete the branches of merged PRs.

**AI helped:**
- Explained the three merge methods: squash glues all commits of a PR into one; a merge commit
  keeps them and also shows where each ticket starts and ends; rebase keeps them in a straight
  line without showing ticket boundaries.
- Changed the repo settings: squash disabled, branches deleted after merge, merge commit =
  PR title + PR description (so `git log --first-parent` reads as a list of features, and the
  "AI usage" section stays in git history).
- Deleted the branches of merged PRs #57, #60, #61, locally and on GitHub.

**AI failed:** nothing notable — this was still setting up the process.

**I overruled:** not squashing was my idea: I want the AI_LOG commits to stay separate and
remain in the history.

**Learned:** squash vs merge commit vs rebase, and what each one leaves in `main`.

## 2026-10-02 · #56 Protect main branch

**Task given to AI:** protect `main` so that changes get in only through pull requests.

**AI helped:**
- Noticed that #56 was blocked by #4 (CI does not exist yet) and proposed to protect `main` now
  without the CI check.
- Created the ruleset "Protect main": PR required, no force push, no deletion, 0 required
  reviews (I can't approve my own PR), no bypass for admin, no "linear history" (it would
  forbid merge commits).
- Added the merge rule to the ticket workflow in `CLAUDE.md`.

**AI failed:** nothing notable.

**I overruled:** AI planned to keep #56 open until #4 and write "Part of #56" in the PR.
I decided to close #56 now and move the two CI items ("CI check required", "failing test
can't be merged") to #4, so that two tickets don't hang in In Progress at the same time.

**Learned:** what a ruleset is, and why bypass is off and 0 reviews are required.

## 2026-10-02 · #59 Sync docs/PLAN.md with board changes

**Task given to AI:** update `docs/PLAN.md` so that it tells the same story as the board after
the planning changes of 2026-10-02 (list of changes in #59).

**AI helped:**
- Built the milestone lists from the real board (`gh issue list`), not from memory, and added
  issue numbers. Issue status is not copied into the plan — it lives on the board, so the plan
  doesn't go stale with every closed ticket.
- Added the new sections: testing approach, translation approach, board and workflow (sprints,
  dependencies, ticket workflow, protected `main`, merge rules).
- Removed the one-time "Execution after approval" steps and the outdated "empty repository"
  paragraph; updated the verification steps (58 issues, Sprint, ruleset).

**AI failed:** nothing notable.

**I overruled:** nothing — I accepted the recommended option for the outdated Context paragraph
(replace it with one sentence about the current state).

**Learned:** tickets change during the project, so the plan and other docs have to be synced
with the board and its settings from time to time.

## 2026-10-03 · Planning: Architecture review

**Task given to AI:** explain how Django works and how BauHelfer is built: how it differs from
a separate backend + frontend, and why there is no classic 3-layer structure. Then: explain the
design of the finished system and its limits, how many users it can handle and how to scale it.

**AI helped:**
- Explained MTV, projects vs. apps, the three settings files and migrations on the example of
  this repo; server-side rendering with HTMX vs. an SPA + API; where Django's layers are
  (views/templates, models/forms, ORM) and when a `services.py` makes sense.
- Drew the final system (Django monolith on Render + PostgreSQL + Claude API, Nominatim, email)
  and listed its technical, product and legal limits.
- Estimated capacity on the smallest Render plan (hundreds of active users, ~50–100 open chats)
  and found the first bottleneck: synchronous Claude API calls block gunicorn workers. Listed
  scaling steps from cheap to expensive (indexes and polling fixes → task queue → bigger
  instance → several instances → Channels).

**AI failed:** nothing notable.

**I overruled:** nothing. Two decisions are still open: whether to show the exact address
before an application is accepted, and whether to add a task queue for translations and email.

**Learned:** the app keeps no state on the server (sessions in the DB, no local files), so it
can run on several servers; the first thing to fix under load is the synchronous AI call, not
the database.

## 2026-10-03 · Planning: Job photos (#64)

**Task given to AI:** I wanted employers to be able to add photos to a job — how much harder
does that make the project? Then: explain each choice in detail (impact on the system,
complexity, time, benefit).

**AI helped:**
- Compared 4 decisions (when, how many, storage, dependencies) by impact on the system,
  complexity, time and benefit. Pointed out that the Render disk is wiped on every deploy,
  that phone photos contain GPS in EXIF (GDPR), and that Django does not delete files with the record.
- Created #64 (labels, M3, Sprint, blocked by #16 and #5, blocks #21), added photo items to #43,
  #44, #45, and synced `docs/PLAN.md`.

**AI failed:** to avoid touching my uncommitted #8 work, it created the PLAN.md branch in a
git worktree in its temporary folder. I couldn't see the branch in VS Code.

**I overruled:** I rejected the hidden worktree because it is not proper git flow. I made
a commit on #8 first, and then the branch was created normally from `main` in the project folder.
For photos I took AI's recommendations, for my own reasons:
- MVP in M3, up to 5 photos — photos make the scope of work easy to understand, so the
  employer doesn't need a long description.
- Cloudflare R2 — easier to set up than AWS, and the free tier has no time limit.
- New dependencies (Pillow, django-storages, boto3) — needed for R2 and for checking and
  resizing images.

**Learned:** why the app must stay stateless to run on several servers, and why uploaded
files can't live on the Render disk.

## 2026-10-03 · #8 Custom User model with role (employer / worker)

**Task given to AI:** implement the custom User model before the first migration: email login,
name, phone, `role`, `preferred_language`, `work_permit_confirmed`, visible in the admin. Tests
first (TDD). I asked it to explain each part, because most of the work is done by Django itself.

**AI helped:**
- Offered four design choices with a recommendation: `AbstractUser` vs `AbstractBaseUser`, one
  `name` field vs first/last name, role required vs empty until onboarding, default language.
- Wrote 15 failing unit tests, then the model, manager, admin and admin forms; then 7
  integration tests for the admin with the Django test client. Checked that the tests really
  catch bugs by breaking the email lowercasing on purpose (4 tests failed).
- Added a case-insensitive email (stored lowercase, login in any case), so one person
  cannot get two accounts as `Anna@` and `anna@`.
- Explained Django on a live demo with a temporary database: migrations and their SQL, the ORM
  generating SQL, the request path (middleware → URL → view → template), CSRF and sessions.
  Then explained the inheritance chain of `AbstractUser`, managers, password hashing, how
  `authenticate()` reaches our code, and the in-memory test database with rollback per test.

**AI failed:**
- The model had a redundant `clean()`: Django's `AbstractUser.clean()` already normalizes the
  email through our manager. Found while AI explained the code against Django's source; removed.
- `ruff format` reformatted files outside the ticket (`config/`); AI noticed it and reverted
  them. `ruff check .` already fails on `main` because the project has no ruff config — left
  for #4 (CI).
- When I asked to update the branch with `main`, AI rebased without checking the current
  branch. Another session had switched to `sync-plan-job-photos`, so the rebase ran there
  first. Nothing was lost; AI found it from the output and rebased the right branch.

**I overruled:**
- Default language `en` instead of AI's `de`: the school course is in English, so first of all
  the project has to fit the learning format, not a real-world app.
- I asked for a 3-layer architecture (views → `services.py` → models). AI showed how to do it
  in Django, then I cancelled it: for learning it is better to keep Django's original structure
  first and understand how it works. I already don't like that the tests live inside
  `accounts/`; I will come back to this when the app grows.

**Learned:**
- How testing works in Django: a temporary database (in memory for SQLite) with every test
  rolled back, and the test client that calls Django directly without a real server.
- How to run the app locally, and how and where the database is created (`migrate` →
  `db.sqlite3`). I want to come back to this later.
- The Django admin is the base for moderation (#45): blocking a user is already the "Active"
  checkbox. I clicked through the admin by hand and looked at the tables in a SQLite viewer.

## 2026-10-03 · #2 PostgreSQL via Docker Compose + env config

**Task given to AI:** take the next ticket after #8 and run PostgreSQL locally with Docker
Compose, so development and tests use the same database as production. Docker was not
installed on my machine, so I installed it myself while AI wrote the tests and config.

**AI helped:**
- Found that the env config was already done in #1 (`django-environ` reads `DATABASE_URL`,
  `psycopg` installed), so no Django code had to change.
- Wrote 2 failing tests first: the database is PostgreSQL, and its major version is 17 (the
  same as on Render). Then `docker-compose.yml` (`postgres:17`, port open to localhost only,
  a volume for the data, a healthcheck), a new `DATABASE_URL` in `.env.example` and the
  `docker compose up -d` command in `CLAUDE.md`. First `migrate` on PostgreSQL ran with the
  custom User model from #8; 24 tests pass.
- Gave install steps for Docker on Ubuntu (Engine and Desktop) and explained Engine vs
  Desktop, and why Docker goes into the system and not into the project's `.venv`.
- Explained the project structure file by file and the path of one request through Django;
  explained that Django apps form a modular monolith, not microservices.
- Explained how tests will run in GitHub Actions (#4): a `postgres:17` service container
  per run instead of `docker-compose.yml`.
- Showed how to check what runs in Docker (`docker ps`, `docker compose ps`, `docker stats`,
  volumes, images, `psql` inside the container).

**AI failed:**
- Put the database test into `config/tests/`. I didn't like test files inside the settings
  folder; moved to a root `tests/` folder before the first commit.
- `ruff check .` still fails on files from #8 and `config/settings/` (no ruff config in the
  project) — left for #4, as before.

**I overruled:**
- AI recommended Docker Engine from Docker's repository; I first chose Docker Desktop, then
  installed Engine after all and use the Docker extension in VS Code instead of the Desktop
  app. Engine runs directly in the system, not in a separate virtual machine, and its
  licence is free.
- AI first suggested moving all tests into one root `tests/` folder. I want tests per app;
  only tests that belong to no single app (database check now, E2E later) go to the root
  `tests/`. This is provisional — I will come back to it before the first E2E ticket (#14).
- AI recommended `restart: unless-stopped` so the database starts after every reboot; I chose
  to start it by hand with `docker compose up -d`: I don't want it running in the background,
  and I want to see explicitly what is running.

**Learned:**
- What a container, an image and a volume are, and why the data survives a restart.
- Why the project is a modular monolith and not microservices.

## 2026-10-03 · #4 GitHub Actions CI: ruff, pytest, coverage

**Task given to AI:** Set up CI that runs ruff and pytest on every PR, measures test and
docstring coverage (fail below 80%), adds pre-commit hooks, a PR template and a CI badge,
makes the check required for merging into `main`, and proves that a failing test blocks
the merge.

**AI helped:**
- Measured the starting point before writing any config: test coverage 99%, docstring
  coverage 35.5% — so the docstring threshold would have failed CI on the first run.
- Wrote `.github/workflows/ci.yml`: a `postgres:17` service container with a healthcheck,
  `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest --cov`, `interrogate`.
- Coverage and interrogate settings in `pyproject.toml`: migrations, tests and server entry
  points not counted; `__init__.py`, `__str__` and nested `Meta`/`TextChoices` skipped by
  interrogate. Thresholds live in `pyproject.toml`, so a local run checks the same as CI.
- Fixed the ruff errors left from #8: migrations excluded from ruff, two unused `# noqa`
  removed, Django-generated files formatted (quotes only). Added docstrings in `accounts/`
  (35.5% → 100%), turning existing comments into docstrings where they already explained
  the method.
- Explained that a `pull_request` workflow runs from the PR itself, so CI works before the
  merge; that pushing workflow files needs the `workflow` token scope (I already had it);
  how `git commit --fixup` + `git rebase --autosquash` fold a fix into an earlier commit.
- Verified the merge block with a throwaway PR #69 (`assert False`): check `test` red,
  merge state `BLOCKED`; closed without merging. Screenshot in my comment on #68:
  https://github.com/AndrewKchn/BauHelfer/pull/68#issuecomment-5973204815

**AI failed:**
- Used `astral-sh/setup-uv@v10` — that tag does not exist (setup-uv only has exact tags
  like `v10.2.0`); CI would have failed with "Unable to resolve action". I expected GitHub
  to reject the YAML file and asked; while checking, AI found the wrong tag. Fixed before
  the first push.
- Wrote a PR template whose "AI usage" headings did not match the `/ai-log` format, and did
  not notice that `gh pr create --body` ignores the template anyway.
- Twice answered me in English although we talk in Russian.

**I overruled:**
- Dropped the PR template from the ticket (struck through in #4): it would only duplicate
  what we already have — PRs are created with `gh pr create --body`, which ignores the
  template, and `/ai-log` already writes the "AI usage" section.
- AI recommended a separate fix commit for the `setup-uv` tag (visible in history); I chose
  to fold the fix into the CI commit: I want a clean history.
- AI recommended a local pre-commit hook (`uv run ruff`, one ruff version from `uv.lock`);
  I kept the standard `ruff-pre-commit` hook with its own pinned version: the local hook is
  not the setup the ruff documentation describes.
- Reviewed every commit separately before it was made, instead of one batch of 4 commits.
- AI was not allowed by its permission settings to change the "Protect main" ruleset; I
  added the required check `test` myself in GitHub settings.

**Learned:**
- Nothing new in the CI idea itself: I set up similar CI on a previous project and was
  already familiar with it. I think checking every change before the merge is the right way.

## 2026-10-04 · #5 First deploy to Render (Frankfurt): gunicorn, WhiteNoise, auto-deploy from main

**Task given to AI:** deploy the app to Render (Frankfurt) with gunicorn and WhiteNoise, with
auto-deploy from `main`. Before starting I asked how to prepare, and to explain again why
Render was chosen and what the alternatives are. I created the Render account (GitHub login)
and the Supabase project myself.

**AI helped:**
- Listed what to prepare: Render account and GitHub app limited to this repo, free-tier
  limits (sleep after 15 min, Render's free database expires after 30 days), the concepts
  gunicorn / WhiteNoise / collectstatic / build vs start.
- Compared Render with Koyeb, Railway, Fly.io, Heroku, PythonAnywhere and a Hetzner VPS
  (EU region, free tier, managed PostgreSQL, effort for a beginner).
- Explained what Supabase changes: Session pooler instead of the IPv6-only direct connection,
  Data API off (Django tables are in `public`), automatic RLS, 7-day pause, 500 MB per project.
  Suggested checking it first with `migrate` from my machine before touching Render.
- Wrote 5 failing tests (`tests/test_deploy.py`), then the settings, `render.yaml` and
  `.python-version`. Checked Render's docs instead of guessing: pre-deploy commands are
  paid-only, uv is supported via `uv.lock`, the default Python would be 3.14.
- Ran the build and start commands locally with production settings: hashed + gzipped static
  files, `http` → `301 https`, wrong `Host` → `400`.
- Explained every line of `render.yaml` and the permissions the Render GitHub app asks for.
- After the deploy, checked the live site and that Render really reaches Supabase (a wrong
  admin login returns the normal error, not a 500).

**AI failed:**
- Promised that `Refs #5` in the first PR would keep the issue open. The PR came from a branch
  linked to the issue (`gh issue develop`), so merging it closed #5 and moved the card to Done.
  I noticed it on the board; the issue was reopened.
- Asked where to run migrations in a quick multiple-choice form with a short explanation.
  I picked the recommended option, and later did not remember making that decision.
- The first implementation produced 7 WhiteNoise warnings in the tests (no `staticfiles/`
  locally); fixed with `WHITENOISE_AUTOREFRESH` in `local.py`.
- Told me to look for the `migrate` output in Render's logs, but it is not there; the cause
  is unknown. Verified via the Start Command in Render settings instead; noted in #5 that the
  final proof comes with the first deploy that adds a migration (#11 / #15).

**I overruled:**
- Database on Supabase instead of Render: it is free without a trial period, and I already
  had a Supabase account. I wanted to set it up first and only rewrite the plan and the
  tickets if it works — the plan, #5 and #46 were updated after the live deploy.
- Free plans only, also for the defense: it is a learning project. The plan said "paid tier
  for the defense"; #46 is now "Demo readiness on free plans".
- Migrations in the start command: I re-decided it after AI explained the options again
  (build / start / pre-deploy). If a migration fails, the site stays on the working version.
- AI called the "no empty host" test weak and offered to delete it; I kept it: it is a
  safety net for future changes to this code.

**Learned:**
- What happens in one deploy: CI → build → start → health check, and why the old version
  stays online if a step fails.
- Why `DEBUG=False` needs WhiteNoise for static files and `ALLOWED_HOSTS` for the host name.

## 2026-10-04 · #6 README: project idea, stack, how to run locally, live link

**Task given to AI:** expand the README (problem and solution, step-by-step local setup, links
to the live app, plan and board), list the new issues #73–#75 in `docs/PLAN.md`, and prove that
each remaining CI gate blocks the merge — #4 only proved it for a failing test (#69).

**AI helped:**
- Calculated how big each deliberate problem must be: coverage was 99 % (127 statements), so
  more than 31 uncovered lines are needed to fall below 80 %; docstrings were 23/23, so more
  than 5 undocumented functions.
- Built the throwaway PR #76: four pushes, one problem each (unused import, `ANSWER=42`, an
  untested function, 8 functions without docstrings plus a test that calls them, so test
  coverage stays green). Ran every check locally first; each CI run failed at exactly the
  expected step and the PR stayed `BLOCKED`. Closed it without merging.
- Wrote the README sections and the PLAN changes (62 issues now).
- Explained why the project uses uv instead of pip (one tool for Python, venv and packages;
  `uv.lock` pins every package on every machine), why login is by email, and that the site and
  the admin use the same account with two login pages.

**AI failed:**
- Did not expect the local pre-commit hook: ruff fixed the unused import itself and stopped
  the commit. The ruff pushes needed `git commit --no-verify`.
- The first README setup was written only from Linux. I ran it on Windows: it did not say
  that Docker Desktop is needed, how to install uv, or what `createsuperuser` asks for.
- Guessed that the slow `manage.py` commands on Windows come from `localhost` resolving to
  IPv6 first. I tested `127.0.0.1` — no change.

**I overruled:**
- Each CI gate in its own push, and a separate "yes" for every push (AI suggested one "yes"
  for all four): I needed a screenshot for every gate.
- Linked PR #76 to #4 as well, with a comment, and added my own terminal screenshots for every
  push as evidence.
- Removed the extended install block (Docker Desktop, uv commands per OS, "tested on Windows")
  from the README and kept only the `createsuperuser` note: I think the teachers know this.
- Stopped investigating the slow Windows commands: the teachers mostly use Macs, and the app
  is already deployed.

**Learned:**
- Why a project has two lines of defence: the pre-commit hook locally and CI on GitHub.
- What `uv.lock` guarantees that `requirements.txt` does not.

## 2026-10-04 · #3 Base layout template with Tailwind + HTMX, mobile-first

**Task given to AI:** create `base.html` (header, navigation, messages, footer) with Tailwind
and HTMX, mobile-first, and lay out the decisions the ticket asks for: component library and
how Tailwind is loaded.

**AI helped:**
- Compared daisyUI / Flowbite / plain Tailwind and CDN / standalone CLI, including the GDPR
  point: a CDN sends every visitor's IP to a third party.
- Checked the latest releases before installing: found that HTMX 4.0 had come out five weeks
  earlier and showed what changed compared to 2.x; verified that pytailwindcss can pin
  Tailwind v4.3.3 and that daisyUI 5 ships one file for the standalone CLI.
- Wrote 7 failing tests first (layout used, viewport, CSS/HTMX linked and served, daisyUI in
  the built CSS, messages, every page template extends `base.html`), then `base.html`,
  `tailwind/input.css`, and the CSS build step in CI and in `render.yaml`.
- Ran production `collectstatic` locally and took a 360px screenshot with headless Firefox.
- Explained template inheritance, why `app.css` is built and not in git, how WhiteNoise
  serves static files, and what HTMX will be used for.

**AI failed:**
- Offered pytailwindcss as a dev dependency, but Render installs with `--no-dev` and must
  build the CSS too. Noticed by AI before installing.
- Wrote a comment at the end of a `.gitignore` line, which git reads as part of the file
  name. Noticed by AI before the commit.
- The first CSS build was 371 KB: Tailwind scanned `daisyui.mjs`, which names every daisyUI
  class. Limited the scan to templates: 30 KB.
- Two static-file tests got 404: pytest always runs with `DEBUG=False`, and WhiteNoise then
  does not look in `static/`. Fixed with `WHITENOISE_USE_FINDERS = True` in `local.py`.
- Said that "allow pasting" in DevTools only applies to one tab; it is remembered for the
  browser profile. And in Brave it did not work for me, so I typed the commands by hand.

**I overruled:**
- Nothing overruled. From the options AI laid out I chose daisyUI (ready classes, works well
  with HTMX), a Tailwind build with pytailwindcss instead of a CDN, and HTMX 2.0.10 instead
  of 4.0 (4.0 is still raw, 2.x has far more material).
- No spec file for this ticket: it is a small task and everything is already in the issue.
- I did the manual checks myself in Brave: 360px, `htmx.version`, a request with
  `HX-Request: true`.

**Learned:**
- How `{% extends %}` and `{% block %}` build one page from `base.html` and a page template.
- Why only the classes used in the templates end up in `app.css`, and why that file is built
  instead of committed.

## 2026-10-04 · Planning: spec files

**Task given to AI:** explain what spec files are, how they differ from what the project
already uses, and add a spec step to the next complex ticket.

**AI helped:**
- Explained spec-driven development: a short file per feature (goal, requirements, out of
  scope, acceptance criteria, open questions) written before tests and code.
- Compared it with `CLAUDE.md`, `docs/PLAN.md`, skills and issues, and with the current way
  of working: decisions made in chat are lost after the session, a spec keeps them in the repo.
- Added a "Spec first (trial)" section and a "Done when…" item to #10.

**AI failed:**
- Called #10 "the next open ticket" without checking blockers; its issue list had cut off at
  50 issues, so #3 and #9 were missing. When I asked what is next, the blockers showed
  #3 → #9 → #10. The spec trial stays on #10.
- Said the memory files contain personal data about me; after checking, it is a short
  profile, the rest is project notes.

**I overruled:**
- Nothing overruled. I decided to try a spec on one complex ticket first and compare it with
  a normal ticket, instead of adding specs everywhere.

**Learned:**
- The difference between a spec, an issue, `CLAUDE.md` and `docs/PLAN.md`, and when a
  separate spec is worth it.

## 2026-10-04 · #79 Mark downloaded daisyUI and HTMX files as vendored

**Task given to AI:** I noticed that GitHub showed the repo as 91 % JavaScript and asked why,
what `tailwind/daisyui.mjs` is and where it came from, how to leave it out of the statistics,
and that the repo docs should say the file is there.

**AI helped:**
- Found the cause with the GitHub languages API: the JavaScript total (350 541 bytes) was
  exactly the size of `daisyui.mjs`; `htmx.min.js` was already skipped because of `.min.js`.
- Explained what the file is: the official daisyUI 5.7.47 plugin from its GitHub releases,
  used only while building `app.css`, never sent to the browser; and why it is kept in the
  repo instead of downloaded on every build.
- Added `.gitattributes` with `linguist-vendored`, and a note in `CLAUDE.md` and `README.md`:
  which files are downloaded, not edited by hand, and how to update them.
- Created #79 with milestone, Sprint and board status, and checked the live site after #78:
  hashed `app.css` (30 KB) and `htmx.min.js` are served, same hash as the local build.

**AI failed:**
- Added a 350 KB third-party file in #3 without thinking about the language statistics;
  I found it on GitHub.
- Copied "(#3)" into the PR #78 title from #77, although most earlier PRs do not have it;
  GitHub adds the PR number itself, so the merge commit on `main` has two numbers
  ("(#3) (#78)"). I asked why it was there.
- Proposed adding the fix as one more commit to PR #78 without checking that it was already
  merged.

**I overruled:**
- AI suggested adding the fix to PR #78. I asked to update `main` first and do it as a new
  ticket with its own branch, following the process.
- I removed "(#3)" from the PR #78 title on GitHub; the merge commit on `main` still has it.

**Learned:**
- How GitHub counts languages (by file size) and what `linguist-vendored` changes.
- Why a downloaded library can live in the repo instead of being fetched on every build.

## 2026-10-04 · #9 Registration, login, logout, password reset

**Task given to AI:** build the account pages with Django's built-in auth views, styled with
daisyUI: register, log in, log out, password reset by email (console backend locally); unit
tests first, then integration tests.

**AI helped:**
- Explained what Django already gives (login, logout, 4-step password reset) and what we write
  ourselves (only registration), and why logout is POST-only and password reset never says
  whether an email is registered.
- Offered choices with a recommendation; I picked: email + password twice only (role in #10,
  work permit in #13), log in right after signup, console email until SMTP in #27, URLs listed
  one by one instead of `include("django.contrib.auth.urls")`.
- Wrote `SignupForm`, `RegisterView`, `accounts/urls.py`, one shared form template
  `_form_fields.html` (field errors under the field, form errors in a red alert) and 6 pages +
  the reset email; tests: 20 unit, 19 integration, 100 % coverage of views and forms.
- After the integration tests passed at once, broke the code twice on purpose (no `login()`,
  email without link) to show that the tests catch it.

**AI failed:**
- Kept Django's default login error "both fields may be case-sensitive". With email login only
  the password is; I found it while testing by hand.
- In #3 it built the CSS with the light theme only and did not ask me, so dark mode works in
  the admin but not on the site; I noticed it.
- Said pushing the branch would run CI; I pointed out that CI runs only on PRs and on `main`.
- Suggested putting the plan lines for #83/#84 into the #9 PR, although they are not about #9.
- A stash conflict when moving the plan change to another branch; fixed.

**I overruled:**
- Asked whether email format is really checked; AI added 6 invalid addresses to the tests
  (no @, no domain, no dot, two @, space).
- After signup I wanted email verification, so that nobody creates fake accounts, and Google
  login, because it is faster and easier: created #81 (email verification, M4, after SMTP in
  #27) and #82 (Google sign-in, Stretch, only if time is left).
- Dark mode and colours: split into #83 (colours + dark mode, M2) and #84 (logo, icons,
  images, Stretch — after the main features).
- The plan lines for #83/#84 do not belong to this ticket: instead of AI's separate branch
  from `main`, I chose a branch on top of #9, rebased after the merge.
- The email is hidden in the header on phones: I decided to leave it until the menu in #10.
- Shortened AI's new login error to "Wrong email or password." — that the password is
  case-sensitive is obvious.
- Commit order: integration tests first, then the fix with its tests as a separate commit,
  because it is a bug fix (AI suggested the other way round).

**Learned:**
- Which auth views Django gives and why logout must be POST.
- Why password reset gives the same answer for unknown emails.

## 2026-10-05 · #89 Allure test report: tests grouped by story

**Task given to AI:** after #9 I asked whether the project needs test documentation: at work
we had Jira, where every test case was easy to read. I wanted a document that explains in
plain language what each test does, grouped by story. This became #89: an Allure report built
in CI and published on GitHub Pages.

**AI helped:**
- Explained why test cases written by hand go stale and the tests themselves do not; built a
  quick prototype catalog from the 80 existing tests to show what is possible.
- Checked allure-pytest's source (2.16.2) in a throwaway environment instead of guessing: labels
  can be added as pytest marks at collection time, the title comes from
  `__allure_display_name__`, the docstring is the default description.
- Wrote `tests/story_labels.py`, a pytest plugin: story = "#N" + issue title, epic =
  milestone, a link to the issue, the first docstring line as the title, the steps as the
  description, Suites = level → story; a test without story, docstring or file level stops the
  run. Tests first: 16 unit + 8 integration (pytester runs a real pytest with Allure).
- Added docstrings (short line + steps) and `story(N)` to all 80 existing tests, and checked in
  git history that no test file mixes tests from different stories.
- CI: `stories.json` from `gh issue list` with the built-in token, the report built also when
  tests fail, kept as an artifact, published from `main` to Pages without blocking the Render
  deploy; a result line on the run's Summary page. Verified the action versions from their
  releases before using them.

**AI failed:**
- Its first idea, steps generated from the code, gave lines like "Check 5 results" — useless
  for a reader. AI showed it honestly and proposed docstrings instead.
- The report showed 103 tests instead of 95; I noticed it. The pytester runs inside the same
  process wrote their sample tests into our report. Fixed by running them in a separate process.
- The first in-process pytester run also set up Django twice; found by the test run.
- The script that added the docstrings put them under existing comments, with an extra blank
  line; AI saw it in the diff, reverted and redid it.
- Said four test files needed a level in their docstring; the strict check found five.
- Allure 3 groups the tree by files by default; AI found it while checking the report and set
  the grouping explicitly.
- The issue link was drawn as a bug icon (Allure's "issue" type); I noticed it.

**I overruled:**
- The Jira-like catalog was my idea; I chose Allure instead of AI's self-written catalog
  script, because I know it from work and it also shows the result of every run.
- AI proposed a `Story: #N` line in every docstring; I said that is too much for every test and
  suggested tags: one `story(N)` per file, a test from another ticket gets its own.
- I asked to take the story title from GitHub by its number, and to use the docstring as the
  test name in the report. I wrote "#9" only as a link idea; since the link is there anyway, the
  marker takes just the number.
- After looking at the report: removed the features (issue labels) I had chosen first, grouped
  Suites and the tree by level (Unit / Integration) instead of milestone, hid the technical
  labels, kept only the new Allure 3 view instead of the classic one: it has fewer tabs, so
  there is less noise, and everything is visible on the first page.
- I installed Node.js myself to build the report locally; I chose the strict check.
- I wanted to see that everything works on GitHub before writing this log: AI opened the PR as a
  draft first. I added screenshots of the report, the artifact upload log and the Summary page as
  evidence: https://github.com/AndrewKchn/BauHelfer/pull/90#issuecomment-5994763477
- Kept the plugin in `tests/`, although that folder is not counted for coverage.

**Learned:**
- How a pytest hook adds labels to the tests at collection time.
- Why tests must not call the network.

## 2026-10-05 · #88 Security notes: docs/SECURITY.md

**Task given to AI:** write `docs/SECURITY.md` for reviewers: what BauHelfer protects, how,
where in the code, which tests check it, known limitations, and how to report a vulnerability.
Before deciding anything I asked AI to explain each attack (user enumeration, open redirect,
session fixation, CSRF, HTTPS settings) and why production settings differ from local ones.

**AI helped:**
- Checked every protection against the code and tests and found five with no test:
  same login error for an unknown email, `?next=` to another site, new session id on login,
  CSRF, HTTPS-only production settings.
- Wrote 6 tests for them. For each one it broke the protection on purpose (mutation check)
  to show that the test turns red.
- Ran `manage.py check --deploy` (I ran it myself first) and explained the three warnings:
  W020 only appears locally, W005 and W021 are accepted because we have no own domain.
- Pointed out that a CSRF test on the login page proves nothing, because `LoginView` is
  protected by its own decorator. The test uses the signup form instead.
- Wrote `docs/SECURITY.md` and checked by script that every link and test name in it exists.
  Also created #91 (login rate limiting).

**AI failed:**
- Pushed the branch to GitHub although I had only said yes to the commit. Our rule is no push
  without an explicit yes. No harm was done (it was the ticket branch, and CI did not run), but
  AI reported it itself.
- The deploy-check test passed locally but failed in CI (`security.W009`, weak secret
  key): it set `SECRET_KEY` in the environment, but `base.py` had already read the short
  CI key. My `.env` has a long key, so only CI found it. Fixed by setting the key directly.

**I overruled:**
- AI offered three options: tests for all five gaps, document only, or tests for some. I chose
  tests for all five.
- For production settings AI asked me to choose between `check --deploy` and plain asserts.
  I asked "why not both?", because two ways cover more cases. It turned out the deploy check
  does not look at `SECURE_PROXY_SSL_HEADER` at all, so now there are 6 tests instead of 5.
- I asked for a link to `SECURITY.md` from the README; AI also added it to `CLAUDE.md` and the
  plan.
- I removed the "AI usage" section from PR descriptions: it made the PR too long, and this log
  already has everything. Changed in `/ai-log`, `CLAUDE.md` and the plan.

**Learned:**
- Which security problems a web app can have and how each one is solved.
- How much of this a framework like Django gives out of the box: my part was to switch it on
  and prove it with tests.

## 2026-10-05 · #93 Docs sync at the end of each sprint + /sprint-docs skill

**Task given to AI:** new questions and ideas keep coming up during tickets, and I was updating
the docs a little in every ticket. I asked for ideas on doing this once, at the end of each
sprint.

**AI helped:** suggested three parts that work together: a "Docs sync — Mx" issue per sprint
that collects ideas as comments (not a file in the repo, which would cause merge conflicts
between branches); a Docs sync ticket as the last ticket of each milestone; and a `/sprint-docs`
skill that drafts the doc changes from the comments, the sprint's issues, commits and AI_LOG
entries. It created the eight issues (#93–#100) with "blocked by" links to the E2E tickets,
updated `CLAUDE.md` and `docs/PLAN.md`, and applied the new rule to this ticket: the missing
`PLAN.md` entries for #93–#100 became a comment in #94 instead of an edit here.

**AI failed:** its script for setting the Sprint field on the board had two bugs (an empty item
id, then an iteration set by name, which `gh` does not support); the third try was blocked by
Claude Code's permission check, so I set the Sprints by hand on the board.

**I overruled:**
- `docs/SECURITY.md` updates move to the end of the sprint, although the rule "update it in the
  same branch" had only just been added in #88 (AI presented this as a trade-off). I want a
  ticket's branch to contain only what belongs to its story's functionality, without small doc
  edits; at the end of the sprint the whole security picture is seen at once.
- AI recommended one exception and I agreed: `CLAUDE.md` is still fixed in the ticket that makes
  it wrong, because Claude must be up to date — it works from that file.

**Learned:** a per-sprint issue collects ideas without merge conflicts that a shared file would
cause; updating docs once a week means they can be behind for a few days, and the comments make
sure nothing is forgotten in the meantime.

## 2026-10-06 · #10 Role selection and onboarding flow

**Task given to AI:** after signup a new user must choose "I need workers" or "I am looking
for work" and must not be able to skip it; then go to the profile form of that role, with a
menu that differs by role. This ticket was a trial of spec-driven development: a spec with the
decisions first, then failing tests, then code. Before the spec I asked AI to answer the
likely defense questions and to explain middleware, the `auth` context processor and how the
role form is sent, so I could decide with understanding.

**AI helped:** drafted `docs/specs/onboarding.md` with requirements, acceptance criteria
AC1–AC10 and five open questions, each with options and a recommendation. Wrote 18 unit tests
(form, middleware with `RequestFactory`, `get_profile_url`) and 22 integration tests,
including a CSRF test and "a worker cannot become an employer by posting the form again".
Implemented `OnboardingMiddleware`, `RoleForm`, `RoleSelectView`, placeholder profile pages
and the role menu. It checked that the tests really guard the code: with the middleware
turned off, or the "role already chosen" check removed, 3 tests failed each time. It
predicted that 5 tests from #9 would break (their user had no role) and fixed them with a
minimal change. It also created three local test users (worker, employer, no role) so I
could click through the flow myself.

**AI failed:**
- The header overflowed on phones: at 360px the logo, role link, email and "Log out" did not
  fit (about 460px). AI had not counted the width, and the test client cannot see layout.
  I found it in the browser.
- AI pushed the branch expecting CI to run, but CI runs only on pull requests and on `main`.

**I overruled:**
- For the phone header AI offered a ☰ menu button, hiding the email again, or a two-line
  header. I chose the menu button but asked to keep the user's email next to it, so it is
  always visible who is logged in.
- I asked to open the PR before the AI_LOG entry (CLAUDE.md says the other way round) so CI
  would run earlier and serve as evidence for "Done when…".

**Learned:**
- How a request passes through middleware, and why deny-by-default is safer than a check in
  each view.
- Hiding a button is not security: the server must check, and tests prove it.
- When a page looks wrong after a CSS change, reload without the cache first: the menu seemed
  to stretch the header, but it was my browser's cached old CSS, not the code.
- Spec trial: writing the spec first was worth it — the decisions were mine and written down
  before any code, and the tests came straight from the acceptance criteria. We keep specs for
  complex tickets.

## 2026-10-06 · #83 Brand colors and dark mode

**Task given to AI:** replace daisyUI's default black-and-white light theme with our own
construction-coloured theme, in a light and a dark variant; dark must follow the phone's
setting, text and buttons must pass WCAG AA contrast. I asked to see the colour proposals
running, not only as hex codes.

**AI helped:** proposed three palettes with computed WCAG contrast for every pair, then ran
three dev servers side by side (ports 8001–8003, one CSS build each, nothing changed in the
repo) so I could compare them in both themes. Explained the difference between hand-written
CSS variables and daisyUI's theme plugin when I could not choose. Before writing tests it
built a probe theme to see the real CSS daisyUI generates, and found that the plugin does not
fill in missing variables (no `--radius-box` at all), so every theme sets all 28. Wrote 30
tests: unit tests that compute the WCAG formula from `input.css` (after checking the formula
itself against known values) and integration tests on the built `app.css`.

**AI failed:**
- It first recommended hand-written CSS variables because they matched the ticket's wording
  ("no new dependency"). When I asked what is better for the whole app, it changed its
  recommendation to the theme plugin.
- The desktop header from #10 (plain-text menu row when logged in, real buttons when logged
  out) looked inconsistent; AI had not noticed it. I found it while checking the pages.

**I overruled:**
- AI recommended palette B (yellow + charcoal, highest contrast). I chose C (navy + safety
  orange): I liked it more and it looks more solid.
- For the header AI suggested turning the desktop links into buttons. I decided to use the
  phone's dropdown menu on every screen width instead, so it is the same everywhere. It is a
  separate ticket (#103), not part of #83.

**Learned:**
- How `prefers-color-scheme` switches the theme in the browser, without JavaScript or server
  code.
- What WCAG contrast 4.5:1 means and how it is computed.

## 2026-10-07 · #11 Worker profile: team size, skills, languages, legal status

**Task given to AI:** build the worker profile from the plan (team size, skills, languages,
legal status, district) with a spec first, like #10. I asked to discuss the skill storage and
the district in more detail before deciding.

**AI helped:** offered every open question with options and a recommendation, and explained the
trade-offs: skills in code (`TextChoices` + PostgreSQL `ArrayField`, translated by `.po` files)
vs. a database table; how a district list would work with the future map (#41, #42). Wrote the
spec `docs/specs/worker-profile.md` (R1–R9, AC1–AC13, my decisions D1–D8), 29 failing unit
tests, the model with a database `CheckConstraint` for team size 1–10, two forms on one page
saved in one transaction, a read-only profile card without contact details (for employers in
#23), 403 for other roles, the admin inline and 25 integration tests. It checked one of its own
tests by breaking the code on purpose.

**AI failed:**
- A comment in the edit view said `all([...])` was needed so both forms show their errors. The
  mutation check (replacing it with `and`) showed the test still passed: `form.errors`
  validates by itself on first use. The comment was corrected.
- Its skill name "Drywall / plastering helper" did not fit one line on a phone, and the profile
  page did not handle a long name without spaces (the page scrolled sideways). I found both
  while trying the form in the browser.
- It rebuilt the CSS without `--minify`, and two theme tests from #83 failed. It found the
  cause: those tests only match minified CSS, while the dev command (`--watch`) is not
  minified. Posted as an open question in #94.

**I overruled:**
- AI planned a district for workers (from the plan) and recommended "one home district". I
  asked what it is for: "if a person applied for a job, they already know how far it is and
  they agree". No feature needed it, so we dropped it (GDPR data minimisation). The district
  list moves to the job (#15).
- I split "drywall / plastering helper" into two skills and added "bricklayer's helper": "if
  someone lays bricks, I think they may need a helper".
- On a phone the profile showed each label above its value; I asked for one line, label and
  value side by side.
- I changed the ticket workflow: draft PR and CI first, then the "Done when…" items are ticked
  without asking again, then `/ai-log`. I want to see CI first: if it fails on GitHub for some
  reason, I can still fix it, and the AI_LOG commit stays the last one.

**Learned:**
- Why team size is checked in the form *and* in the database.
- Why the card employers will see has no phone or email.

## 2026-10-07 · #12 Employer profile

**Task given to AI:** build the employer profile (company or personal name, trade) with a short
spec first, in the same pattern as the worker profile (#11). I asked to discuss how to store
the trade before deciding.

**AI helped:** compared a fixed trade list with free text (translation by `.po` files, typos,
where the trade is used) and proposed 15 trades, including "private person" and "other". Wrote
the spec `docs/specs/employer-profile.md` (R1–R11, AC1–AC11, my decisions D1–D3), 16 failing
unit tests, the `EmployerProfile` model and form, the two pages, the admin inline and 23
integration tests. Instead of copying the worker views it moved the shared parts into
`RoleRequiredMixin`, `ProfileView` and `ProfileEditView`; the #11 tests passed unchanged.
Drafted six comments for the M2 docs sync (#94) and the PR.

**AI failed:**
- The employer page used the company name as its title. daisyUI's `card-title` is a flex box,
  so a long name without spaces ran out of the page on a phone. I found it in the browser; the
  first fix (`wrap-anywhere`) was replaced when I compared the two profile pages (see below).
- "Private person / own renovation" did not fit its badge on a phone. I found it in the browser.
- It rebuilt the CSS without `--minify` again, and the two theme tests failed again — the same
  open question as in #11 (already in #94).

**I overruled:**
- AI recommended one trade per employer; I chose several: one firm can work in related trades.
- I added an idea: users should be able to get missing trades added (through support or
  another way). Recorded in #94, not built.
- I found that `/accounts/` and `/accounts/profile/` give 404. AI recommended fixing it in this
  branch and started; I rolled it back and moved it to #94: it is not part of this ticket.
- I asked AI to compare the worker and employer models and forms. They matched, but the pages
  did not: the employer title showed the company name (twice on the page). I made the title
  "My company", like "My profile" for workers, and dropped the `wrap-anywhere` fix.
- I shortened "private person / own renovation" to "private person"; long names in other
  languages are revisited in M5.
- AI wrote "the student" in the #94 comments and the PR. I asked for the first person instead
  ("I chose…"): they are posted from my account.

**Learned:**
- Why a flex title does not wrap a long word, while a grid cell with `min-w-0` does.
- Why changing a choice label needs no new migration when the migration is not shared yet.
