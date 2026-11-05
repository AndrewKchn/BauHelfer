# UI mockups

Phone screens (390 × 844) of the finished BauHelfer as planned in M3, drawn with AI during #15
and saved here in #122. They are **frozen**: they show the plan, not the app. Where a ticket
decides differently, the spec says so, and the screen stays as it is. In M8 the defense shows
them next to screenshots of the real app: planned → built.

Screens are drawn at 390 px (iPhone 12–14); the app itself is checked at 360 px, the project's
phone width (a small Android phone, `docs/TESTING.md`).

Before writing the spec of a ticket, find its screens below and compare: every difference
(a field, a label, a layout) becomes a decision in the spec, not a fix after the merge.

Details on a screen that are in no ticket yet (for example the distance on job cards or the
"2 / 3 workers found" bar) are proposals: the ticket decides whether they become features.

Each screen is shown 180 px wide; click it to see it full size.

The **Built** row shows the real app: one screenshot per screen in `built/`, 390 px wide, light
theme, full page, test data only. A ticket that changes a screen overwrites its file, so
`git log -- docs/mockups/built/<screen>.png` shows how the screen grew (decided in #19).
`uv run pytest tests/e2e/built_screenshots.py` takes them again with made-up data.

## Worker: find a job, apply, get accepted

| Jobs list + filters | Job detail + apply | Map, near me | My applications |
| --- | --- | --- | --- |
| <img src="jobs-list.png" width="180" alt="Jobs list + filters"> | <img src="job-detail.png" width="180" alt="Job detail + apply"> | <img src="map.png" width="180" alt="Map, near me"> | <img src="my-applications.png" width="180" alt="My applications"> |
| #18 | #19, #22, #32, #64 | #41, #42 | #25, #26 |
| **Built:** <img src="built/jobs-list.png" width="180" alt="Jobs list as built"> | <img src="built/job-detail.png" width="180" alt="Job detail as built"> | not built yet | <img src="built/my-applications.png" width="180" alt="My applications as built"> |

## Employer: post a job, pick workers, chat, review

| Post a job | My jobs + applications | Chat, dark mode | Worker profile + review |
| --- | --- | --- | --- |
| <img src="post-a-job.png" width="180" alt="Post a job"> | <img src="my-jobs.png" width="180" alt="My jobs + applications"> | <img src="chat.png" width="180" alt="Chat, dark mode"> | <img src="worker-profile.png" width="180" alt="Worker profile + review"> |
| #16, #17, #64 | #20, #23, #24 | #35, #36 | #38, #39 |
| **Built:** <img src="built/post-a-job.png" width="180" alt="Post a job as built"> | <img src="built/my-jobs.png" width="180" alt="My jobs as built"> <img src="built/job-applications.png" width="180" alt="Applications on the job page as built"> | not built yet | not built yet |

## Decided differently

| Screen | Mockup | App | Decided in |
| --- | --- | --- | --- |
| Post a job | "From · To" | start time + hours | #15 (`docs/specs/job.md` D2) |
| Post a job | district found on the map | district drop-down until geocoding (#41) | #16 |
| Post a job | rate "12,00" with a comma | a dot until the translations (M5) | #16 |
| Post a job | photo tiles in the form | photos are added on the job's edit page, which opens after "Publish" at `#photos`; the form says so | #64 (D10, D13, D21) |
| Post a job | an "Add" tile with a camera | a file field (several files) and an "Add photos" button | #64 (D14) |
| Jobs list | district · date · time on one line | district on its own line (cut with "…"), date and time below | #18 (D8) |
| Jobs list | "This week" | "Next 7 days" / "Next 30 days", counted from today | #18 (D12) |
| Jobs list | filters change the list at once | a "Show" button next to the district, the page reloads | #18 (D9, D11) |
| Jobs list | phone only | on laptops (from 1024 px) the filters are a column on the left | #18 (D13) |
| Jobs list | "No photo" tile | a hard-hat icon with "No photo" | #64 (D26) |
| Job detail | "1 of 3 workers found" | "Needs 3 workers" until someone is accepted, then "1 of 3 workers found" | #19, #24 (`docs/specs/accept-reject.md` D10) |
| Job detail | "Translated by AI" | not shown until the translations | #19 (#32) |
| Job detail | the employer's rating | not shown until the reviews | #19 (#39) |
| Job detail | "Workers I bring" with "−" / "+" | a number field | #22 (`docs/specs/application.md` D4) |
| Job detail | a big photo box | without photos a low strip instead | #19 (D11) |
| Job detail | phone only | the photo is 16 : 9 on a laptop | #19 (D11) |
| My jobs | one list | swipeable groups with status tabs | #20 (`docs/specs/my-jobs.md` D1, D2) |
| My jobs | a status badge on the card | none: the tab above says it | #20 (D13) |
| My jobs | "Demolition · Thu 22 Oct" on one line | the date on its own line under the job type | #20 (D9) |
| My jobs | the district | the photo square, the address above the district | #20 (D3) |
| My jobs | "Applications (3)" with the list in the card | "3 applications", a link to the job page; the job page shows the list to its employer instead of the employer card | #20, #23 (`docs/specs/applications-list.md` D15, D16) |
| My jobs | Accept / Reject in the card | on the job page, in the owner's list | #24 (`docs/specs/accept-reject.md`, `applications-list.md` D15) |
| My jobs | "Accept 2" | "Accept 2", or "Accept 1 of 2" when fewer places are left | #24 (D1) |
| My jobs | "Accepting 2 fills the job: you need only 1 more." | "Accepting fills the job: the other pending applications will be closed." | #24 (D9) |
| My jobs | "Workers found 2 / 3" bar in the card | the bar on the owner's job page | #24 (D11, D19) |
| My jobs | "Crew of 2 · ★ 4,7 (9) · work permit ✓" | "2 workers" in bold; no crew size, no "work permit ✓" | #24 (D22, D23) |
| My jobs | no way to take back an acceptance | "Cancel" on an accepted application | #24 (D2, D26) |
| My applications | one list with badges | tabs by status, as "My jobs"; no badge on the card, a photo instead | #26 (`docs/specs/my-applications.md` D1, D13) |
| My applications | "Open chat" | none until the chat | #26 (#35) |
| My applications | "Done", "Rate the employer" | none; accepted stays "Accepted" | #26 (#37–#39, D3) |
| My applications | green banner "… accepted your application" | none; an email instead | #26 (#27) |
| My applications | — | a "Withdraw" button and a "Past" tab | #26 (D3, D5) |
