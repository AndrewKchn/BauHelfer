# BauHelfer

[![CI](https://github.com/AndrewKchn/BauHelfer/actions/workflows/ci.yml/badge.svg)](https://github.com/AndrewKchn/BauHelfer/actions/workflows/ci.yml)

A web app that connects construction specialists in Munich with general labourers and small crews
for short-term work: clearing debris, demolition, carrying materials.

**Live:** https://bauhelfer.onrender.com (free hosting: the first visit after a quiet period can
take up to a minute while the server wakes up)

- **Employers** post a job: type of work, date, district, number of workers, hourly rate.
- **Workers and crews** browse jobs and apply.
- **Employers** accept applications; both sides then see each other's contacts.

Job descriptions and chat messages are translated automatically with the Claude API, so employers
and workers can communicate even without a common language.

Final project for the "Development with AI" course at [ReDI School of Digital Integration](https://www.redi-school.org/), Munich.

## Stack

- Python 3.12, Django 5
- Django templates, HTMX, Tailwind CSS
- PostgreSQL
- Claude API for translation
- Leaflet + OpenStreetMap
- pytest-django, ruff, GitHub Actions
- Hosting: Render (Frankfurt), database on Supabase (Frankfurt), both on free plans

## Status

In development: first deploy done (M1). See [docs/PLAN.md](docs/PLAN.md) and the [issues](../../issues).
