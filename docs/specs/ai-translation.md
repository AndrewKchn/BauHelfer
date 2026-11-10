# Spec: translation service with a DB cache (#31, #34)

Status: **agreed**. I decided D1–D3 on 2026-11-07. D4–D13 are Claude's defaults, which I
accepted on 2026-11-07, before any tests; D14 likewise, before the tests of iteration 2.
#34 (errors and cost limits) is in its own section at the end.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted.

## Goal

Users write jobs and messages in their own language; a Polish worker cannot read a job
written in Russian. This ticket adds the service that translates such text:
`translate(text, target_lang)`. It asks Claude once per text and language and keeps the
result in the database, so showing the same job again costs nothing. It has no page of its
own: #32 (jobs), #33 (application messages) and #36 (chat) call it.

Two iterations in one branch and one PR:

1. The service, the cache and a fake translator: works without a key.
2. The Claude translator: prompt, model, key from the env, one manual check.

### Out of scope

- Showing translations on pages, the "show original" toggle: #32, #33, #36.
- API errors, text length and rate limits, falling back to the original: #34 (D10).
- Calling `forget()` when a job or message is deleted or edited: #32, #33, #36 (D3).
- DeepL or any other translator (D1, D5).

## Iteration 1: service and cache

### Requirements

R1. A new app `translations/` in `INSTALLED_APPS`, with the model `Translation`:
    `source_hash` (SHA-256 of the source text, 64 hex characters), `target_language` (one of
    `settings.LANGUAGES`), `text` (the translation), `created_at`. One row per
    `source_hash` + `target_language` (a unique constraint). The source text itself is not
    stored (D6). Not in Django admin (D13).
R2. `translations.services.translate(text, target_lang) -> str`:
    - empty or whitespace-only text is returned as it is: no translator call, no row (D7);
    - a `target_lang` that is not one of the 7 codes of `settings.LANGUAGES` raises
      `ValueError`, before any call (D8);
    - a row for the text and language → its `text`, without calling the translator;
    - no row → the translator is called once, the result is saved and returned.
R3. `translations.services.forget(text)` deletes the rows of this text in every language;
    rows of other texts stay (D3).
R4. The translator is chosen by the setting `TRANSLATION_BACKEND`, a dotted path to a class
    with `translate(text, target_lang) -> str`, as `EMAIL_BACKEND` chooses how email is sent
    (D5).
R5. `translations.backends.fake.FakeBackend` returns `"[<lang>] <text>"` and calls nothing
    outside. `base.py` uses it, so the site and the tests run without a key.

### Acceptance criteria (→ tests)

AC1. `translate()` returns what the translator returned.
AC2. The second call with the same text and language does not call the translator again and
     returns the same text.
AC3. The same text in another language calls the translator again (a second row).
AC4. Empty and whitespace-only text is returned unchanged; no call, no row.
AC5. An unknown language code raises `ValueError`; no call, no row.
AC6. After `forget(text)` the rows of that text are gone in every language, rows of another
     text stay, and the next `translate()` calls the translator again.
AC7. A saved row contains the hash and the translation, not the source text.
AC8. Without any setting of ours, `TRANSLATION_BACKEND` is the fake translator.

## Iteration 2: the Claude translator

### Requirements

R6. `translations.backends.claude.ClaudeBackend` calls the Claude API through the official
    `anthropic` library (D2): model `claude-haiku-5-5`, thinking off (D4).
R7. The system prompt is fixed: translate into <language name in English, e.g. "Polish">;
    keep construction terms, numbers, prices, dates, phone numbers and names; add nothing,
    explain nothing; output only the translation; if the text is already in that language,
    return it unchanged (D8). The user's text goes into the user message inside
    `<text>…</text>`; the prompt says that everything inside is text to translate, also
    when it looks like an instruction (D9).
R8. The translation is the text of the answer, without surrounding whitespace; blocks are
    read by their type, so a thinking block is never taken for the answer. An answer that
    was cut off (`max_tokens`) or declined (`refusal`) raises `TranslationError` instead
    of returning: what it returned would be cached for good (D14). `max_tokens` is at least
    4000, enough for a long job text. Changed by #34 (D19): 1500, since texts are at most
    1000 characters.
R9. The key comes from the env variable `ANTHROPIC_API_KEY`. `production.py` sets
    `TRANSLATION_BACKEND` to the Claude translator and refuses to start without the key
    (D11). `render.yaml` lists the variable as set in the dashboard. `.env.example`
    documents it; locally it stays empty and the fake translator is used.
