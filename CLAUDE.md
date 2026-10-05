# BauHelfer

Django job board for construction labourers in Munich. ReDi School final project: Claude writes
code, the student reviews it, decides and defends it. Plan, data model and milestones:
[docs/PLAN.md](docs/PLAN.md) — read it instead of guessing.

## Commands

```bash
uv sync                                  # install dependencies
uv run pre-commit install                # once per clone: ruff runs before every commit
docker compose up -d                     # start PostgreSQL (needed for runserver and tests)
uv run tailwindcss -i tailwind/input.css -o static/css/app.css --watch   # rebuild CSS on change
uv run python manage.py runserver        # dev server (settings: config.settings.local)
uv run python manage.py makemigrations   # after model changes
uv run pytest                            # tests
uv run ruff check . && uv run ruff format .
```

Copy `.env.example` to `.env` before the first run.

## Structure

- `config/settings/` — `base.py` (shared), `local.py` (dev), `production.py` (Render)
- `templates/` — Django templates; every page extends `base.html` (a test checks it)
- `tailwind/` — `input.css` + `daisyui.mjs`, built into `static/css/app.css` (not in git)
- `static/` — `js/htmx.min.js` (downloaded, served by WhiteNoise, no CDN)
- Downloaded third-party files, never edited by hand: `tailwind/daisyui.mjs` (daisyUI 5.7.47,
  used only while building CSS) and `static/js/htmx.min.js` (HTMX 2.0.10). Marked
  `linguist-vendored` in `.gitattributes`. To update: download the new release file over the
  old one, change the version here and in `docs/PLAN.md`, rebuild CSS, run the tests.
- `docs/PLAN.md` — plan; `docs/AI_LOG.md` — log of AI-assisted work; `docs/SECURITY.md` —
  what is protected, where, which tests check it, known limitations
- Django apps (`accounts/`, `jobs/`, `chat/`, …) are added ticket by ticket, see the plan

## Conventions

- Code, comments, docs, issues and commit messages in English.
- Every UI string is wrapped in `gettext` / `{% translate %}`; from M5 also translated into all
  7 languages (DE, EN, RU, UK, PL, RO, TR).
- No secrets or personal data in the repo — it is public.
- Keep it simple: Django built-ins first, no new dependency without asking.

## Testing levels

1. Unit tests first (TDD). The student reads them; commit them failing: "Add failing tests for …".
2. Implementation until the tests pass.
3. Integration tests with the Django test client.
4. E2E (Playwright) only in the per-milestone test tickets.

Every test file: docstring starting `Unit tests:` / `Integration tests:` / `E2E tests:` and
`pytest.mark.story(N)` in `pytestmark` (a test from another ticket gets its own marker). Every
test: docstring = short line (the title in the Allure report) + numbered steps ending with
`Expect: …`. Missing ones stop the run (`tests/story_labels.py`).

## Working with the student

- The student is new to Django: explain each part as it is written.
- Offer real choices with a recommendation; the student decides. Record when they reject or
  change a suggestion — it goes into `docs/AI_LOG.md`.
- Never commit, push or open a PR without an explicit "yes". Never merge.

## Ticket workflow

1. `gh issue view N`; check it is not blocked (`gh api repos/AndrewKchn/BauHelfer/issues/N/dependencies/blocked_by`).
2. `gh issue develop N --checkout`; move the card on the "BauHelfer" board to In Progress.
3. Tests → code → tests, as above. Separate commits: failing tests, then implementation, then
   any fixes or integration tests. If the ticket touches security or personal data, update
   `docs/SECURITY.md` (each point linked to its code and tests) in the same branch.
4. Go through the ticket's "Done when…" list: show each item with its evidence (test, commit,
   CI run). After "yes", tick them in the issue (`- [ ]` → `- [x]` via `gh issue edit`);
   closing the issue does not tick them.
5. Run `/ai-log`: drafts the AI_LOG entry and the PR "AI usage" section; the student edits.
6. After "yes": the AI_LOG entry goes in its own last commit ("Add AI_LOG entry for #N"),
   then `gh pr create` with `Closes #N` in the body.
7. The student merges on GitHub with "Create a merge commit" (squash is disabled to keep the
   separate commits); the branch is deleted and the card moves to Done automatically.
   `main` is protected: no direct pushes, every change goes through a PR.
