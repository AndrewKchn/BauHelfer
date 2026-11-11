# Spec: application messages in the employer's language, "Show original" (#33)

Status: **agreed**. I decided D1, D2, D5 and D11 on 2026-11-11. D3, D4 and D6–D10 are
Claude's defaults, which I accepted the same day, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

A worker writes the message of an application (#22) in their own language: Andrii in
Ukrainian, Ion in Romanian. Klaus, the employer, reads German. After #33 the applications on
the job page (#23) show each message in the employer's language, translated by the service
of #31 / #34, with the same label and "Show original" toggle as the job description (#32).

The difference from #32: one job page has one description, but many applications. Translated
while the page loads, 8 new messages would keep Klaus waiting about 16 seconds (D1).

Three iterations in one branch and one PR (D11):

1. Refactoring, no new behaviour: the rule "who sees the original, who the translation"
   becomes one function for any text, and the label with its toggle one template.
2. The language of a message, translating it when it is sent, showing it translated with its
   label, forgetting it.
3. The "Show original" / "Show translation" toggle of each message.

### Out of scope

- Chat messages (#36): it reuses the rule and the template of iteration 1 with its own
  wrapper (D5).
- Emails: they carry no message text (notifications.md D9), so nothing to translate.
- "My applications": the worker reads their own message, in the original (D6).
- The "Cancel" / "Accept" rules written in the template, the views and the model: found
  while reading `job_detail.html`, a separate Stretch issue (from session redi-d1).

## Mockup (docs/mockups/my-jobs.png)

| Mockup | App | Why |
|---|---|---|
| "“We are a crew of two…” · from Ukrainian" after the quote | the quote, then a small grey line "文A Translated from Ukrainian by AI · Show original" | the same label and toggle as the description (D4) |
| — | "Original · Show translation" after the toggle | the mockup shows one state only |
| — | the original with "Translation is not available right now." | #34 D15, job-translation.md D10 |
| — | a message in the employer's language: no label | job-translation.md D8 |

## Layers

| Layer | Answers | Where | Knows |
|---|---|---|---|
| 1. Translator | "this text in Polish" | `translations/services.py` | the cache, the limits, Claude |
| 2. Rule | "does this reader see the original or a translation?" | `jobs/shown_text.py`: `shown_text()` | plain values only: texts, languages, author or not, original asked for or not |
| 3. Wrappers | "where are the text, its language and its author in this model?" | `description_for(job)`, `messages_for(applications)`; #36: its own | their model |
| 4. Template | "how to draw this state?" | `jobs/_translation_label.html` | `state`, `label`, the id of the block |

Each layer uses only the one below it. The decision is made in layer 2; the template only
draws it (D5).

## Iteration 1: one rule, one label (refactoring)

### Requirements

R1. `jobs/descriptions.py` becomes `jobs/shown_text.py`. `Description` is renamed
    `ShownText(text, state, from_language)` with its `label`; `TRANSLATED_FROM` stays.
R2. `shown_text(text, from_language, reader_lang, *, is_author, translated,
    show_original=False) -> ShownText` holds the rule of job-translation.md R7, R12: author →
    `own`; same language → `same`; `show_original` → `original`; otherwise `translated`
    (`translated` is the `Translated` of #31: `ok` → `translated`, not `ok` →
    `unavailable`). It takes no model (D5); `translated` is asked for only when needed, as a
    function, so `own`, `same` and `original` make no translator call.
R3. `description_for(job, reader_lang, *, is_owner, show_original=False)` keeps its
    signature and only calls `shown_text()` with the job's values.
R4. `jobs/_job_description.html`'s label and toggle move into
    `jobs/_translation_label.html` (D9): it gets the `ShownText`, the id of the block to
    swap, and the two URLs ("Show original", "Show translation"). It branches only on
    `state` (D5). `jobs/_description_toggle.html` goes.
R5. Nothing the user sees changes: the job page's HTML for each state is the same as before.

### Acceptance criteria (→ tests)

AC1. `shown_text`: each of the 5 states from plain values; `own`, `same` and `original` do
     not call `translated`.
AC2. The tests of #32 (`test_descriptions.py`, `test_job_translation_views.py`) pass with
     only the import and the class name changed.

## Iteration 2: language, translation when sent, label, forgetting

### Requirements

R6. `Application.original_language`: the same field as `Job.original_language` (2 letters,
    our 7 languages, `""` for another one, `blank=True`, default `""`). The migration gives
    existing rows `""` (D10).
R7. Sending an application with a message sets `original_language` from
    `detect_language(message)`; `None` (cannot tell, the fake translator) keeps the worker's
    `preferred_language` (D3). An empty message: no call, the worker's `preferred_language`.
R8. After the application is saved and the employer notified, `JobApplyView` calls
    `translate(message, employer.preferred_language)` when the message is not empty and its
    language is not the employer's (D1). The result is not used: the call only fills the
    cache. A failure changes nothing for the worker: "Application sent." as always
    (`translate()` never raises, #34 D15).
R9. `translations.services.translate_many(texts, target_lang) -> dict[str, Translated]`:
    the cached translations of all `texts` in **one** query (`source_hash__in`); each text
    not in the cache goes through `translate()` (its limits and logging). Empty and repeated
    texts are handled as by `translate()` (D2).
R10. `jobs.shown_text.messages_for(applications, reader_lang, *, original_id=None)` gives
     each application a `shown_message` (`ShownText`): one `translate_many()` for the
     messages that need a translation, then `shown_text()` per application. The page is the
     employer's, so `is_author` is false (D6).
R11. The job page calls `messages_for()` for the owner only, with the active language
     (`translation.get_language()`, job-translation.md R8).
R12. The message shows `shown_message.text` in quotes with its line breaks and, under it,
     `_translation_label.html` (D4): `translated` → "文A Translated from <language> by AI";
     `unavailable` → "Translation is not available right now."; `same` → nothing. The
     template compares no languages and checks no owner (D5).
R13. A `post_delete` receiver on `Application` calls `forget(message)` (D7): also when the
     application goes with its job or with the worker's account (`on_delete=CASCADE`).
     Messages are never edited, so nothing else forgets.
R14. No new UI strings: the labels are those of #32.

### Acceptance criteria (→ tests)

AC3. `translate_many`: 3 cached texts → their translations in 1 query; a text not cached is
     translated and saved; a failing translator gives the original with `ok` false; an
     empty text comes back as it is.
AC4. Applying with a detected `uk` saves `uk`; with `None` saves the worker's
     `preferred_language`; with an empty message no detection call.
AC5. Applying in Ukrainian to a German employer saves a `Translation` row (→ de); applying
     in German to a German employer makes no translation call; a failing translator still
     gives "Application sent." and the application.
AC6. The employer's page in German: a Ukrainian message shows its translation and
     "Translated from Ukrainian by AI"; a German message shows no label; with
     `original_language=""` "Translated by AI"; a failing translator shows the original and
     "Translation is not available right now."
AC7. The template draws what `messages_for()` decided: a `ShownText` with state `same` gets
     no label, whatever the languages (D5).
AC8. Deleting an application, its job, or the worker's account deletes the translations of
     its message.
AC9. The page's queries do not grow with the applications (applications-list.md D7, AC17),
     now also with messages in another language, all cached.

## Iteration 3: "Show original" per message

### Requirements

R15. With the state `translated`, the label ends with "· Show original": a link to the same
     page with `?original=<application id>#application-<id>` (D8). HTMX attributes as in
     job-translation.md R11, but `hx-select` and `hx-target` are `#message-<id>`, the
     message's own block: only it is swapped, without a reload.
R16. `?original=<id>` shows that application's message in the original with "Original ·
     Show translation", state `original`; the others stay translated. "Show translation"
     links to the page without the parameter. A wrong or foreign id changes nothing.
R17. The click in a browser is left for the E2E ticket #40, as in job-translation.md R13.

### Acceptance criteria (→ tests)

AC10. A translated message has "Show original" linking to `?original=<id>#application-<id>`
      with the four HTMX attributes on `#message-<id>`.
AC11. `?original=<id>` shows that message in the original with "Original" and "Show
      translation"; another application's message stays translated; no translator call.
AC12. `?original=` with a letter, or the id of an application to another job: the page as
      without it, no error.

## Decisions

D1. **The message is translated when it is sent, into the employer's language; the page
    translates only what is missing** (mine, 2026-11-11; option B; criterion: usability —
    "the worker waits 2 s rather than the employer 16"). The worker waits about 2–3 s once
    (detection and translation); the employer's page reads the cache. If the employer later
    switches the site to another language, the page translates as in #32. Rejected:
    translating only on the page (A: 8 new applications ≈ 16 s for the employer, a risk of
    a timeout on Render); each message loaded by HTMX with "Translating…" (C: a new URL,
    view and template, the most code; I dropped the same idea in #32 D4).
D2. **One query for all cached messages: `translate_many()`** (mine, 2026-11-11; option A).
    The page of #23 promises the same number of queries for 1 or 10 applications
    (applications-list.md D7); a `translate()` per message would add one query each, the
    "N+1" problem. Rejected: accepting N queries and changing #23 D7 (B: no code, but it
    breaks a rule I defended in #23).
D3. **The language of a message is found by Claude when it is sent; if Claude cannot tell,
    the worker's site language** (Claude's default, accepted): the same as for jobs (#32 D2,
    D11). Example: Andrii's site is in German, he writes in Ukrainian; with his site
    language Klaus would get no translation.
D4. **The label and the toggle are those of the description** (Claude's default, accepted),
    not the mockup's "· from Ukrainian": one look for every translated text on the site, no
    new strings, and "by AI" says who translated (#32 D9).
D5. **The translator only translates; who sees what is one rule in `jobs`, without models;
    the template only draws its result** (mine, 2026-11-11; option B). I asked whether
    deciding what to show is the translator's job: it is not — the translator knows the
    cache and Claude, the rule knows readers, authors and `?original`. `shown_text()` takes
    plain values, so #36 reuses it with its own wrapper (a chat message's author changes
    from message to message: `is_author` per message); `chat` importing from `jobs` adds no
    new link, a chat already belongs to a job. The template branches only on `state`, as
    `_job_description.html` already does (suggested by session redi-d1: when a rule is
    written in the template too, the copies drift apart, as the "Cancel" / "Accept" rules
    did). Rejected: the rule in `translations/display.py` (A, Claude's first default: the
    translator would know about pages); a copy of the rule for messages (C: two places to
    fix). **Revisit when** #36 needs the rule outside `jobs`.
D6. **Nobody sees their own message translated** (Claude's default, accepted, as
    job-translation.md D7): the worker on "My applications" reads the original; nothing
    changes there.
D7. **Translations of a message are forgotten when its application is deleted**
    (Claude's default, accepted; my criterion of ai-translation.md D3: personal data must
    not outlive the text it came from). A `post_delete` receiver, as for jobs (#32 D12).
D8. **"Show original" is `?original=<application id>`** (Claude's default, accepted): one
    message switches, the others stay translated. `#application-<id>` in the link: without
    JavaScript the page reloads at that application, not at the top (as accept-reject.md
    D3).
D9. **One label template for the description and the messages** (Claude's default,
    accepted): the block to swap and the URLs are parameters.
D10. **Existing applications get `original_language = ""`** (Claude's default, accepted):
     every employer then gets them translated, labelled "Translated by AI". There are no
     real users yet (#32 D1), so no data migration that guesses the language.
D11. **Three iterations; the refactoring is the first, on its own** (mine, 2026-11-11;
     Claude proposed two, as in #32). Moving the rule and the label changes no behaviour:
     with the tests of #32 still green it is shown to be a pure refactoring, and the
     messages are built on top of it.
D12. **`Description` becomes `ShownText`, `jobs/descriptions.py` becomes
     `jobs/shown_text.py`** (mine, 2026-11-11). It changes nothing in how the code works:
     the change that matters is `shown_text()` taking plain values instead of a job (R2).
     The names are for the reader: an application's message is not a description. Cost:
     the class name in 8 lines of the #32 tests and one import in the view. Rejected:
     keeping `Description` and adding `shown_text()` to `descriptions.py` (no old test
     touched, but a message or a chat message would be "a Description"). It is a function,
     not a property of the model: unlike `Application.can_withdraw`, the answer depends on
     who reads (their language, author or not, "Show original").

## Known limitations (→ docs/SECURITY.md)

- The message is sent to Anthropic when the application is sent, twice (detection and
  translation), before the employer has opened it (ai-translation.md D1).
- The detection is not counted in the daily limit (job-translation.md D11).
- Two applications with the same message ("Hallo") share their translations: deleting one
  forgets them for the other, which is translated again (ai-translation.md D3).
- The worker waits 2–3 s on "Send" (D1).
