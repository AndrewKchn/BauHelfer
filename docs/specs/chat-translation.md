# Spec: chat messages in the reader's language, "Show original" (#36)

Status: **agreed**. I decided D1 and D11 on 2026-11-17. D2–D10 and D12 are Claude's defaults,
which I accepted on 2026-11-17, before any tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

The chat of #35 joins a worker and an employer who often have no language in common: Andrii
writes in Ukrainian, Klaus reads German. After #36 each of them reads the other's messages in
their own language, translated by the service of #31 / #34, with the same label and "Show
original" toggle as the job description (#32) and the application messages (#33). Their own
messages stay as they wrote them.

Nearly everything exists already (application-translation.md D5): the rule `shown_text()`
(`jobs/shown_text.py`), `translate_many()`, the label template
`jobs/_translation_label.html`, `forget()`. The chat gets its own small wrapper, as the
comment of Docs sync M5 (#97) on this issue asks.

Three iterations in one branch and one PR:

1. The language of a message, translating it when it is sent, showing it translated with its
   label, forgetting it (R1–R10).
2. The "Show original" / "Show translation" toggle of each message (R11–R13).
3. The last message on the "Chats" page in the reader's language (R14–R16).

### Out of scope

- Translating the messages again when the reader switches the site language: the page
  translates what is missing, as in #32 / #33 (no new code).
- Keeping "Show original" open when a new message arrives (D8).
- Real-time delivery (WebSockets): #54.

## Mockup (docs/mockups/chat.png)

| Mockup | App | Why |
|---|---|---|
| "08:14 · translated from Ukrainian · original" in the footer | the time in the footer as in #35; under the bubble "文A Translated from Ukrainian by AI · Show original" | the same label and toggle as the description and the applications (D7) |
| the original as a second, italic bubble "original of 08:14 · show translation" | the text in the same bubble is swapped, "Original · Show translation" | one look for every translated text; the same template (D7, D8) |
| own messages: "08:20 · you", no label | the same | nobody reads their own text translated (D5) |
| — | the original with "Translation is not available right now." | #34 D15, D10 |
| — | a message in the reader's language: no label | job-translation.md D8, D4 |

## Layers

As in application-translation.md, with the chat's own wrapper:

| Layer | Where | Knows |
|---|---|---|
| 1. Translator | `translations/services.py` | the cache, the limits, Claude |
| 2. Rule | `jobs/shown_text.py`: `shown_text()` | plain values only |
| 3. Wrapper | `chat/shown_text.py`: `chat_messages_for()`, `chat_previews_for()` | `Message`, who reads |
| 4. Template | `jobs/_translation_label.html` | `state`, `label`, the block to swap |

## Iteration 1: language, translation when sent, label, forgetting

### Requirements

R1. `Message.original_language`: the same field as `Application.original_language` (2
    letters, our 7 languages, `""` for another one, `blank=True`, default `""`). The
    migration gives existing rows `""` (D2).
R2. Sending a message sets `original_language` from `detect_language(text)`; `None` (cannot
    tell, the fake translator) keeps the sender's `preferred_language` (D3).
R3. After the message is saved, `ChatView.post` calls `translate(text, <the other person's
    preferred_language>)` when the message's language is not that one (D1, D4). The result
    is not used: the call only fills the cache. A failure changes nothing for the sender: the
    message is saved and the page reloads as always (`translate()` never raises, #34 D15;
    D10).
R4. `chat.shown_text.chat_messages_for(messages, reader, reader_lang)` gives each message a
    `shown` (`ShownText`): one `translate_many()` for the messages that need a translation
    (not the reader's own, not in `reader_lang`), then `shown_text()` per message with
    `is_author = message.sender_id == reader.pk` (D5, D6).
R5. The chat page calls it with the active language (`translation.get_language()`,
    job-translation.md R8), on GET, on a form with errors and on a poll that brings something
    new (#35 R15). A 204 calls nothing.
R6. Each bubble shows `shown.text` (line breaks kept); under the bubble of the other person's
    message, `_translation_label.html` (D7): `translated` → "文A Translated from <language> by
    AI"; `unavailable` → "Translation is not available right now."; `same` and `own` →
    nothing. The template compares no languages (application-translation.md D5).
R7. A `post_delete` receiver on `Message` calls `forget(text)` (D9): also when the message
    goes with its application, its job or an account (`on_delete=CASCADE`). Messages are
    never edited, so nothing else forgets.
R8. The chat page makes the same number of queries for 1 and for 5 messages (#35 AC6), also
    with messages in another language, all cached (one `translate_many()` query).
R9. No new UI strings: the labels are those of #32.
R10. The daily limit of #34 (300 new translations, whole site) counts chat messages too
     (Known limitations).

### Acceptance criteria (→ tests)

AC1. Sending with a detected `uk` saves `uk`; with `None` the sender's `preferred_language`.
AC2. Sending in Ukrainian to a German employer saves a `Translation` row (→ de); sending in
     German to a German employer makes no translation call; a failing translator still saves
     the message and redirects to the chat.
AC3. `chat_messages_for`: the other person's Ukrainian message for a German reader →
     `translated`; one in German → `same`; the reader's own Ukrainian message → `own`, no
     translator call; a failing translator → `unavailable`, the original.
AC4. The chat page in German: the Ukrainian message's translation and "Translated from
     Ukrainian by AI"; the own message without a label; `original_language=""` → "Translated
     by AI".
AC5. Deleting a message, its application, or an account deletes the translations of its text.
AC6. The same number of queries for 1 and for 5 translated messages.

## Iteration 2: "Show original" per message

### Requirements

R11. With the state `translated`, the label ends with "· Show original": a link to the chat
     with `?original=<message id>#message-<id>` (D8). HTMX attributes as in
     application-translation.md R15: `hx-select` and `hx-target` are the message's own block
     `#message-<id>`; the anchor only in `href`.
R12. `?original=<id>` shows that message in the original with "Original · Show translation",
     state `original`; the others stay translated. "Show translation" links to the chat
     without the parameter. A wrong id, or one of another chat, changes nothing; a letter is
     ignored.
R13. The poll asks for the chat without `?original=` (#35 R13): when a new message arrives,
     the list is drawn again and the message is translated again (D8). The click in a
     browser is left for the E2E ticket #40.

### Acceptance criteria (→ tests)

AC7. A translated message has "Show original" linking to `?original=<id>#message-<id>` with
     the four HTMX attributes on `#message-<id>`; an own message and a `same` one have none.
AC8. `?original=<id>` shows that message in the original with "Original" and "Show
     translation"; another message stays translated; no translator call for it.
AC9. `?original=abc`, or the id of a message of another chat: the page as without it.

## Iteration 3: the last message on "Chats" in the reader's language

### Requirements

R14. `ChatListView` annotates the language and the sender of the last message (two
     `Subquery`s next to `last_text`, in the same query, D11).
R15. `chat.shown_text.chat_previews_for(chats, reader, reader_lang)` gives each chat a
     `shown_last`: one `translate_many()` for the previews that need it, then `shown_text()`
     with `is_author = last_sender_id == reader.pk`.
R16. The row shows `shown_last.text`, cut to 60 characters, without a label or a toggle
     (D12). The page makes the same number of queries for 1 and for 3 chats (#35 R25).

### Acceptance criteria (→ tests)

AC10. A German reader's row: the other person's last Ukrainian message translated; the own
      last message in the original; a German one as it is; a failing translator: the
      original.
AC11. The same number of queries for 1 and for 3 chats with translated previews.

## Decisions

D1. **A message is translated when it is sent, into the other person's language** (mine,
    2026-11-17; option A; my criterion of application-translation.md D1: "the sender waits,
    not the reader"). The sender waits about 3 s per message (detection and translation); the
    reader's page and polls read the cache. Rejected: the language when sent, the
    translation on the reader's page (B: the sender waits ~1 s, but a reader who was away
    waits ~2 s per new message when opening the chat, a risk of a timeout on Render); the
    sender's site language without detection (C: no wait, but Andrii with a German site
    writing Ukrainian would get Klaus no translation, application-translation.md D3).
    **Revisit when** the chat moves to WebSockets (#54) or the wait on "Send" is a complaint.
D2. **`Message.original_language`, existing messages `""`** (Claude's default, accepted): as
    application-translation.md R6, D10; there are no real users yet.
D3. **The language is found by Claude; if it cannot tell, the sender's site language**
    (Claude's default, accepted): as application-translation.md D3. A short "Ok" may not be
    told apart.
D4. **The reader's language: no translation, no label** (Claude's default, accepted):
    job-translation.md D8.
D5. **Nobody sees their own message translated; the author is decided per message**
    (Claude's default, accepted): application-translation.md D6. Unlike a job page, a chat
    page holds texts of both people, so `is_author` is `sender_id == reader.pk` for each.
D6. **The chat's own wrapper in `chat/shown_text.py`, the rule stays in `jobs`** (Claude's
    default, accepted): application-translation.md D5 ("Revisit when #36 needs the rule
    outside `jobs`"): it is only imported, not copied; `chat` already imports `jobs`. One
    `translate_many()` per page, as #33 D2.
D7. **The label and toggle of the description, not the mockup's footer line** (Claude's
    default, accepted): application-translation.md D4, D9; no new strings.
D8. **"Show original" is `?original=<message id>`; a new message resets it** (Claude's
    default, accepted): one message switches, as #33 D8. The poll asks without the parameter
    (#35 R13), so the next new message draws the list translated again; carrying `original`
    into the poll is code for a rare case.
D9. **Translations of a message are forgotten when it is deleted** (Claude's default,
    accepted; my criterion of ai-translation.md D3: personal data must not outlive the text):
    a `post_delete` receiver, as #33 D7.
D10. **A failed translation never stops a message** (Claude's default, accepted): #34 D15;
     the reader sees the original with "Translation is not available right now.".
D11. **The last message on "Chats" is translated too, from the cache** (mine, 2026-11-17;
     option a). The translation is already in the cache since the message was sent (D1),
     but the page reads `Message.text`, so it needs two subqueries (language, sender) and
     one `translate_many()`; no Claude call. Rejected: the original in the row (b, Claude's
     recommendation by my "features over polish" criterion: no code, and the chat is one tap
     away).
D12. **The preview has no label and no toggle** (Claude's default, accepted): the row is a
     link to the chat, where the label and "Show original" are; a 60-character line has no
     room.

## Known limitations (→ docs/SECURITY.md)

- Every chat message is sent to Anthropic when it is sent, twice (detection and translation)
  (ai-translation.md D1).
- Chat messages share the site's daily limit of 300 new translations (#34): a busy chat day
  can use it up, then the readers see originals with "Translation is not available right
  now." The detection is not counted (job-translation.md D11).
- The sender waits about 3 s on "Send" (D1).
- Two messages with the same text ("Ok") share their translations: deleting one forgets them
  for the other, which is translated again (ai-translation.md D3).
