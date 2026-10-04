# BauHelfer

[![CI](https://github.com/AndrewKchn/BauHelfer/actions/workflows/ci.yml/badge.svg)](https://github.com/AndrewKchn/BauHelfer/actions/workflows/ci.yml)

A web app that connects construction specialists in Munich with general labourers and small crews
for short-term work: clearing debris, demolition, carrying materials.

**Live:** https://bauhelfer.onrender.com (free hosting: the first visit after a quiet period can
take up to a minute while the server wakes up)

Final project for the "Development with AI" course at [ReDI School of Digital Integration](https://www.redi-school.org/), Munich.

## Problem

A window fitter or plasterer in Munich often needs one or two extra hands for a day: someone to
clear debris, demolish an old wall or carry materials up four floors. Today such helpers are found
through friends, WhatsApp groups and general classifieds. It is slow, there is no way to see who
is reliable, and the two sides often do not share a language.

## Solution

- **Employers** post a job: type of work, date, district, number of workers, hourly rate (never
  below the German minimum wage).
- **Workers and crews** browse jobs and apply.
- **Employers** accept applications; both sides then see each other's contacts.

Job descriptions and chat messages are translated automatically with the Claude API, so employers
and workers can communicate even without a common language. The interface is available in German,
English, Russian, Ukrainian, Polish, Romanian and Turkish.

## Stack

- Python 3.12, Django 5
- Django templates, HTMX 2, Tailwind CSS 4 + daisyUI 5 (built with the standalone Tailwind CLI)
- PostgreSQL
- Claude API for translation
- Leaflet + OpenStreetMap
- pytest-django, ruff, GitHub Actions
- Hosting: Render (Frankfurt), database on Supabase (Frankfurt), both on free plans

## Run locally

You need [git](https://git-scm.com/), [uv](https://docs.astral.sh/uv/) (it installs Python 3.12
for you) and [Docker](https://docs.docker.com/get-docker/).

1. Clone the repository:
   ```bash
   git clone https://github.com/AndrewKchn/BauHelfer.git
   cd BauHelfer
   ```
2. Install the dependencies:
   ```bash
   uv sync
   ```
3. Create your settings file and put a new secret key into `SECRET_KEY`:
   ```bash
   cp .env.example .env
   uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
   ```
4. Start PostgreSQL in Docker:
   ```bash
   docker compose up -d
   ```
5. Create the database tables and an admin account:
   ```bash
   uv run python manage.py migrate
   uv run python manage.py createsuperuser
   ```
   `createsuperuser` asks for an **email** (you log in with it, there is no username) and a
   **password** twice; the password is not shown while you type. For a simple password Django
   asks `Bypass password validation and create user anyway? [y/N]` — answer `y` for local
   development.
6. Build the CSS (Tailwind CLI, no Node.js needed; the first run downloads it):
   ```bash
   export TAILWINDCSS_VERSION=v4.3.3   # the version CI and Render use
   uv run tailwindcss -i tailwind/input.css -o static/css/app.css --minify
   ```
   `static/css/app.css` is not in git. While you change templates, keep it up to date in a
   second terminal: `uv run tailwindcss -i tailwind/input.css -o static/css/app.css --watch`.
7. Start the development server and open http://127.0.0.1:8000 (admin: http://127.0.0.1:8000/admin/):
   ```bash
   uv run python manage.py runserver
   ```

### Tests and code style

```bash
uv run pytest --cov                        # tests; fails below 80 % coverage
uv run ruff check . && uv run ruff format .
uv run pre-commit install                  # once per clone: ruff runs before every commit
```

Every pull request runs the same checks in CI (plus docstring coverage); a red check blocks the
merge into `main`.

## Project links

- [Plan](docs/PLAN.md): stack decisions, data model, milestones
- [Project board](https://github.com/users/AndrewKchn/projects/1): what is in progress now
- [Issues](https://github.com/AndrewKchn/BauHelfer/issues)
- [AI log](docs/AI_LOG.md): how AI was used and which suggestions were changed or rejected

## Status

In development. M1 (foundation and first deploy) is done; next is M2, accounts and profiles.
