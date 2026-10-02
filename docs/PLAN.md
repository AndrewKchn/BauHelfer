# Plan: BauHelfer — ReDi School final project

## Context

Munich has a lot of construction sites. Specialists (window fitters, plasterers, etc.) often need
general labourers for a day or two: clearing debris, demolition, carrying materials. **BauHelfer** is a
web app where an employer posts a job and individual workers or small crews apply.

This is the final project for the course "Development with AI": Claude writes the code, the student
reviews it, makes the decisions and defends the project. Timeline: 2 months, full-time
(≈ 5 Oct – 1 Dec 2026). The school has no stack requirements. The student is new to Django, so Claude
explains each part as it is built, and key decisions are recorded in `docs/AI_LOG.md`.

The `Projects/ReDi` folder is currently an empty git repository with no remote. Goal of this step:
fix the stack and architecture, split the work into milestones, and create the GitHub repository,
labels, milestones, issues and project board. Application code is written later, issue by issue.

## Stack

| Part | Choice | Why |
|---|---|---|
| Backend | **Python 3.12 + Django 5** | Built-in auth, form validation, ORM, migrations, admin and i18n — everything BauHelfer needs. Fastest path to a working result |
| Frontend | **Django templates + HTMX + Tailwind CSS** | The whole project stays in Python with minimal JavaScript. HTMX adds interactivity (filters, applications, chat). Tailwind gives a mobile-first layout |
| Database | **PostgreSQL** (Docker locally) | Django standard, same engine in production |
| Text translation | **Claude API** (`claude-haiku-4-5`) | Handles construction slang and context; translations are cached in the DB |
| Map | **Leaflet + OpenStreetMap**, Nominatim geocoding | Free, no API keys |
| Chat | HTMX polling every 3–5 s | Simpler than WebSockets, enough for the MVP |
| Tests / quality | **pytest-django**, **ruff** | |
| CI | **GitHub Actions**: ruff + pytest on every PR | |
| Hosting | **Render, Frankfurt region** (web service + PostgreSQL), **gunicorn**, static files via **WhiteNoise** | Auto-deploy from `main`, data stays in the EU (GDPR). Free tier during development, paid tier for the defense |

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
├── docs/PLAN.md  docs/AI_LOG.md
├── docker-compose.yml  pyproject.toml  render.yaml  .github/workflows/ci.yml
```

## Labels

`backend`, `frontend`, `database`, `i18n`, `ai`, `legal`, `devops`, `testing`, `docs`, `stretch`
(+ default `bug` and `enhancement`; other default labels are removed).

## Milestones and issues (55)

Each issue has a **Description** and a **Done when…** checklist.

### M1 · Foundation & First Deploy — due 11 Oct
- Set up Django project structure and settings (`backend`)
- PostgreSQL via Docker Compose + env config (`devops`, `database`)
- Base layout template with Tailwind + HTMX, mobile-first (`frontend`)
- GitHub Actions CI: ruff + pytest (`devops`, `testing`)
- First deploy to Render (Frankfurt): gunicorn, WhiteNoise, auto-deploy from `main` (`devops`)
- README: project idea, stack, how to run locally, live link (`docs`)
- Start `docs/AI_LOG.md` — log of AI-assisted decisions (`docs`)

### M2 · Accounts & Profiles — due 18 Oct
- Custom User model with role (employer / worker) (`backend`, `database`)
- Registration, login, logout, password reset (`backend`, `frontend`)
- Role selection and onboarding flow (`frontend`)
- Worker profile: team size, skills, languages, legal status (`backend`, `frontend`)
- Employer profile (`backend`, `frontend`)
- Work-permit confirmation checkbox at signup (`legal`)
- Tests for accounts and profiles (`testing`)

### M3 · Jobs — due 25 Oct
- Job model and migrations (`database`)
- Create / edit / cancel job (employer) (`backend`, `frontend`)
- Minimum-wage validation (13.90 €/h) (`backend`, `legal`)
- Job list with filters: date, job type, district (HTMX) (`frontend`)
- Job detail page (`frontend`)
- Employer dashboard "My jobs" (`frontend`)
- Tests for jobs (`testing`)

### M4 · Applications — due 1 Nov
- Apply to job (worker) with message and number of workers (`backend`, `frontend`)
- Employer views applications per job (`frontend`)
- Accept / reject application; job becomes "filled" when enough workers (`backend`)
- Reveal contacts to both sides after acceptance (`backend`, `legal`)
- Worker dashboard "My applications" (`frontend`)
- Email notifications: new application, accepted / rejected (`backend`)
- Tests for applications (`testing`)

### M5 · Multilingual & AI Translation — due 8 Nov
- Django i18n setup + language switcher (DE, EN, RU, UK, PL, RO, TR) (`i18n`)
- Translate UI strings into all languages (`i18n`)
- Claude API translation service with DB cache (`ai`, `backend`)
- Auto-translate job descriptions, "show original" toggle (`ai`, `frontend`)
- Auto-translate application messages (`ai`)
- Error handling and cost limits for the AI service + tests with mocked API (`ai`, `testing`)

### M6 · Chat & Reviews — due 15 Nov
- Chat per accepted application (HTMX polling) (`backend`, `frontend`)
- Auto-translation of chat messages (`ai`)
- Mark job as done (`backend`)
- Reviews and ratings in both directions (`backend`, `frontend`)
- Show rating on profiles and applications (`frontend`)
- Tests for chat and reviews (`testing`)

### M7 · Map, Legal & GDPR — due 22 Nov
- Geocode job address (Nominatim) (`backend`)
- Job map with Leaflet + "near me" filter (`frontend`)
- Impressum, privacy policy, platform disclaimer pages (`legal`, `docs`)
- Account deletion and personal-data export (GDPR) (`legal`, `backend`)
- Admin panel for moderation: block user, remove job (`backend`)

### M8 · Production & Defense — due 1 Dec
- Production setup: paid Render plan, persistent DB, backups, optional custom domain (`devops`)
- Demo seed data: employers, workers, jobs (`backend`)
- Mobile and accessibility check, fix issues (`frontend`)
- End-to-end manual test scenario, fix bugs (`testing`)
- Final docs: architecture diagram, AI_LOG summary (`docs`)
- Defense presentation and demo script (`docs`)

### Stretch (no due date)
- Real crews: crew leader invites members (`stretch`)
- Push / browser notifications for nearby jobs (`stretch`)
- Real-time chat via WebSockets (Django Channels) (`stretch`)
- Worker availability calendar (`stretch`)

## Execution after approval (GitHub setup only, no application code)

1. Rename branch `master` → `main`; first commit: `README.md` (idea + stack), `.gitignore` (Python),
   `docs/PLAN.md` (this plan).
2. `gh repo create AndrewKchn/BauHelfer --public --source . --remote origin --push`.
3. Labels: remove unused defaults, create the 10 project labels (`gh label create`).
4. 9 milestones with due dates (`gh api repos/AndrewKchn/BauHelfer/milestones -f title=… -f due_on=…`).
5. 55 issues created by a script from the list above (`gh issue create --title --body --label --milestone`).
6. Board: `gh project create --owner @me --title BauHelfer`, `gh project link` to the repo,
   `gh project item-add` for every issue. Columns: Todo / In Progress / Done.

The student creates the Render account during week one (M1 issue "First deploy").

## Verification

- `gh repo view AndrewKchn/BauHelfer` — repository exists, README is shown.
- `gh label list` — 12 labels; `gh api repos/AndrewKchn/BauHelfer/milestones --jq '.[].title'` — 9 milestones.
- `gh issue list --limit 100 --json number --jq length` → 55; every issue has a milestone and a label.
- `gh project item-list <number> --owner @me` — all 55 issues are on the board.
- The student opens the repository and the board in the browser and checks how they look.
