# Spec: translating the M2–M4 strings (#30)

Status: **agreed**. I decided D1–D5 on 2026-11-07. D6–D13 are Claude's defaults, which I
accepted on 2026-11-07, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted.

## Goal

#29 turned i18n on, but the ~330 strings of M2–M4 have no translations: a Russian user sees
English everywhere except the language switcher. This ticket translates them into the 6
languages other than English, removes the `xfail` marker #29 left for it (i18n.md D2), and
closes two gaps found on the way: `€/h` is not marked for translation, and a string added to
the code without running `makemessages` is invisible to every check (i18n.md, "Known
limitations").

Four iterations in one branch and one PR (D13):

1. The gaps: `€/h`, `makemessages` in CI, placeholders checked.
2. The glossary, Russian and Ukrainian (I review them).
3. German, Polish, Romanian, Turkish (back-translation, D1).
4. Long translations on a phone: screenshots, fixes only where something runs out (D2).

### Out of scope

- An E2E test that no page scrolls sideways at 360 px in German: moved to #40 (D3).
- Translating user content (jobs, messages): #31–#34.
- A review by native speakers of DE / PL / RO / TR (D1, "Revisit when").

## Iteration 1: the gaps

### Requirements

R1. `€/h` is translated wherever a rate is shown: `templates/jobs/_job_summary.html`,
    `_job_card.html`, `job_detail.html`. The number is inside the translated string
    (`{% blocktranslate %}{{ rate }} €/h{% endblocktranslate %}`), so a language can put the
    unit before the number (D9).
R2. CI runs `makemessages` with the flags from `CLAUDE.md` after installing `gettext`, then
    `git diff --exit-code locale/`: a string wrapped in the code but missing from the `.po`
    files, or one deleted from the code but still in them, turns CI red (D4).
R3. `tests/translations.py` runs `msgfmt` with `--check-format`: a translation whose
    placeholders (`%(name)s`, `%(count)d`) differ from the English string is reported (D8).
    Without it, only in that language, a misspelt placeholder crashes Python code
    (`KeyError`, error 500; a template falls back to English) and a missing one loses its
    value (an email without the job's date).

### Acceptance criteria (→ tests)

AC1. In German the job list, the job detail page and the job summary (My jobs, My
     applications) show the rate as "… €/Std.".
AC2. A sample `.po` whose translation drops or renames a placeholder is reported by the
     check.
AC3. The CI step fails after a `{% translate %}` string is added without `makemessages`
     (checked by hand once, the command run locally; result in the PR's "How to test":
     a CI step has no pytest test).

## Iteration 2: glossary, Russian, Ukrainian

R4. The glossary below is filled in for all 6 languages; every translation uses its words
    (D6). I review the RU and UK columns before the strings are translated.
R5. `locale/ru` and `locale/uk`: every string translated, polite address (D5), German legal
    terms kept (D10). I read both `.po` diffs; what I change goes into `docs/AI_LOG.md`
    (D11).
R6. The `xfail` marker of `test_every_string_is_translated` no longer covers `ru` and `uk`
    (D7): the failing-tests commit removes it for them, the translations make it pass.

AC4. `test_every_string_is_translated[ru]` and `[uk]` pass without `xfail`.

## Iteration 3: German, Polish, Romanian, Turkish

R7. `locale/de`, `pl`, `ro`, `tr`: every string translated with the glossary, polite address
    (D5).
R8. Back-translation (D1, D12): for each language a separate agent without our context gets
    only the translations and writes them back in English. Claude lists only the strings
    whose meaning differs from the original; I decide each one. The count and my decisions
    go into `docs/AI_LOG.md`.
R9. The `xfail` marker is removed completely (closes i18n.md D2).

AC5. `test_every_string_is_translated` passes for all 6 languages, with no marker left.
AC6. In every one of the 7 languages the job list has `<html lang="…">` and its title
     ("Jobs in Munich") in that language.

## Iteration 4: long translations on a phone

R10. Screenshots at 360 px, light and dark, in German and Romanian (the longest), of: job
     list, job detail (guest, worker, employer with applications), job form, My jobs, My
     applications, both profiles, role page, log in, sign up.
R11. Only what runs out of its box or makes the page scroll sideways is fixed (D2); a badge
     gets `h-auto whitespace-normal` (D2, option A). Each fix is listed in the iteration's
     summary with its before / after screenshot.

## Glossary (D6)

Filled in iteration 2; RU and UK reviewed by me.

| English | DE | RU | UK | PL | RO | TR |
|---|---|---|---|---|---|---|
| job | | | | | | |
| application | | | | | | |
| apply | | | | | | |
| worker | | | | | | |
| employer | | | | | | |
| crew | | | | | | |
| accept / reject | | | | | | |
| withdraw | | | | | | |
| work permit | | | | | | |
| hourly rate, €/h | | | | | | |
| post a job | | | | | | |
| Munich | | | | | | |

## Decisions

D1. **DE / PL / RO / TR are checked by back-translation** (mine, 2026-11-07; option B). I
    cannot read these languages; an agent without our context translates them back into
    English and I decide on every string whose meaning changed. Rejected: Claude's draft
    without any check (A: wrong words nobody notices, e.g. a Polish "Apply" button that
    means "file a complaint"); native speakers (C: the best quality, but slow and dependent
    on other people). Costs: catches wrong meaning, not clumsy style. **Revisit when** a
    native speaker of one of them can review it, or a user complains about a translation.
D2. **Long translations: checked on screenshots, fixed only where something breaks** (mine,
    2026-11-07; option C). A reversible one-class change is tried, not argued. If a badge
    runs out, it wraps (`h-auto whitespace-normal`, option A) rather than getting a shorter
    translation (B: loses meaning, e.g. the red "Work permit not confirmed" badge an
    employer must understand). **Revisit when** a later ticket adds a badge or a button
    with a long label.
D3. **The E2E test "no sideways scroll at 360 px in German" goes to #40** (mine, 2026-11-07;
    option B). `CLAUDE.md` keeps E2E tests in a milestone's test ticket, and M5 has none;
    this ticket is checked by the screenshots of iteration 4. Rejected: writing it here
    (A: an exception to that rule); not at all (C). Costs: M5 tickets have no automatic
    guard, only their own screenshots.
D4. **`makemessages` is checked by a CI step, not a pytest test** (mine, 2026-11-07;
    option B). Three lines in `ci.yml`; a trial on 2026-11-07 showed `makemessages` leaves
    `locale/` unchanged byte for byte, so the diff gives no false alarms. Rejected: a pytest
    test (A: ~40 lines, `makemessages` writes into the project's `locale/` and would have to
    be redirected); nothing (C). Costs: the check runs only in CI, not in `uv run pytest`.
D5. **Polite address in every language** (mine, 2026-11-07; option A): Sie, вы, ви, Pan /
    Pani or impersonal, dumneavoastră, siz. The users are employers and workers of all
    ages; "too polite" costs nothing, "too familiar" may cost a user. Where the polite form
    in PL or RO gets long, an impersonal form is fine ("Zgłoszenie" instead of "Proszę się
    zgłosić"). Rejected: "du" everywhere (B); each language's own habit (C: harder to check
    by back-translation).
D6. **A glossary of ~12 key words first** (Claude's default): one word for "job" or
    "application" on every page and in every email, chosen once; the next tickets translate
    with it too.
D7. **The `xfail` marker is removed one language at a time** (Claude's default): it is
    strict, so a translated language turns CI red until its marker is gone. Removing it is
    the failing-tests commit of iterations 2 and 3.
D8. **`msgfmt --check-format`** (Claude's default): `compilemessages` already uses it, but
    only on my machine; the CI check did not. 38 strings per language have placeholders.
D9. **The rate is one translated string with the number inside** (Claude's default), not
    `{{ rate }} {% translate "€/h" %}`: "€/h" alone gives a translator no context, and a
    language can move the number.
D10. **German legal words stay German** (Claude's default): "Gewerbe", "Minijob" and
     "BauHelfer" are kept in every language, e.g. RU "Самозанятый (Gewerbe)": a worker
     meets them on German papers. "Munich" is translated (München, Мюнхен, Monachium,
     Münih).
D11. **RU / UK reviewed by me in the `.po` diff** (Claude's default): Claude writes the
     `.po` files, I read the diff in VS Code, Claude applies my corrections; no
     back-translation for them.
D12. **Back-translation sees only the translations** (Claude's default): the agent gets no
     English original, so it cannot copy it; it gets the glossary's English words, so it
     does not invent synonyms.
D13. **Four iterations** (Claude's default): the gaps first, so all translations are checked
     with `--check-format`; RU / UK before the rest, so the glossary is fixed by the
     languages I can read.

## Known limitations

- DE / PL / RO / TR have no native-speaker review (D1).
- Field names seen only in the admin ("latitude", "thumbnail") are translated too: the check
  allows no untranslated string.

## Differences from the mockups

None: the mockups are in English; long translations are handled in iteration 4.