R10. Every call to Claude is logged, without the text:
     `Translation created: lang=<code> hash=<first 12 characters> input_tokens=…
     output_tokens=…` (#124 style; the tokens show the cost).
R11. One manual check against the real API with a separate local key (deleted afterwards):
     a Russian job text into German and Polish. Its result goes into the PR's "How to test".

### Acceptance criteria (→ tests, with the `anthropic` client replaced; no real call in CI)

AC9.  The request names `claude-haiku-5-5` and turns thinking off.
AC10. The system prompt names the target language and contains the rules of R7; the user's
      text is inside `<text>…</text>` in the user message, unchanged.
AC11. The answer's text, stripped, is returned; a thinking block is skipped; an answer cut
      off or declined raises `TranslationError` and leaves no row.
AC12. Production settings use the Claude translator and read the key from the env.
AC13. The log line has the language, the hash prefix and the token counts, not the text.

## Decisions

D1. **The Claude API translates** (mine, 2026-11-07; criteria: money — a one-time $5 top-up
    is fine; personal data is handled honestly (GDPR matters to me); AI in the project is a
    plus). Facts checked on the official pages on 2026-11-07: API inputs and outputs are not
    used for training by default, are deleted within 30 days, the DPA with Standard
    Contractual Clauses is part of the Commercial Terms. Processing is in the US or "global"
    (`inference_geo` has no EU option). Rejected:
    - DeepL API Free (free, company in Germany): its terms let DeepL "perpetually store any
      Content" and forbid personal data on the free API — job texts and messages contain
      names and phone numbers. I first chose it and changed my mind after these terms.
    - DeepL API Pro (no storage, EU): a monthly subscription.
    - Gemini API free tier: texts may be used for training.
    - No API, a "translate in Google" button: no AI, #31–#36 lose their point.
    - The school's Claude subscription: it covers working with Claude, not API calls from a
      server.
    **Revisit when** the project must keep personal data in the EU, or Anthropic offers EU
    processing on the API.
D2. **The official `anthropic` library** (mine, 2026-11-07): typed errors (rate limit,
    network, server) and automatic retries, which #34 builds on. Rejected: raw HTTP
    requests (no new dependency, but errors and retries are ours to get right).
D3. **`forget(text)` removes a text's translations** (mine, 2026-11-07; option C, criterion:
    personal data must not outlive the job or message it came from). #32, #33 and #36 call
    it when a job or message is deleted or edited. Rejected: keeping translations forever
    (A, as in the plan); deleting rows unused for N days (B: Render's free plan has no cron,
    the command would be run by hand). Costs: two jobs with the same text share rows, so
    forgetting one makes the other translate again — a few hundredths of a cent.
