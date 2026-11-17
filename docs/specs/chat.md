# Spec: chat per accepted application (#35)

Status: **agreed**. I decided D1 and D2 on 2026-11-17 (my criteria: simple code and ease of use
before polish). D3–D10 are Claude's defaults, which I accepted on 2026-11-17, before any tests.
Iteration 2: I decided D11 on 2026-11-17 (same criteria, plus the load on Render's free plan);
D12–D14 are Claude's defaults, which I accepted on 2026-11-17, before its tests.
Iteration 3: I decided D15 and D16 on 2026-11-17 (same criteria; the count is on every page);
D17–D22 are Claude's defaults, which I accepted on 2026-11-17, before its tests.

Marks: **(mine, date)** — my decision; **(Claude's default, accepted)** — Claude's default
that I accepted; **(Claude's recommendation)** — what Claude advised where I chose
otherwise.

## Goal

Once an application is accepted, the worker and the employer can only phone each other
(#25). This ticket gives every accepted application a chat that only these two people can
read and write. New messages appear without a reload (HTMX polling), and the navigation
shows how many messages are unread.

Three iterations in one branch and one PR:

1. The chat page: messages, sending, who may read and write (R1–R12, D1–D10).
2. New messages without a reload (HTMX polling) (R13–R18, D11–D14).
3. The unread count in the navigation and a "Chats" page (R19–R26, D15–D22).

### Out of scope

- Translating the messages ("translated from Ukrainian · original" on the mockup): #36.
- A chat line or a reason when the employer cancels (D2).
- Real-time delivery (WebSockets): #54.
- Emails or push notifications about new messages.

## Requirements

### Iteration 1: the chat page

R1. A new app `chat/` with the model `Message`: `application` (FK to `Application`,
    `related_name="messages"`, CASCADE), `sender` (FK to `User`, CASCADE), `text`
    (`CharField`, at most 1000 characters, D5), `created_at` (`auto_now_add`). Ordered by
    `created_at`, then `id`.
R2. `Application.chat_writable` (a property): the same rule as `shows_contacts`: accepted,
    and the day of the job is not over, Munich time (D1).
R3. `Application.chat_readable` (a property): `chat_writable`, or the chat already has at
    least one message (D1, D3). Uses the annotation `has_messages` when the queryset has it
    (R11), otherwise one query.
R4. `ChatView` at `/chat/<application_pk>/` (`name="chat"`), login required. Only the
    application's worker and the employer of its job; anyone else, and a participant when
    the chat is not readable, gets 404 (D4).
R5. GET: the page with every message of this application, oldest first, and the form when
    the chat is writable. Two queries for the messages and their senders whatever their
    number.
R6. POST: saves the message with the logged-in user as `sender`, then redirects to the same
    page (Post/Redirect/Get), so a reload does not send it twice. An empty text or one with
    only spaces is refused with the form error. POST when the chat is not writable: 404 and
    nothing saved.
R7. The page header: the other person's name; the job type, date and district; a back link
    to "My applications" for the worker and to the job page at the application
    (`#application-<id>`) for the employer.
R8. Each message: the text (line breaks kept), the time `H:i`, Munich time. Own messages on
    the right in the primary colour with "you"; the other person's on the left (D7). A date
    line before the first message of each day (D8).
R9. A readable but not writable chat shows "This chat is closed. You can still read it."
    instead of the form (D1).
R10. No messages yet: "No messages yet. Write the first one." above the form.
R11. Links: the worker's card on "My applications" and every accepted or cancelled
     application in the owner's list on the job page get a "Chat" link when the chat is
     readable (D6). Both pages annotate `has_messages` (`Exists`), so the links cost no query
     per card.
R12. Every new string is wrapped for translation and translated into all 7 languages.

### Iteration 2: new messages without a reload

R13. A writable chat asks the server every 4 seconds for new messages (D11, D13): the message
     list (`#chat-messages`) has `hx-get` of the same page, `hx-trigger="every 4s"`,
     `hx-select="#chat-messages"`, `hx-swap="outerHTML"`, and sends the id of its last
     message as `?after=<id>` (`hx-vals`; 0 without messages). A closed chat does not ask
     (D12).
R14. GET with `?after=<id>` and no message of this chat with a higher id: **204** with an empty
     body; HTMX then changes nothing (D11). The access check of R4 comes first: a stranger
     still gets 404.
R15. GET with `?after=<id>` and a newer message: the whole page as without it; HTMX takes the
     message list out of it, so the swapped list carries the new last id and the date lines
     stay right.
R16. `?after=` that is not a number is ignored: the whole page, as `?original=` (#33).
R17. A 204 renders no template and sends no body; it makes no more queries than the page
     (both 4: the session, the user, the application, then the messages or one EXISTS).
     Measured in the tests: the page with 10 messages is ~9 KB and ~13 ms, the 204 ~7 ms.
R18. Above the form: "New messages appear every few seconds." (D14). Sending stays a plain form
     with a reload (R6).

### Iteration 3: the unread count and the "Chats" page

R19. `Message.read_at` (date and time, empty until read; not editable): when the other person
     first saw the message (D15).
R20. Rendering the chat page marks every message of the other person that is still unread as
     read, in one `UPDATE`, before the page is drawn: on GET, on a form with errors, and on a
     poll that brings something new (R15). A 204 marks nothing; own messages are never
     marked (D17).
R21. `unread_count(user)` in `chat/models.py`: the messages in the user's chats (as the worker
     or as the employer of the job) that are not the user's own and not read. One query.
R22. A context processor `chat.context_processors.unread_messages` gives every template
     `unread_messages`: the R21 count for a logged-in worker or employer, 0 for anyone else
     without a query (D18).
R23. The navigation, for workers and employers: the menu button shows a badge with the count
     when it is above 0; the menu has "Chats" with the same badge, after "My applications" /
     "My jobs". The badge has a text for screen readers ("3 unread messages") (D19).
R24. `ChatListView` at `/chat/` (`name="chat_list"`), login required: every readable chat of
     the user (R3), as worker or as employer, newest activity first (the last message, or the
     application if it has none) (D20). Each row links to its chat and shows the other
     person's name, the job type and date, the last message cut to 60 characters, and the
     unread count of this chat when above 0 (D21). None: "No chats yet. A chat opens when an
     application is accepted."
R25. The list makes the same number of queries for 1 and for 3 chats.
R26. The "Chat" links of R11 stay as they are, without a count (D22).

## Acceptance criteria (→ tests)

### Iteration 1

AC1. `chat_writable`: True for an accepted application on the day of the job; False the day
     after; False for pending, rejected, cancelled, withdrawn.
AC2. `chat_readable`: True when writable; for a cancelled and a withdrawn application True
     with one message and False without; with and without the `has_messages` annotation the
     same answer.
AC3. GET by the worker and by the employer: 200 and the messages, oldest first. Another
     worker, another employer: 404. A guest: to the login page. A pending application: 404.
AC4. POST by each participant: a message with that sender, a redirect to the chat. Empty /
     spaces only: no message, the form error. 1001 characters: refused. POST after the day
     of the job: 404, nothing saved.
AC5. A closed chat with messages: the messages and the R9 line, no form.
AC6. The same number of queries for a chat with 1 and with 5 messages.
AC7. "Chat" link on the worker's card and in the owner's list when readable, not otherwise;
     the same number of queries for 1 and 3 accepted applications.

### Iteration 2

AC8. A writable chat: the list has `hx-trigger="every 4s"` and `"after": <id of its last
     message>` (0 when empty), and the R18 line. A closed chat: neither.
AC9. `?after=<last id>`: 204, empty. `?after=<an older id>`: 200 with the newer message.
     `?after=abc`: 200, the whole page. A stranger with `?after=`: 404.
AC10. The 204 renders no template and makes no more queries than the whole page.

### Iteration 3

AC11. Opening the chat marks the other person's messages read, not the own ones and not those
      of another chat; a 204 marks none; a poll with something new marks it.
AC12. `unread_count`: counts the other person's unread messages in all the user's chats, as
      worker and as employer; not the own ones, not read ones, not other people's chats.
AC13. The badge on the menu button and next to "Chats" with the count; none at 0. A guest's
      page makes no query for it.
AC14. `/chat/`: the user's readable chats, newest activity first, each with the name, the job,
      the last message (cut) and its unread count; not a pending application, not a closed
      chat without messages, not another user's chat; the empty line when there are none. A
      guest goes to the login page. The same number of queries for 1 and 3 chats.

## Decisions

D1. **Writing while the contacts are shown, reading afterwards too** (mine, 2026-11-17;
    option B): the history stays readable after the job, also when writing a review (#38),
    and after a cancellation. Rejected: the chat only while the contacts are shown (A: the
    history vanishes the day after the job); writing until "Done" or a cancel (C: a job
    nobody marks done keeps its chat open for ever).
D2. **No chat line when the employer cancels** (mine, 2026-11-17; option A; the question
    from #37 D11): the cancellation is shown by the status and the email (#37). I wanted a
    system line "Cancelled by the employer · <date>" (B), but left it out for lack of time:
    it needs messages without a sender, drawn differently, and translated through `.po`
    files instead of Claude (#36). Rejected too: B with a reason the employer writes (C).
    **Revisit when** there is time after M6: B is the first improvement of the chat.
D3. **"Was accepted" is read from the messages, not from the status** (Claude's default,
    accepted): a worker can withdraw an accepted application (`WITHDRAWABLE`), so "withdrawn"
    does not say whether it was accepted. A chat with no messages has nothing to read, and a
    chat that was never writable cannot have any.
D4. **404 for anyone else** (Claude's default, accepted), as for other employers' applications
    (#24): it does not even say that the chat exists.
D5. **At most 1000 characters** (Claude's default, accepted): the limit of a text the
    translation takes (#34), so #36 can translate every message.
D6. **The way in: a "Chat" link on the two pages that already list the application** (Claude's
    default, accepted): the worker's card on "My applications" (the mockup's "Open chat", #26),
    the owner's list on the job page. No list of all chats: the unread count of iteration 3
    links to them. **Changed by D16:** a "Chats" page lists them all; the links stay.
D7. **The mockup's bubbles with daisyUI `chat`** (Claude's default, accepted): `chat-start` /
    `chat-end`, `chat-bubble-primary` for own messages, no JavaScript.
D8. **A date line per day instead of "Application accepted · <date>"** (Claude's default,
    accepted): the mockup's line needs a new field `accepted_at`; a date line per day comes
    from `{% ifchanged %}` and no field.
D9. **The phone stays** (Claude's default, accepted; the question from #25, contacts.md D1):
    nobody sees a chat message until they open the page, so a worker who is late on the day
    still needs the phone. **Revisit when** the chat sends notifications.
D10. **Messages are not in the Django admin** (Claude's default, accepted), as applications: a
     chat is private between two people.

D11. **Ask for new messages, and get "nothing new" as an empty 204** (mine, 2026-11-17;
     option C): the page of #32's HTMX pattern (`hx-get` the same page + `hx-select`) when
     something is new, so no new view and the date lines stay in one template; an empty
     answer otherwise, so an open chat costs Render little while nobody writes. Rejected: the
     whole page on every ask (A, Claude's recommendation: simplest, but the whole page,
     ~9 KB, every 4 seconds per open chat); a view that sends only the new messages (B: a
     new view and template, and the date line breaks where two pieces meet). **Revisit
     when** the chat moves to WebSockets (#54).
D12. **Only a writable chat asks** (Claude's default, accepted): a closed one gets no new
     messages. A chat that closes while open (midnight after the job) keeps asking until the
     page is reloaded; every answer is then a 204.
D13. **Every 4 seconds** (Claude's default, accepted): the plan says 3–5 s (`docs/PLAN.md`);
     a message is seen within 4 seconds, and 15 asks a minute per open chat.
D14. **The mockup's line about new messages** (Claude's default, accepted): without it,
     someone waiting for an answer reloads the page by hand.

D15. **Each message knows when it was read: `read_at`** (mine, 2026-11-17; option A): one
     field where the message is, and the count reads as a sentence: "messages in my chats,
     not mine, not read". Rejected: "last opened" times for both sides on the application
     (B: two fields in `jobs`, and a count whose condition depends on which side I am).
D16. **A "Chats" page with all chats; the count leads there** (mine, 2026-11-17; option B):
     two taps to any chat for both sides. Rejected: counts on the cards of "My jobs" / "My
     applications" and on the "Chat" buttons (A: counts on three levels, four taps for the
     employer); a count only in the menu (C: it does not say where the message is). Replaces
     D6's "no list of all chats".
D17. **Read when the page is drawn** (Claude's default, accepted): opening the chat is reading
     it; a poll that brings a message draws it on the open page, so it is read too. A 204 draws
     nothing. **Revisit when** a message can be missed on an open page (a long chat scrolled
     up).
D18. **The count on every page, by a context processor** (Claude's default, accepted): the
     navigation is in `base.html`, which every view renders; a context processor is how Django
     gives every template the same value. One query per page for workers and employers.
D19. **Messages, not chats, are counted** (Claude's default, accepted): "3" says how much is
     waiting, as in messengers; the "Chats" page shows which chat has them.
D20. **Newest activity first** (Claude's default, accepted): the chat that just got a message
     is on top; a new chat without messages counts from its application.
D21. **The last message in the row** (Claude's default, accepted): as in messengers; one
     subquery, not a query per row.
D22. **No count on the "Chat" buttons** (Claude's default, accepted): the "Chats" page has it
     (D16).
## Known limitations (→ docs/SECURITY.md)

- The messages are stored in plain text in the database: whoever has database access can
  read them (the Supabase account).
- No limit on how many messages someone sends.
- An open chat asks the server every 4 seconds, also in a tab in the background (the
  browser slows it down there): each costs a request, mostly a 204 (D11, D13).

## Differences from the mockups

| Mockup | App | Why |
|---|---|---|
| "Application accepted · Tue 20 Oct" | a date line per day | D8 |
| "translated from Ukrainian · original" | not shown until #36 | #36 |
| a send icon without a label | a "Send" button | a label every language can read; changed after the screenshots if I decide so |
| — | a "Chats" page and a count in the menu | D16 |
| "New messages load every few seconds" | "New messages appear every few seconds.", above the form | D14 |
