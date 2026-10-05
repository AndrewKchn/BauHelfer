# Plan: BauHelfer — ReDi School final project

## Context

Munich has a lot of construction sites. Specialists (window fitters, plasterers, etc.) often need
general labourers for a day or two: clearing debris, demolition, carrying materials. **BauHelfer** is a
web app where an employer posts a job and individual workers or small crews apply.

This is the final project for the course "Development with AI": Claude writes the code, the student
reviews it, makes the decisions and defends the project. Timeline: 2 months, full-time
(≈ 5 Oct – 1 Dec 2026). The school has no stack requirements. The student is new to Django, so Claude
explains each part as it is built, and key decisions are recorded in `docs/AI_LOG.md`.

The repository, labels, milestones, issues and project board are set up; application code is
written issue by issue.

## Stack

| Part | Choice | Why |
|---|---|---|
| Backend | **Python 3.12 + Django 5** | Built-in auth, form validation, ORM, migrations, admin and i18n — everything BauHelfer needs. Fastest path to a working result |
| Frontend | **Django templates + HTMX 2 + Tailwind CSS 4 + daisyUI 5** | The whole project stays in Python with minimal JavaScript. HTMX adds interactivity (filters, applications, chat). Tailwind gives a mobile-first layout. Decided in #3: **daisyUI** on top of Tailwind (short classes like `btn`, no own JS, so no clash with HTMX; Flowbite and plain Tailwind rejected). Own colour theme with dark mode in #83. Tailwind is **built** by the standalone CLI via `pytailwindcss` (no Node.js), not loaded from a CDN: smaller CSS, no flash of unstyled page, and no visitor IPs sent to a CDN (GDPR). **HTMX 2.0.10**, not the new 4.0 (released Aug 2026): far more docs and examples. HTMX and daisyUI are downloaded files in the repo, served by WhiteNoise |
| Database | **PostgreSQL**: Docker locally, **Supabase** (Frankfurt, free plan) in production | Django standard, same engine everywhere. Supabase instead of a Render database: Render's free database expires after 30 days, Supabase's does not (it pauses after 7 days without activity). Only plain PostgreSQL is used, via the Session pooler; Data API off, RLS on |
| Text translation | **Claude API** (`claude-haiku-4-5`) | Handles construction slang and context; translations are cached in the DB |
| Map | **Leaflet + OpenStreetMap**, Nominatim geocoding | Free, no API keys |
| Job photos | **Cloudflare R2** (EU jurisdiction) via `django-storages` + `boto3`; **Pillow** for validation, resizing and EXIF stripping | The Render disk is wiped on every deploy. R2 is S3-compatible, free up to 10 GB with free egress, data stays in the EU, and the app stays stateless (can run several instances) |
| Chat | HTMX polling every 3–5 s | Simpler than WebSockets, enough for the MVP |
| Tests / quality | **pytest-django**, **ruff**, **Allure Report 3** | Decided in #89: an Allure report (GitHub Pages) groups tests by level and by story, with a readable title and steps from each test's docstring, like test cases in Jira. Issue titles come from GitHub at CI time |
| CI | **GitHub Actions**: ruff, pytest, coverage on every PR; required to merge into `main` | |
| Hosting | **Render, Frankfurt region** (web service), **gunicorn**, static files via **WhiteNoise**; `render.yaml` Blueprint | Auto-deploy from `main` after CI is green, data stays in the EU (GDPR). Free plans only, also for the defense — a learning project. The server sleeps after 15 min without traffic (first request then takes up to a minute) |

**Deploy from week one:** after M1 the project has a live version, and every merge to `main` updates the site.

## Data model (core)

- **User** (custom): email, name, phone, `role` = employer | worker, `preferred_language`,
  `work_permit_confirmed` ("I am allowed to work in Germany").
- **WorkerProfile**: `team_size` (1 = individual, >1 = crew), skills (demolition, cleanup, carrying…),
  languages, `legal_status` = Gewerbe | Minijob | employed, district.
- **EmployerProfile**: company / name, trade.
- **Job**: employer, job type, description, `original_language`, address / district, coordinates,
  date and hours, number of workers, hourly rate in € (≥ `MINIMUM_WAGE = 13.90`),
  status open | filled | done | cancelled.
- **JobPhoto**: job, image, uploaded_at; up to 5 per job, resized to max 1600 px, EXIF removed.
- **Application**: job, worker, message, `workers_offered`, status pending | accepted | rejected.
- **Translation**: translation cache (source text hash + language → translated text).
- **Message**: chat within an accepted application.
- **Review**: rating 1–5 + text, after status done, in both directions.

In the MVP a crew is a single account with a `team_size` field; full crews with members are a stretch goal.

## Project structure (planned)

