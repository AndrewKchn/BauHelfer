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