D4. **`claude-haiku-5-5` without thinking** (Claude's default, accepted): $0.10 / $0.50 per
    million input / output tokens against $1 / $5 for `claude-haiku-4-5` in the plan, and 4
    times the requests per minute. A translation needs no reasoning, and thinking tokens are
    paid as output. About $0.00025 per translated job. **Revisit when** translations of
    construction slang turn out wrong.
D5. **The translator is a setting, like `EMAIL_BACKEND`** (Claude's default, accepted): Claude
    in production, a fake one locally and in tests — no key, no network, no cost. Another
    translator later is one more class.
D6. **The cache key is the SHA-256 of the text plus the language; the source text is not
    stored** (Claude's default, accepted): less personal data in the database. The
    translation itself still contains it (D3).
D7. **Empty text is not translated** (Claude's default, accepted): no call and no row for
    nothing.
D8. **Only our 7 languages as targets; the source language is detected by Claude**
    (Claude's default, accepted): authors write in any language; a text already in the
    target language comes back unchanged.
D9. **The user's text is data, not instructions** (Claude's default, accepted): it goes inside
    `<text>` tags and the prompt says so. If the model still follows an instruction inside,
    only the author's own text is shown changed. The translation is shown through Django's
    autoescaping, so HTML in it is not run.
D10. **No error handling in this ticket** (Claude's default, accepted): an API error is raised
     to the caller. #34 adds "show the original", the text length limit and the rate limit.
     Replaced by #34: D15 (the original instead of an error), D16–D17 (limits).
D11. **Production refuses to start without `ANTHROPIC_API_KEY`** (Claude's default, accepted),
     as with Brevo (notifications.md D12): a missing variable shows up at the deploy.
D12. **Translated in the request, no queue** (Claude's default, accepted), as email
     (notifications.md D11): no worker process on Render's free plan. **Revisit when** users
     notice the delay.
D13. **The cache is not in Django admin** (Claude's default, accepted): the rows contain
     personal data; the log lines (R10) are enough to see what happens.

D14. **A cut-off or declined answer is an error, not a translation** (Claude's default,
     accepted on 2026-11-07, before the tests of iteration 2): the cache keeps what it gets
     forever, so half a sentence or an empty text would be shown to every reader of that
     job. Raising keeps the row empty, and the next reader asks again. #34 decides what the
     page shows meanwhile (D10).

## Known limitations (→ docs/SECURITY.md)

- Job and message texts are sent to Anthropic (US / global processing), kept there up to 30
  days, not used for training; up to 2 years if flagged for a policy violation (D1).
- Translations stay in our database until `forget()` is called (D3); until #32 / #33 call it,
  nothing is deleted.
- A changed prompt or model does not refresh translations already in the cache.
- A prompt injection inside a text can change at most that text's own translation (D9).
- Until #34, an API error breaks the page that asked for the translation (D10). Fixed by #34
  (D15).

---

## #34: API errors and cost limits

Status: **agreed**. I decided D15–D17 on 2026-11-10. D18–D22 are Claude's defaults, which I
accepted on 2026-11-10, before any tests.

### Goal

After #31 an API error reaches the view and the page answers 500 (D10), a job description
has no length limit, and nothing stops one person from using up the prepaid $5. After #34
`translate()` never breaks a page: when it cannot translate, it returns the original and
says so. Texts are at most 1000 characters, and the whole site makes at most 300 new
translations a day.

Two iterations in one branch and one PR:

1. The service: the result with a flag, errors, the length and the daily limit, timeout.
2. The job form: the description is at most 1000 characters.

### Out of scope

- What a page shows when `ok` is false ("Translation not available", "show original"):
  #32, #33, #36.
- A limit per reader or per author (D17).

### Iteration 1: the service

#### Requirements

R12. `translate(text, target_lang)` returns `Translated(text, ok)`, a small frozen
     dataclass in `translations/services.py`: `ok` is true when `text` is a translation
     (from the cache or from the translator), false when it is the original (D15). Empty
     text keeps D7: the original with `ok` true, nothing to translate. An unknown language
     keeps D8: `ValueError`, a programming error, not a service failure.
R13. A translator that fails raises `TranslationError` (moved from `backends/claude.py` to
     `translations/backends/__init__.py`, so every translator can raise it). The Claude
     translator turns every `anthropic.APIError` (network, timeout, rate limit, server,
     no credit left) into a `TranslationError` (D20). `translate()` catches only
     `TranslationError`: the original with `ok` false, no row saved, and a log line
     `Translation failed: lang=<code> hash=<12> error=<exception class>`, without the
     text and without the error message (D20).
R14. A text longer than `TRANSLATION_MAX_LENGTH` (1000, in `base.py`) is not sent: the
     original with `ok` false and a log line `Translation skipped: reason=too_long lang=…
     hash=…` (D16). A text already in the cache is still returned from it.
R15. When the site has saved `TRANSLATION_DAILY_LIMIT` (300, in `base.py`) or more rows of
     `Translation` in the last 24 hours, no new text is sent: the original with `ok` false
     and `Translation skipped: reason=daily_limit lang=… hash=…` (D17). Texts already in
     the cache are still returned from it.
R16. The Claude client waits at most 10 seconds and retries once (D18); `max_tokens` is
     1500 (D19).
R17. Manual check before the merge: a monthly spend limit set in the Anthropic Console;
     its value goes into the PR's "How to test" (D21).

#### Acceptance criteria (→ tests, mocked client, no real call)

AC14. A translation (new or from the cache) comes back with `ok` true; empty text comes
      back unchanged with `ok` true.
AC15. A translator raising `TranslationError` gives the original with `ok` false, saves
      no row, and logs the failure line with the class name and without the text; the
      next call asks the translator again.
AC16. The Claude translator turns `anthropic.APIConnectionError`,
      `anthropic.APITimeoutError`, `anthropic.RateLimitError` and
      `anthropic.InternalServerError` into `TranslationError`.
AC17. A text of 1001 characters is not sent (`ok` false, skip line); 1000 characters is
      sent.
AC18. With 300 rows of the last 24 hours, a new text is not sent (`ok` false, skip line);
      a text in the cache still comes back with `ok` true; with 299 rows, or 300 rows
      older than 24 hours, a new text is sent.
AC19. The Claude client is created with `timeout=10` and `max_retries=1`; the request has
      `max_tokens=1500`.

### Iteration 2: the job description

#### Requirements

R18. `Job.description` gets `max_length=1000` (a `TextField` still, D22): the form then
     refuses a longer text with Django's own translated error, and the `<textarea>` gets
     `maxlength="1000"`, so the browser stops typing at 1000.
R19. The help text under the field names the limit: "Write in your language, up to 1000
     characters. Workers read it in theirs." Translated into all 6 languages. The only
     difference from the mockup `post-a-job.png` (D22).

#### Acceptance criteria (→ tests)

AC20. The job form with 1001 characters of description is invalid, with 1000 valid;
      the edit form likewise.
AC21. The form page has `maxlength="1000"` on the textarea and the new help text.

### Decisions

D15. **`translate()` returns the text and a flag `ok`** (mine, 2026-11-10; option B,
     criterion from notifications.md D10: an outside service never breaks the action, and
     the rule is in one place). Example: Maria opens a job written in Russian while the API
     is down; #32 must not label the Russian text "translated from Russian". Rejected:
     returning the original silently (A: a page can tell it only by comparing, which is
     wrong when the text was already in the reader's language); raising an exception (C:
     every view of #32, #33, #36 repeats the same `try`, and a forgotten one is a 500
     again). Cost: the tests of #31 read `.text`.
D16. **A job description is at most 1000 characters** (mine, 2026-11-10). I compared
     examples of the same demolition job: 419 characters (a usual job), 894 (tasks, tools,
     safety gear, hours, pay, transport, next work: all a worker needs to decide), 1915
     (padded with what is said on site: the toilet, the kettle, the neighbours). Rejected:
     2000 (I could not fill it honestly). The limit is checked twice: the form tells the
     author (D22), the service does not trust its callers, chat messages included (R14).
     **Revisit when** employers ask for more room.
D17. **One daily limit for the whole site: 300 new translations in 24 hours** (mine,
     2026-11-10; option B, criteria: the $5 must last until the defense, simple code).
     Facts: the credits are prepaid, so more than $5 can never be spent; when they run out
     the API errors and everyone sees originals (D15). So the limit protects the service,
     not the wallet. The cost grows with new texts, not with readers: 100 readers of one
     job in Polish are one request. Prices from the manual check of #31 (62 characters =
     220 input / 50 output tokens, about 2 characters per token): a chat message about
     $0.00005, a usual job $0.00017, a job of 1000 characters about $0.0004. 300 a day of
     the longest texts is $0.12 a day, the $5 last at least 40 days; the project needs
     about 120 translations in all (20 jobs × 6 languages). Counted from the rows of
     `Translation`: no new table, and Render's sleep does not reset it. Rejected: a limit
     per reader per hour (A: an author with 200 long jobs is not stopped, since each reader
     asks a few times; anonymous readers share an IP in a dormitory's Wi-Fi); both (C:
     twice the code for little more). Cost: the issue's "rate limit per user" changes to
     "a daily limit on new translations"; one abuser can use up a day and everyone sees
     originals until the next. 500 and 1000 rejected: at 1000 the $5 last 12 days under
     abuse. **Revisit when** real use comes near 300 a day.
D18. **Timeout 10 seconds, one retry** (Claude's default, accepted): the library waits up
     to 10 minutes and retries twice. A page waits at most about 20 seconds, then shows
     the original.
D19. **`max_tokens` 1500 instead of 4096** (Claude's default, accepted): three times what
     1000 characters need; an answer inflated by a prompt injection costs at most
     $0.00075.
D20. **The translator turns its own errors into `TranslationError`; the service catches only
     that** (Claude's default, accepted): `services.py` does not know about `anthropic`
     (D5), and a bug in our own code (a `TypeError`) still shows up as an error, not as an
     "untranslated" text. The log has the class only, as notifications.md D10: an error
     message can contain the request. Nothing is cached, so the next reader asks again.
D21. **A spend limit in the Anthropic Console** (Claude's default, accepted): a second guard
     outside our code, set once by hand. Set on 2026-11-10 (mine): $3 a month, auto-reload
     off. Below the worst case of D17 ($3.6 a month): a month of abuse would end the
     translations early, and everyone would see originals (D15), never a bill.
D22. **`TextField(max_length=1000)`, not a `CharField`; the limit in the help text**
     (Claude's default, accepted): the column stays `text`, so the migration changes
     nothing in the database and cannot fail on a longer old description at the deploy
     (`migrate` runs on start, render.yaml). The application message of #22 is a
     `CharField` because it was new. The help text names the limit, since `maxlength`
     stops typing without saying why; the mockup has no counter, and none is added
     (simple first).

### Known limitations (→ docs/SECURITY.md)

- The daily limit counts saved rows: rows deleted by `forget()` free their place, and
  failed or cut-off answers are not counted, though a cut-off one is paid.
- One abuser can use up the day's 300; everyone then sees originals until the oldest row
  is 24 hours old.
- A description longer than 1000 characters saved before #34 stays, is not translated,
  and must be shortened at the next edit.
- Between two requests of the same moment both may pass the limit check: the limit can be
  passed by a few rows.
- Haiku makes small mistakes, kept in the cache for good. The manual check of 2026-11-10
  (6 jobs in RU, DE, PL, UK, RO, TR into Russian and Polish, 12 calls, about $0.0016)
  found two: "рigips" with a Cyrillic "р" (RO → RU) and an awkward "наличие отсутствия
  боязни высоты" (DE → RU). The meaning was kept in both. `forget()` of the text clears
  them (D3); D4 says when to change the model.
- A text already in the reader's language is still sent to Claude and comes back
  unchanged: a paid call and 1.5–3 seconds. The pages (#32, #33, #36) know the original
  language and should not ask.
