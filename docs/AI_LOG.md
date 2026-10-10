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

**My part:** suggestions I rejected or changed and why, my own ideas, and how I checked the
result by hand.

**Learned:** what I now understand and can explain.
```

Sessions without a ticket (planning, process) use `Planning:` instead of `#N`. Entries before
#109 use **I overruled:** instead of **My part:**; they stay as they are.

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

## 2026-10-07 · #103 Header: same dropdown menu on desktop as on phone

**Task given to AI:** pick a small next ticket after #12, then build #103: show the logged-in
links in the phone's dropdown menu on every screen width (my decision from #83).

**AI helped:** compared three small M2 tickets (#85, #103, #13) and recommended #103. Showed
how the header worked (two copies of the links through `_nav_links.html`, a hidden logout form
submitted by two buttons) and offered three options for the partial and the form. When I asked,
explained in detail why the partial and the hidden form existed and why both stop being needed
with one menu. Wrote two failing tests (each link appears once, the dropdown has no `*hidden`
class, the "Log out" button sits inside the POST form), the new header, and three comments
for #94.

**AI failed:** after moving "Log out" into a form, daisyUI styled the form as the menu item:
the whole row lit up on hover, but only the text was clickable. AI found it by reading
daisyUI's CSS rule before I tried it, and fixed it with `block p-0` on the form and padding on
the button.

**I overruled:** nothing this time — I asked for a fuller explanation of the options, then
chose the recommended one (no partial, logout form inside the menu item).

**Learned:**
- Why logout must be a POST form with a CSRF token, not a link.
- Why a daisyUI rule inside `:where()` loses to a Tailwind utility class.

## 2026-10-08 · #13 Work-permit confirmation checkbox at signup

**Task given to AI:** update `main` and explain the catch in #13, then build it with a spec
first.

**AI helped:** found three catches before any code. (1) At signup there is no role yet (#10),
so a checkbox "for workers" cannot be there. (2) The model had only a boolean, no date.
(3) There is no apply view until #22. For each it offered options with a recommendation.
Wrote the spec `docs/specs/work-permit.md` (decisions D1–D7) and failing tests, including the
first migration test in the project: Django's `MigrationExecutor` moves the database back,
creates old data, migrates forward and checks it. Then wrote the code: one date field instead
of the boolean, a hand-written migration (add the field → copy the data with `RunPython`
→ remove the old field, reversible), `WorkerUserForm`, `User.can_apply()` for #22, the
display on the profile page and card, and the admin field. Also drafted Docs sync comments
and suggested moving the "cannot apply" check into #22's "Done when…".

**AI failed:** one failing test passed by mistake (`test_saving_again_keeps_the_first_date`):
`refresh_from_db()` does not reset an attribute that is not a model field yet. AI noticed it
in the failing-tests run and changed the test to read the user from the database again.

**I overruled:** nothing this time. I chose the recommended option for every question:
checkbox in the worker profile, not at signup; one date field; `can_apply()` now and the view
check in #22; the checkbox in a `WorkerUserForm`; keep the first date; employers see only
"confirmed"; a data migration that keeps existing confirmations. Why not at signup: I wrote
the issue early, when it was not clear yet where the checkbox belongs. While building it, it
became clear that it concerns only workers, so it belongs in the worker profile form.

**Learned:**
- Why one date field is better than a boolean + a date.
- What a data migration with `RunPython` and the historical model `apps.get_model` does.

## 2026-10-08 · #85 CI and deploy triggers: fix comment, skip Render deploys for docs-only changes

**Task given to AI:** update `main`, delete the old local branch, then do #85.

**AI helped:** deleted the merged branch of #103 (PR #107). Rewrote the first comment in
`ci.yml`: CI runs on pull requests and on pushes to `main`, not on every push, and the
`push: main` run stays because it checks the merged result and Render deploys only after the
checks on that `main` commit pass (`autoDeployTrigger: checksPass`). Added a `buildFilter`
with `ignoredPaths` to `render.yaml`. Before I chose, it listed the extra files that do not
change the site and explained the one risk of the filter: a wrongly ignored file means the
site does not update. It checked that no site code imports from `tests/`.

**AI failed:** nothing notable.

**I overruled:** nothing this time. I chose the recommended option for every question:
seven extra dev-only files in the filter (`conftest.py`, `allurerc.json`,
`docker-compose.yml`, `.pre-commit-config.yaml`, `.env.example`, `.gitignore`,
`.gitattributes`); no unit test for `render.yaml`; the `docs/PLAN.md` title change goes to
Docs sync M2 (#94), not this ticket. No test because I did not want to add a dependency
(`pyyaml`) for one check; I will check it by hand: Render should show "skipped" on the next
docs-only merge.

**Learned:**
- Why CI runs again on `main` after the PR was green.
- How `ignoredPaths` decides: a deploy is skipped only if every changed file matches.

## 2026-10-08 · #109 Phone number accepts any text

**Task given to AI:** do #109, which I opened while testing #13: the phone field accepted any
text, but employers will call this number after accepting an application (#25). The rule
was already in the issue: a number callable from a mobile phone, `+` and a country code or
`0` and a German area code, 10–15 digits, no new dependency.

**AI helped:** wrote `validate_phone` (a short regex for the start and the allowed characters,
plus a separate digit count) and put it on the `User.phone` model field, so both profile forms
and the admin use it; the migration only changes the field description, no SQL. Explained why
`[0-9]` and not `\d` (Python's `\d` also matches Arabic digits) and why `type="tel"` is only
convenience, not validation. Wrote 27 unit tests first, then 7 integration tests that run for
both roles and check the admin. Found two old tests from #13 that saved "+49 170 1" (5 digits)
and fixed them. When I asked what happens to wrong numbers already in the database, it
explained that a validator only runs when a form is saved, so old rows stay, and how to handle
this with real users: count first, fix only unambiguous numbers in a data migration, ask users
to correct the rest, never delete silently, add a database constraint last.

**AI failed:** it first put the `type="tel"` widget in `Meta.widgets`; ruff rejected it (RUF012,
a mutable dict on the class), so it moved it to `__init__`, like `team_size`.

**My part:**
- AI recommended rejecting "+49 (0) 151 …". I did not add a rule for it: I have not seen
  numbers written like that in Germany, people write either +49… or 0…. Such a number
  passes; it is noted as a known limitation in #94.
- I first agreed to a placeholder "+49 151 12345678", then changed it to a hint under the field
  ("For example +49 151 12345678 or 0151 12345678."): a bare number in the field does not
  say that it is an example.
- I checked the result by hand locally, on a laptop and on a phone, as a worker and as an
  employer: a wrong number shows the error, a valid one is saved as typed, the phone opens
  the number keyboard.

**Learned:**
- Why a validator on the model also protects the admin, but not the rows already in the
  database.
- Why a migration appears even though the database does not change.
- How I would clean up wrong numbers if real users already had them.

## 2026-10-09 · #14 E2E tests (Playwright) and coverage review for M2

**Task given to AI:** do #14, the first E2E ticket: set up Playwright with Django's
`live_server`, add a CI step for the browser, cover the M2 flows (register → role → profile,
login / logout, password reset), review coverage, decide the test folder layout and write
`docs/TESTING.md`.

**AI helped:** set up `pytest-playwright` and found that Django refuses database calls next
to Playwright's event loop (`SynchronousOnlyOperation`); the fix, `DJANGO_ALLOW_ASYNC_UNSAFE`,
is set only in `tests/e2e/conftest.py`. Wrote 4 E2E tests and checked them by breaking the code
on purpose: without `{% csrf_token %}` in the logout form the test fails with "CSRF verification
failed", a 500 px block makes the phone test fail with "180px wider than the screen". Turned
on branch coverage; it found two untested branches, now tested (100 % lines and branches).
When I said the tests got too slow, it measured and found the cause: PBKDF2 takes 0.7 s per
password, so it switched tests to an MD5 hasher (full run ~2 min → ~30 s). Compared CI logs
before and after `--only-shell`.

**AI failed:**
- An E2E test matched "Name" and "Company name" at once (`exact=True` was missing).
- It first credited `--only-shell` for the faster CI; the logs showed most of the 3.5 minutes
  was a slow Ubuntu mirror (`apt`), which the flag does not fix.

**My part:**
- AI suggested a phone-width test for the worker only. I asked why only the worker, then
  chose one signup flow per device: the worker on a 360 px phone, the employer on a laptop,
  instead of a separate phone test for both roles. This way similar flows cover both the
  laptop and the phone view, and a worker is more likely to use a phone. Employers will use
  phones too; that case will be checked in the ticket where they create jobs.
- I did not accept the slower tests (E2E 11 s → 27 s) and asked to re-check; that is how the
  slow password hasher was found. I asked for a unit test that production still uses PBKDF2.
- I asked to add `test-results/` to `.gitignore` (Playwright traces hold the typed passwords).
- I watched every E2E flow in the browser with `--slowmo 500`, replayed them in the Trace
  Viewer and read the CI logs on GitHub.

**Learned:**
- Nothing new about Playwright itself: I had used it before.

## 2026-10-10 · #94 Docs sync — M2

**Task given to AI:** do the first "Docs sync" ticket with `/sprint-docs`: handle the 38
comments collected in #94 during M2, check `docs/PLAN.md`, `CLAUDE.md`, `docs/SECURITY.md` and
`README.md` against the board and the code, and propose for each comment: into a doc, a new
issue, or rejected.

**AI helped:** checked every test, class and file named in the comments with grep before
proposing them for `SECURITY.md` (all exist). Counted the issues: the board had 81, PLAN.md
listed 71. Found what #14 had already done (the 360 px check) and which comments the later
ones had made out of date (`_nav_links.html`, removed in #103). Drafted the changes as a table
plus before → after per doc. When I asked about the theme tests, it built `app.css` with and
without `--minify` and showed the difference. That is how it found that
`test_built_css_has_no_builtin_daisyui_themes` always passes on unminified CSS: the test could
not fail. After my "yes" it edited 5 docs, created #113–#115, added notes and "Done when…"
lines to 11 future issues and answered all 38 comments with the commit or issue.

**AI failed:** nothing notable. It checked the `CLAUDE.md` commands by reading them and by the
green CI run, not by running each one.

**My part:**
- I accepted the recommendations for renaming #13 (the checkbox is in the worker profile, not
  at signup), for turning two ideas into Stretch issues (#114, #115) and for putting notes for
  later tickets into those issues instead of PLAN.md: whoever starts #22 opens #22 and sees
  the note there; in PLAN.md it would have to be looked for.
- On the theme tests I asked for a fuller explanation before deciding. I chose to fix the test
  (#113, M3), not to add `--minify` to the watch command: the cause of the bug is in the
  test, so it has to be fixed, not hidden.
- "My part" instead of "I overruled" was my idea from #109; now it is the entry format and
  the `/ai-log` skill uses it.

**Learned:**
- Why a test that cannot fail is worse than a red one: it looks like protection but checks
  nothing.
- Why sprint notes go into the issue that needs them.

## 2026-10-10 · Planning: AI_LOG review

**Task given to AI:** after merging #94 I asked AI to go through the closed issues for
unticked "Done when…" items, then to review the whole AI_LOG: are the steps of the process
logical, and does it look as if AI did everything and I did not take part? I have not written
a line of code myself.

**AI helped:** confirmed with the CI and deploy history that the docs-only merge of #94 did
not deploy (CI green on `main`, no new Render deploy; #14 had deployed 2 minutes after its
CI). Found unticked items in six closed issues, ticked those with evidence (#7, #58, #59, #88)
and raised two without it (#13, #58). The review listed what is clearly mine in the log
(product decisions, overruled recommendations, bugs I found by hand) and its weak spots:
repeated AI mistakes that were only logged, not fixed (the theme tests and `--minify` came up
three times before #113); a lot of process work compared to features; sprint dates on the
board that do not match the real pace; and entries where I accepted every recommendation
without saying why.

**AI failed:**
- In #85 it promised that Render would show "skipped" for a docs-only merge. Render shows
  nothing; the only evidence is that no deploy appeared. I found it on Render after the merge.
- It added a "Done when…" line to #22 without reading the list first. The same item was
  already there, so I had to remove the duplicate.

**My part:**
- I asked for the review and the question "does it look like I did nothing?" myself.
- Instead of waiting for an AI_LOG entry as proof for #85, I posted a comment with a
  screenshot of the GitHub deployments.
- For #58 (strike through the dropped "AI usage" part) and #13 (leave "cannot apply"
  unticked, the check moves to #22) I accepted the recommendations: the options were small
  and the recommendation matched what I wanted.
- AI suggested that I write #113 myself. I postponed it to the end of the sprint: the review
  showed that the process now outweighs development, so I need to work on features.

**Learned:**
- The process now takes more time than the product; M3 should focus on features.

## 2026-10-10 · #117 /ai-log: ask why when every recommendation was accepted

**Task given to AI:** make `/ai-log` ask for the reason when I accepted every recommendation.
This came out of the AI_LOG review (see the previous entry).

**AI helped:** created #117 and wrote one rule in `.claude/skills/ai-log/SKILL.md`: if I
accepted every recommendation, the draft does not say only "I chose the recommended option"
but leaves `TODO: why you accepted them` and asks me. The first run was this entry's draft.

**AI failed:** in the review it first counted #13 among the "small" tickets. In fact #13 had a
spec, seven decisions and a data migration.

**My part:**
- I pointed out that the tickets where I accepted everything were small, but that this is
  not obvious from the log. This ticket came out of it.
- I accepted the wording of the rule: the options were small and the recommendation matched
  what I wanted.

**Learned:**
- Why accepting every recommendation needs a reason in the log, too.