```
BauHelfer/
├── config/            # Django settings
├── accounts/          # User, profiles, registration
├── jobs/              # Job, Application
├── chat/              # Message
├── reviews/           # Review
├── translations/      # Claude API service + cache
├── templates/  static/  locale/
├── docs/PLAN.md  docs/AI_LOG.md  docs/SECURITY.md
├── CLAUDE.md  .claude/skills/ai-log/   # instructions and /ai-log skill for Claude Code
├── docker-compose.yml  pyproject.toml  render.yaml  .github/workflows/ci.yml
```

## Labels

`backend`, `frontend`, `database`, `i18n`, `ai`, `legal`, `devops`, `testing`, `docs`, `stretch`
(+ default `bug` and `enhancement`; other default labels are removed).

## Milestones and issues (71)

Each issue has a **Description** and a **Done when…** checklist. Numbers are GitHub issue numbers;
the status of each issue lives on the board, not here.

### M1 · Foundation & First Deploy — due 11 Oct
- #1 Set up Django project structure and settings (`backend`)
- #8 Custom User model with role (employer / worker) (`backend`, `database`) — must exist before
  the first `migrate` on PostgreSQL in #2
- #2 PostgreSQL via Docker Compose + env config (`devops`, `database`)
- #4 GitHub Actions CI: ruff, pytest, coverage (`devops`, `testing`) — also makes the CI check
  required in the "Protect main" ruleset
- #5 First deploy to Render (Frankfurt): gunicorn, WhiteNoise, auto-deploy from `main` (`devops`)
- #6 README: project idea, stack, how to run locally, live link (`docs`)
- #7 Start `docs/AI_LOG.md` — log of AI-assisted decisions (`docs`)
- #56 Protect main branch (`devops`)
- #58 Development guardrails: `CLAUDE.md` and `/ai-log` skill (`devops`, `docs`)
- #59 Sync `docs/PLAN.md` with board changes (`docs`)

### M2 · Accounts & Profiles — due 18 Oct
- #3 Base layout template with Tailwind + HTMX, mobile-first (`frontend`)
- #79 Mark downloaded daisyUI and HTMX files as vendored (`docs`)
- #9 Registration, login, logout, password reset (`backend`, `frontend`)
- #10 Role selection and onboarding flow (`frontend`)
- #11 Worker profile: team size, skills, languages, legal status (`backend`, `frontend`)
- #12 Employer profile (`backend`, `frontend`)
- #13 Work-permit confirmation checkbox at signup (`legal`)
- #83 Brand colors and dark mode: own daisyUI theme, light + dark by device setting (`frontend`)
- #85 Fix misleading trigger comment in CI workflow (`devops`)
- #88 Security notes: `docs/SECURITY.md` (`docs`, `legal`)
- #89 Allure test report: tests grouped by story (`testing`, `devops`) — before #10
- #14 E2E tests (Playwright) and coverage review for M2 (`testing`)
- #74 Staging environment on free plans (`devops`, `stretch`) — optional, before M3

### M3 · Jobs — due 25 Oct
- #15 Job model and migrations (`database`)
- #16 Create / edit / cancel job (employer) (`backend`, `frontend`)
- #64 Job photos: up to 5 per job, resize, strip EXIF, Cloudflare R2 storage (`backend`,
  `frontend`, `devops`, `legal`) — after #16 and #5
- #17 Minimum-wage validation (13.90 €/h) (`backend`, `legal`)
- #18 Job list with filters: date, job type, district (HTMX) (`frontend`)
- #19 Job detail page (`frontend`)
- #20 Employer dashboard "My jobs" (`frontend`)
- #21 E2E tests (Playwright) and coverage review for M3 (`testing`)

### M4 · Applications — due 1 Nov
- #22 Apply to job (worker) with message and number of workers (`backend`, `frontend`)
- #23 Employer views applications per job (`frontend`)
- #24 Accept / reject application; job becomes "filled" when enough workers (`backend`)
- #25 Reveal contacts to both sides after acceptance (`backend`, `legal`)
- #26 Worker dashboard "My applications" (`frontend`)
- #27 Email notifications: new application, accepted / rejected (`backend`)
- #81 Email verification at signup (`backend`) — after #27, needs real email sending
- #28 E2E tests (Playwright) and coverage review for M4 (`testing`)

