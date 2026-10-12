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

## Worker: find a job, apply, get accepted

| Jobs list + filters | Job detail + apply | Map, near me | My applications |
| --- | --- | --- | --- |
| <img src="jobs-list.png" width="180" alt="Jobs list + filters"> | <img src="job-detail.png" width="180" alt="Job detail + apply"> | <img src="map.png" width="180" alt="Map, near me"> | <img src="my-applications.png" width="180" alt="My applications"> |
| #18 | #19, #22, #32, #64 | #41, #42 | #25, #26 |

## Employer: post a job, pick workers, chat, review

| Post a job | My jobs + applications | Chat, dark mode | Worker profile + review |
| --- | --- | --- | --- |
| <img src="post-a-job.png" width="180" alt="Post a job"> | <img src="my-jobs.png" width="180" alt="My jobs + applications"> | <img src="chat.png" width="180" alt="Chat, dark mode"> | <img src="worker-profile.png" width="180" alt="Worker profile + review"> |
| #16, #17, #64 | #20, #23, #24 | #35, #36 | #38, #39 |

## Decided differently

| Screen | Mockup | App | Decided in |
| --- | --- | --- | --- |
| Post a job | "From · To" | start time + hours | #15 (`docs/specs/job.md` D2) |
| Post a job | district found on the map | district drop-down until geocoding (#41) | #16 |
| Post a job | rate "12,00" with a comma | a dot until the translations (M5) | #16 |
