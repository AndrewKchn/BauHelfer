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
