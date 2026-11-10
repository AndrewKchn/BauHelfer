# Spec: job descriptions in the reader's language, "Show original" (#32)

Status: **agreed**. I decided D1–D6 on 2026-11-10. D7–D13 are Claude's defaults, which I
accepted on 2026-11-10, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

Employers write a job's description in their own language, mostly German; a worker from
Ukraine or Romania cannot read it. After #32 the job page shows the description in the
reader's language, translated by the service of #31 / #34, with the line "Translated from
German by AI · Show original". "Show original" swaps only the description, without
reloading the page. To know what "from German" is, the language of a description is found
by Claude when the job is saved (job-form.md D8 promised it).

Two iterations in one branch and one PR (D13):

1. The language of a description, the translated description and its label, forgetting
   old translations.
2. The "Show original" / "Show translation" toggle with HTMX.

### Out of scope

- Application messages (#33) and chat messages (#36): they reuse `translate()`, not this
  page's code.
- A "Translating…" note while the first reader waits (D4).
- Showing the whole page in the employer's language (D5).
- Translating the job type, the district and the other fields: they are keys from a list,
  shown in the reader's language by the `.po` files of #30.

## Mockup (docs/mockups/job-detail.png)

| Mockup | App | Why |
|---|---|---|
| "文A Translated from German by AI · Show original" under the description | the same, in the description's card | — |
| — | "Original · Show translation" after the toggle | the mockup shows one state only |
| — | "Translated by AI", without a language, for a language not among our 7 | D3 |
| — | the original with "Translation is not available right now." | #34 D15, D10 |
| — | the owner sees their own text, without a label | D7 |

## Iteration 1: language, translation, label

### Requirements

R1. `Job.original_language` may be empty (`blank=True`, the empty string, not `NULL`):
    "a language not among our 7" (D3). The migration changes no existing row.
R2. `translations.services.detect_language(text) -> str | None`: one of the 7 codes of
    `settings.LANGUAGES`, `""` for another language, `None` when it cannot tell (D11):
    - empty text, or text longer than `TRANSLATION_MAX_LENGTH`: `None`, no call;
    - the translator class of `TRANSLATION_BACKEND` gets a method
      `detect_language(text)`; a `TranslationError` from it gives `None` and the log line
      `Language detection failed: hash=<12> error=<exception class>`, without the text.
R3. `ClaudeBackend.detect_language(text)`: the same model and client as `translate()`
    (D4, D18 of ai-translation.md), thinking off, `max_tokens=10`. The system prompt asks
    which language the text inside `<text>` is written in, the language of most of it if
    mixed, and to answer with one code: `de`, `en`, `ru`, `uk`, `pl`, `ro`, `tr` or
    `other`. `other` becomes `""`; any other answer, a cut-off or a declined one raise
    `TranslationError`. Every call is logged without the text:
    `Language detected: lang=<code or other> hash=<12> input_tokens=… output_tokens=…`.
R4. `FakeBackend.detect_language(text)` returns `None`: locally and in tests a job keeps
    the employer's `preferred_language`, as before #32.
R5. Posting a job sets `original_language` from `detect_language(description)`; `None`
    keeps `preferred_language` (D2). Editing a job runs the detection only when the
    description changed; `None` keeps the current value (D11).
R6. Editing a job's description calls `forget(old description)` (ai-translation.md D3).
    Deleting a job — also with its employer's account — does the same, through a
    `post_delete` receiver on `Job` (D12).
R7. `jobs.descriptions.description_for(job, reader_lang, *, is_owner)` decides what the
    page shows and returns a small frozen dataclass `Description(text, state,
    from_language)`:
    - the owner: the original, state `own` (D7);
    - `original_language` is `reader_lang`: the original, state `same`, no call (D8);
    - otherwise `translate(job.description, reader_lang)`: `ok` → the translation, state
      `translated`; not `ok` → the original, state `unavailable` (D10).
    `from_language` is `original_language` (`""` when unknown). The view only calls it.
    Iteration 2 adds `show_original=False` and the state `original` (R12).
R8. The reader's language is the active one (`translation.get_language()`), the same that
    picks the page's own strings (i18n.md D3).
R9. The description's card (`id="description"`, `jobs/_job_description.html`) shows the
    text with its line breaks and, under it in small grey text:
    - `translated`: "文A Translated from <language> by AI" — one whole sentence per
      language, 7 of them, so each language can use its own grammar (D9); for an unknown
      language "Translated by AI";
    - `unavailable`: "Translation is not available right now.";
    - `own` and `same`: nothing.
R10. All new strings are wrapped in `gettext` / `{% translate %}` and translated into the 6
     languages.

### Acceptance criteria (→ tests)

AC1. `detect_language`: the translator's code comes back; `""` for another language;
     `None` for empty text, for 1001 characters (no call) and when the translator raises
     `TranslationError` (failure line with the class, without the text).
AC2. `ClaudeBackend.detect_language` (client replaced): the request has the model,
     thinking off, `max_tokens=10`, the text inside `<text>`; `ru` → `"ru"`, `other` →
     `""`; `"Russian"`, a `max_tokens` stop or a refusal raise `TranslationError`; an
     `anthropic.APIError` becomes `TranslationError`; the log line has no text.
AC3. Posting a job with a detected `ru` saves `ru`; with `None` saves `preferred_language`;
     with `""` saves `""`.
AC4. Editing only the rate does not call the detection; editing the description does, and
     `None` keeps the old value.
AC5. After editing a description, the old text has no rows in `Translation`; after
     deleting a job (and after deleting its employer), neither.
AC6. `description_for`: owner → `own` without a call; same language → `same` without a
     call; another language → `translated` with the translation; a failing translator →
     `unavailable` with the original.
AC7. A German job opened in Polish shows the translation and "Translated from German by
     AI" (in Polish); with `original_language=""` "Translated by AI"; opened in German it
     shows the original and no label; the owner sees the original and no label; a failing
     translator shows the original and "Translation is not available right now."
AC8. A guest's page of a job in another language makes a fixed number of queries,
     whatever the photos: the count of #19 AC14 plus the cache lookup (the test is
     updated, not removed).