### M5 · Multilingual & AI Translation — due 8 Nov
- #29 Django i18n setup + language switcher (DE, EN, RU, UK, PL, RO, TR) (`i18n`)
- #30 Translate all existing UI strings from M2–M4 (`i18n`)
- #31 Claude API translation service with DB cache (`ai`, `backend`)
- #34 Error handling and cost limits for the AI service + tests with mocked API (`ai`, `testing`)
  — done before the features that use the service (#32, #33, #36)
- #32 Auto-translate job descriptions, "show original" toggle (`ai`, `frontend`)
- #33 Auto-translate application messages (`ai`)

### M6 · Chat & Reviews — due 15 Nov
- #35 Chat per accepted application (HTMX polling) (`backend`, `frontend`)
- #36 Auto-translation of chat messages (`ai`)
- #37 Mark job as done (`backend`)
- #38 Reviews and ratings in both directions (`backend`, `frontend`)
- #39 Show rating on profiles and applications (`frontend`)
- #40 E2E tests (Playwright) and coverage review for M6 (`testing`)

### M7 · Map, Legal & GDPR — due 22 Nov
- #41 Geocode job address (Nominatim) (`backend`)
- #42 Job map with Leaflet + "near me" filter (`frontend`)
- #43 Impressum, privacy policy, platform disclaimer pages (`legal`, `docs`)
- #44 Account deletion and personal-data export (GDPR) (`legal`, `backend`)
- #45 Admin panel for moderation: block user, remove job (`backend`)
- #91 Login rate limiting: slow down password guessing (`backend`, `legal`, `stretch`)

### M8 · Production & Defense — due 1 Dec
- #46 Demo readiness on free plans: wake-up, Supabase not paused, manual backup (`devops`)
- #47 Demo seed data: employers, workers, jobs (`backend`)
- #48 Mobile and accessibility check, fix issues (`frontend`)
- #49 End-to-end manual test scenario, fix bugs (`testing`)
- #50 Final docs: architecture diagram, AI_LOG summary (`docs`)
- #51 Defense presentation and demo script (`docs`)

### Stretch (no due date)
- #52 Real crews: crew leader invites members (`stretch`)
- #53 Push / browser notifications for nearby jobs (`stretch`)
- #54 Real-time chat via WebSockets (Django Channels) (`stretch`)
- #55 Worker availability calendar (`stretch`)
- #73 Error monitoring on production with Sentry (`stretch`)
- #75 Modern admin theme with django-unfold (`frontend`, `stretch`)
- #84 Logo, icons and images (`frontend`, `stretch`) — after the main features
- #82 Sign in with Google (`backend`, `legal`, `stretch`) — only if time is left; new dependency

## Testing approach

Tests are part of every feature ticket, not separate tickets.

1. **Unit tests first (TDD).** Written before the code, read by the student, committed failing
   ("Add failing tests for …").
2. **Implementation** until the unit tests pass.
3. **Integration tests** with the Django test client (view + form + DB) for the main flow.
4. **E2E tests (Playwright)** once per milestone, in the milestone test tickets #14, #21, #28,
   #40, together with a coverage review.

CI (#4) runs ruff and pytest, fails below 80 % test coverage and 80 % docstring coverage, and is
required to merge into `main`. #49 is the final manual end-to-end scenario before the defense.

## Translation approach

Translations are done inside each UI ticket, not in one late batch.

- **From M2:** every UI string is wrapped in translation functions (`{% translate %}`,
  `gettext_lazy`).
- **#29 (M5)** sets up i18n and adds a CI check that fails on untranslated or fuzzy strings.
- **#30** translates all strings written in M2–M4 into the 7 languages.
- **From M5 on:** every UI ticket translates its own strings into all 7 languages.

User content (job descriptions, application and chat messages) is translated by the Claude API
(#31–#34, #36), not by `.po` files.

## Board and workflow

Board: [BauHelfer](https://github.com/users/AndrewKchn/projects/1), columns Todo / In Progress / Done.

- **Sprints:** Iteration field "Sprint", one iteration per milestone with the same dates. The
  Roadmap view uses it as the timeline. New issues get a Sprint too.
- **Dependencies:** issues are linked with "blocked by". The filter `-is:blocked` shows what can
  be started now.
- **Ticket workflow** (details in `CLAUDE.md`): branch linked to the issue → In Progress →
  failing tests, code, integration tests as separate commits → AI_LOG entry drafted with
  `/ai-log` as the last commit → PR with `Closes #N` → the student
  merges. Board automation closes the issue and moves it to Done.
- **`main` is protected** (ruleset "Protect main"): changes only through PRs, no force push, no
  deletion, no bypass. Squash merge is disabled — PRs are merged with a merge commit, so the
  separate commits stay in the history. Merged branches are deleted automatically.

## Verification

- `gh label list` — 12 labels; `gh api repos/AndrewKchn/BauHelfer/milestones --jq '.[].title'` — 9 milestones.
- `gh issue list --state all --limit 100 --json number --jq length` → 70; every issue has a
  milestone and a label.
- `gh project item-list 1 --owner AndrewKchn` — all issues are on the board, each non-Stretch
  issue has a Sprint.
- `gh api repos/AndrewKchn/BauHelfer/rules/branches/main --jq '.[].type'` — `deletion`,
  `non_fast_forward`, `pull_request` (+ the required CI check after #4).
- The milestone lists above match the board.
