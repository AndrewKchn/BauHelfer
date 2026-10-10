---
name: ai-log
description: Draft a docs/AI_LOG.md entry for the current ticket or session. Use at the end of a ticket, before opening the PR, or when the student asks to log a session.
---

# /ai-log

Draft — never write on your own. The student edits the draft in their own words; the "why"
behind every decision is theirs, not yours.

## 1. Collect material

- The current conversation: what was asked, what you suggested, what the student accepted,
  changed or rejected, and their own ideas. This is the main source.
- The ticket: branch name `N-…` → `gh issue view N` (title, "Done when…").
- What changed: `git log --oneline main..HEAD` and `git diff --stat main...HEAD`.
- Earlier entries in `docs/AI_LOG.md` — follow the "Entry format" section there exactly.

No ticket (planning, process)? Use `Planning: <topic>` instead of `#N <title>`.

## 2. Draft the AI_LOG entry

Fill each section from facts in the session, not from general statements:

- **Task given to AI** — what was asked and what context the student gave.
- **AI helped** — concrete things generated or explained.
- **AI failed** — wrong code, outdated instructions, failing tests, missed edge cases, and how
  they were found. If nothing failed, write "nothing notable" — do not invent failures.
- **My part** — every suggestion the student rejected or changed, the student's own ideas,
  and what they checked by hand. Write *what* happened; for the reason write
  `TODO: your reason` unless the student already said it in the session (then quote or
  closely paraphrase them). If the student accepted every recommendation, do not write only
  "I chose the recommended option": write `TODO: why you accepted them` (e.g. a small ticket
  with little to decide, or the recommendation matched what you wanted, because …) and ask it.
- **Learned** — leave `TODO: what you can now explain`, with 1–2 suggestions in brackets.

Written in first person from the student ("I chose…"), in English, short.

## 3. Ask, then wait

Show the draft in the chat. Below it, ask the student 2–4 short questions about the
`TODO`s and anything you are unsure of (e.g. "Why did you pick X over Y?"). Reply in the
language the student is using.

Then stop. Do not edit any file until the student explicitly confirms the final text.

## 4. After confirmation

- Append the entry to the end of `docs/AI_LOG.md` (today's date, newest at the bottom).
- It is committed on its own, as the last commit of the branch: "Add AI_LOG entry for #N"
  (only after the student's "yes").