## Iteration 2: "Show original"

### Requirements

R11. With the state `translated`, the label ends with "· Show original": a link to the
     same page with `?original=1` (D6). It has `hx-get` to the same URL,
     `hx-select="#description"`, `hx-target="#description"`, `hx-swap="outerHTML"`:
     HTMX replaces only the card, the page does not reload or scroll. Without JavaScript
     it is a plain link and the page reloads.
R12. `?original=1` on a job that would be translated (not the owner, another language)
     shows the original with "Original · Show translation", state `original`;
     "Show translation" links back to the page without the parameter, with the same HTMX
     attributes. For the owner and the same language the parameter changes nothing. It
     makes no translator call, so it cannot know whether a translation would fail: a
     failure shows up after "Show translation" ("Translation is not available right
     now.").
R13. The toggle is tested with the Django test client (the HTML of both states, the HTMX
     attributes). Clicking it in a browser is for an E2E test, as the photo buttons were
     (job-detail.md D9); M5 has no E2E ticket, so it is proposed for #40 (M6) in the
     "Docs sync — M5" issue.

### Acceptance criteria (→ tests)

AC9.  A translated description has "Show original" linking to `?original=1` with the four
      HTMX attributes.
AC10. `?original=1` shows the original text, "Original" and "Show translation" linking to
      the page without the parameter; no translator call.
AC11. `?original=1` for the owner and for the same language shows what the page without
      it shows. A failed translation offers no "Show original" (nothing to toggle).

## Decisions

D1. **Translated for everyone, guests too** (mine, 2026-11-10; option A; criterion: there
    are no users yet, the cache and the daily limit of #34 D17 are enough). A guest who
    switched the site to Ukrainian reads the job in Ukrainian. Rejected: only logged-in
    users, guests see the original and "Log in to read it in your language" (B: a first
    impression the guest cannot read, and one more branch). **Revisit when** the daily
    limit is reached by guests or bots.
D2. **The language of a description is found by Claude when the job is saved** (mine,
    2026-11-10; option A; criteria: an outside service never breaks the action —
    notifications.md D10, #34 D15; $5 until the defense; simple code). Example: Ivan's
    site is in German, he writes in Russian; with `original_language = "de"` Klaus (de)
    would get no translation and see Russian. One short call per save, about $0.0001.
    Rejected: during the translation (B: the language is known only after the first
    translation, the "same language" rule meanwhile reads a wrong field, and #31's service
    changes); a library such as `lingua` (C: a new dependency, weaker on short texts); not
    detecting (D: Ivan's case).
D3. **A language not among our 7 is saved as empty; the label then says only "Translated
    by AI"** (mine, 2026-11-10; option 2; criteria: simple code, polish only for a real
    risk). Example: Ahmed writes in Arabic. Every reader gets a translation, since no
    language is "the same". My question found the case: Claude's first fallback, keeping
    `preferred_language`, would have shown Klaus the Arabic text. Rejected: keeping
    `preferred_language` (1: that bug); any ISO code with Django's language names (3:
    a nicer label, more code and checks); refusing other languages in the form (4: the
    employer is stopped, and the form depends on the API). **Revisit when** jobs in other
    languages are common.
D4. **Translated inside the page's request; the first reader waits** (mine, 2026-11-10;
    option A; criterion: simple code; ai-translation.md D12). The first reader in each
    language waits about 2 seconds, at most 6 per job; the next ones read the cache. I
    asked for a "Translating…" note instead of the original while waiting, and dropped it
    when it turned out to need a second, HTMX-loaded request. Rejected: a "Translating…"
    note loaded by HTMX (B′, and B″ with a cache check: more code for a wait of 6 readers);
    translating into all 6 languages when the job is saved (C: the employer waits about
    10 seconds, translations nobody reads, the daily limit used 6 times faster).
    **Revisit when** users notice the wait.
D5. **"Show original" swaps only the description** (mine, 2026-11-10; criterion: usability
    — most jobs will be in German, and the worker needs the employer's own words). The
    rest of the page is not the employer's text: buttons and labels are ours, job type and
    district are keys from a list. The whole site in German is one tap on the language
    button (#29). Rejected: the whole page in the employer's language (repeats the
    language button; the apply form turns German for a worker who cannot read it; needs a
    temporary override of the profile's language, i18n.md D3).
D6. **The toggle is a link to the same page with `?original=1`, made partial by HTMX's
    `hx-select`** (mine, 2026-11-10; option A2; "a separate URL is too much"). One line
    in the view, no new view; without JavaScript the link still works. The first use of
    HTMX in the project. Rejected: a separate URL returning only the card (A1: a second
    view repeating the page's logic); both texts in the page with a few lines of JS (B:
    not HTMX, the issue's "Done when" would change). Cost: the server renders the whole
    page to swap one card, the translation coming from the cache.
D7. **The owner sees their own description in the original, without a label** (Claude's
    default, accepted): they know their text, and a translation of it would be a paid call
    for nothing.
D8. **The same language is not translated** (Claude's default, accepted; idea from #34):
    no call, no label. The manual check of #34 sent RU → RU and PL → PL: a paid call and
    1.5–3 seconds for an unchanged text.
D9. **One whole sentence per source language in the label** (Claude's default, accepted):
    "Translated from German by AI" and six more. A language name cannot be put into one
    sentence: German says "aus dem Russischen", Russian "с немецкого". The names of
    `LANGUAGES` ("Deutsch") are in their own language, not the reader's.
D10. **A failed translation shows the original and "Translation is not available right
     now."** (Claude's default, accepted): the page does not call a text translated when
     it is not (#34 D15), and the reader knows why it is in another language.
D11. **The detection runs on posting, and on editing only when the description changed;
     it never stops a save** (Claude's default, accepted): no call for a changed rate or
     date. When Claude cannot tell (`None`: an error, the fake translator), posting keeps
     `preferred_language` and editing keeps the current value. Not counted in the daily
     limit: it saves no `Translation` row (a known limitation).
D12. **Old translations are forgotten when a description changes or its job goes**
     (Claude's default, accepted; my criterion of ai-translation.md D3: personal data must
     not outlive the job). A `post_delete` receiver, not the views: it also runs when an
     employer's account is deleted and its jobs go with it (`on_delete=CASCADE`).
D13. **Two iterations** (Claude's default, accepted): the first gives a working page with
     translations, the second the toggle on top of it.

## Known limitations (→ docs/SECURITY.md)

- The description is sent to Anthropic once more on each save of a new or changed text,
  for the detection (ai-translation.md D1).
- The detection is not counted in the daily limit (D11): an employer saving many changed
  descriptions makes calls beyond the 300; each costs about $0.0001, and the Console's
  spend limit (#34 D21) still caps the month.
- A text mixing languages gets the language of most of it; the "same language" rule may
  then leave a part untranslated.
- Two jobs with the same description share their translations: editing one forgets them
  for the other too, which translates again (ai-translation.md D3).
- With `?original=1` in a link someone shares, the reader first sees the original.
