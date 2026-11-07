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

R6a. `tests/translations.py` also runs `msgfmt --check-header` (D14): a plural string with
     fewer forms than the language's `nplurals` is an error.

AC4. `test_every_string_is_translated[ru]` and `[uk]` pass without `xfail`.
AC4a. A sample `.po` for a language with 4 plural forms whose plural string has only 2 is
      reported by the check.

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
     applications, both profiles, role page, log in, sign up. The header in all 7
     languages: in iteration 2 the Russian guest header ("RU · Войти · Регистрация") was
     already 359 px wide, its buttons 8 px out of the menu; a job card with a long word
     ("Подсобник гипсокартонщика") pushed the rate 12 px out of the card.
R11. Only what runs out of its box or makes the page scroll sideways is fixed (D2); a badge
     gets `h-auto whitespace-normal` (D2, option A). Each fix is listed in the iteration's
     summary with its before / after screenshot.

What the check found (2026-11-07): a temporary Playwright probe opened 20 pages at 360 px in
all 7 languages as a guest, a worker and an employer, with the longest words in the data,
and listed every element that stuck out of its card or the screen. Five real problems:

| Where | Languages | Before | Fix |
|---|---|---|---|
| guest header ("Log in", "Register") | DE, RO | page 30 px wider than the screen | smaller paddings on phones (D16) |
| job page: title next to the rate | DE, RU, UK, PL | rate 7–22 px out, page scrolls sideways | the title may hyphenate (D15) |
| job card: title next to the rate | DE, UK | rate 4 px out of the card | the same (D15) |
| skill / trade badges on profiles | RU, DE | 47 px / 16 px out ("Подсобник гипсокартонщика", "Generalunternehmer") | badges wrap and hyphenate (D2) |
| skill checkboxes in the profile form | RU | page 1 px wider | the label may hyphenate (D15) |

After the fixes the probe found nothing on these pages. Left as it is: the status tabs of My
jobs / My applications may run past the right edge (RU "Отклонена 1": 17 px); the strip
scrolls sideways by design (#20), so every tab stays reachable. No automated test guards
these fixes: layout needs a browser, and that test belongs to #40 (D3).

## Glossary (D6)

Claude's draft; I reviewed RU and UK on 2026-11-07 and kept it as it is. I chose between the
alternatives: "вакансия" (not "заказ", "подработка") and "заявка" / "подать заявку" (not
"отклик" / "откликнуться"), the words we already use; the other columns are checked by
back-translation (D1). DE "Helfer": what a helper on a building site is called, and the
"Helfer" of BauHelfer.

| English | DE | RU | UK | PL | RO | TR |
|---|---|---|---|---|---|---|
| job | Job | вакансия | вакансія | zlecenie | lucrare | iş |
| application | Bewerbung | заявка | заявка | zgłoszenie | candidatură | başvuru |
| apply | sich bewerben | подать заявку | подати заявку | zgłosić się | a candida | başvurmak |
| worker | Helfer | рабочий | робітник | pracownik | muncitor | işçi |
| employer | Auftraggeber | работодатель | роботодавець | zleceniodawca | angajator | işveren |
| crew | Team | бригада | бригада | ekipa | echipă | ekip |
| accept / reject | annehmen / ablehnen | принять / отклонить | прийняти / відхилити | przyjąć / odrzucić | a accepta / a respinge | kabul etmek / reddetmek |
| withdraw | zurückziehen | отозвать | відкликати | wycofać | a retrage | geri çekmek |
| work permit | Arbeitserlaubnis | разрешение на работу | дозвіл на роботу | pozwolenie na pracę | permis de muncă | çalışma izni |
| hourly rate, €/h | Stundenlohn, €/Std. | ставка в час, €/ч | погодинна ставка, €/год | stawka godzinowa, €/godz. | tarif orar, €/oră | saatlik ücret, €/saat |
| post a job | Job einstellen | разместить вакансию | розмістити вакансію | dodać zlecenie | publicați o lucrare | iş ilanı vermek |
| Munich | München | Мюнхен | Мюнхен | Monachium | München | Münih |

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
     back-translation for them. I read all 335 strings side by side (EN | RU | UK) on
     2026-11-07 and changed nothing.
D12. **Back-translation sees only the translations** (Claude's default): the agent gets no
     English original, so it cannot copy it; it gets the glossary's English words, so it
     does not invent synonyms.
D13. **Four iterations** (Claude's default): the gaps first, so all translations are checked
     with `--check-format`; RU / UK before the rest, so the glossary is fixed by the
     languages I can read.

D14. **`msgfmt --check-header`: every plural string has all the language's forms**
     (Claude's default, accepted 2026-11-07; added in iteration 2). Found on a screenshot:
     the Russian job list said "16 open". `makemessages` writes 2 empty forms (`msgstr[0]`, `msgstr[1]`) even for
     languages with more (RU, UK, PL: 4; RO: 3); a translation that fills only those 2
     passed `--check-format` and the "every string translated" test, and Django fell back
     to English for 5–20. Its other header warnings (empty `Last-Translator`…) are not
     errors, so the files need no other change.

D15. **A long word may hyphenate: `min-w-0 break-words hyphens-auto`** (Claude's default,
     tried in iteration 4): on the job title, the job card title and the checkbox labels.
     The browser splits a word at a syllable of the page's language (`<html lang>`, e.g.
     "Trockenbau-helfer"); where it has no dictionary (Polish in Chromium), `break-words`
     splits it anyway. Rejected: shorter translations (D2, option B).
D16. **Smaller header paddings on phones** (Claude's default, tried in iteration 4): the
     logo `px-2` and the guest buttons `px-2`, `gap-1`, back to the old sizes from `sm`
     (640 px). Gains ~40 px, enough for RO "Autentificare · Înregistrare". Rejected: hiding
     "Register" on phones (a worker who wants to sign up looks for it in the header).

D17. **Profile cards: on a phone each label above its value** (mine, 2026-11-07; option A).
     In Russian the label column ("Разрешение на работу") took half of a 360 px screen and
     left ~100 px for the values: ten skill badges in one column, words split by hyphens.
     Now the worker and employer cards are one column below 640 px (label, then value; 4 px
     between them, 16 px between pairs), as on the worker profile mockup, and two columns
     from `sm` as before. Rejected: a label column of at most 8rem (B: values get ~190 px,
     still one long badge per line); a shorter Russian label (C: German and Romanian have
     the same problem). The short "Contacts" and "Email notifications" lists keep two
     columns.

## Known limitations

- DE / PL / RO / TR have no native-speaker review (D1).
- Field names seen only in the admin ("latitude", "thumbnail") are translated too: the check
  allows no untranslated string.

## Differences from the mockups

None: the mockups are in English; long translations are handled in iteration 4.
