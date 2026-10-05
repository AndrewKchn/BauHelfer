---
name: sprint-docs
description: Draft the end-of-sprint doc changes from the sprint's "Docs sync — Mx" issue. Use in a Docs sync ticket (#94–#100), or when the student asks to sync the docs for a sprint.
---

# /sprint-docs

Draft — never write on your own. The student decides what goes into the docs.

## 1. Find the sprint

- Branch `N-docs-sync-…` → `gh issue view N --comments`: the milestone and every comment.
- No Docs sync branch? Ask which milestone.

## 2. Collect material

- **Comments** on the Docs sync issue — the main source. Each one is an item to handle.
- **Issues of the milestone:** `gh issue list --milestone "<title>" --state all --json number,title,state`.
- **What changed in the sprint:** `git log --oneline --merges --since=<sprint start>` (dates:
  Sprint field on the board) and `git diff --stat <first commit of the sprint>^ HEAD -- docs/ CLAUDE.md README.md`.
- **AI_LOG entries** of the sprint's tickets — ideas and decisions mentioned there.

## 3. Check the docs against reality

- `docs/PLAN.md`: milestone lists and issue counts match the board; new issues are listed;
  "Board and workflow" matches how we actually work.
- `CLAUDE.md`: every command still runs; structure and conventions are still true.
- `docs/SECURITY.md`: security / personal-data comments are covered; every link points to a
  file, function or test that exists (check with grep).
- `README.md`: run instructions and links still work.

## 4. Draft, ask, wait

Show in the chat, in the student's language:

1. A table: comment → proposal (into which doc / new issue / reject) → why.
2. Per doc: the proposed change as before → after.
3. 2–4 questions where you are unsure.

Then stop. Do not edit files, post replies or create issues until the student says "yes".

## 5. After "yes"

- Edit the docs; show each change as before → after with a link to the changed lines.
- Reply to each comment with the outcome (doc + commit, new issue #, or the reason it was
  rejected). Create new issues with milestone, label and Sprint.
- Commit per doc ("Update docs/PLAN.md for M2", …) — only after the student's "yes".
- Then continue with the ticket workflow in `CLAUDE.md`: "Done when…", `/ai-log`, PR.
