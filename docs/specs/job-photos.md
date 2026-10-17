# Spec: job photos (#64)

Status: **iterations 1 and 2 agreed and built**. D1 and D2 decided by the
student on 2026-10-16; the iteration 1 defaults (D3–D9) accepted by the student the same day,
before any tests. Iteration 2: D10–D13 decided by the student on 2026-10-17; defaults
D14–D19 accepted by the student the same day, before any tests; D20–D24 after looking at the
built edit page the same day. Iteration 3: D25–D28 decided by the student on 2026-10-17
after an experiment with three placeholder icons at 360 px; defaults D29 accepted.
Iteration 4: D30–D32 decided by the student on 2026-10-17; defaults D33 accepted.

## Goal

Employers attach up to 5 photos to a job, so workers see the scope of the work (amount of
debris, floor, access) before they apply. Photos are personal data more often than it seems:
a phone photo carries the GPS position of the place where it was taken, so the location is
removed before a photo is stored.

The ticket comes in four iterations, each with its own failing tests → code → integration
tests:

1. **Photo model and processing:** `JobPhoto`, checking a file, resizing, removing EXIF,
   storing locally in `media/`. Visible in the admin only.
2. **Upload and delete on the job's edit page** (employer).
3. **Thumbnail on the job list.**
4. **Production storage:** Supabase Storage.

## Decisions taken before the spec (student, 2026-10-16)

D1. **The job detail page is not built here; showing photos on it moves to #19.** The
    ticket's "Photos shown on the job detail page" assumed #19 was done; it is not. The
    student's criterion: "first the photo support, the page comes later". #19 gets a
    "Done when" line for the photos (drafted at the end of this ticket, posted after "yes").
    Rejected: building a small detail page here (it is #19's work, and #19 decides who sees
    the address). **Revisit when** #19 starts: the photos go on its page.
D2. **Production photos go to Supabase Storage, not Cloudflare R2.** The student checked R2:
    it needs a payment card even for the free tier, and the project runs on free tiers with
    no card. Supabase is free without a card, the project already has a Supabase account
    (the database, Frankfurt), so the data stays in the EU in a place that is already listed.
    Both speak the S3 protocol, so the same `django-storages` S3 backend and `boto3` (already
    approved) serve either; moving to R2 later means new env values, one line for the public
    address and copying the files (the database stores only the path, `job_photos/….jpg`).
    Free limit: 1 GB or 500 MB (sources disagree, iteration 4 checks); a photo after
    resizing is about 200–400 KB, so hundreds of jobs fit. Rejected: R2 (card), Backblaze B2
    (one more account, the EU region must be chosen at sign-up and cannot change).
    **Revisit when** photos need more than the free limit, or Supabase pauses the project in
    a way that hurts the demo. This changes the ticket's "Production uses R2" and
    `docs/PLAN.md` (comment for Docs sync — M3).

## Iteration 1: photo model and processing

### Requirements

R1. New dependency `Pillow` (approved in the ticket). Django's `ImageField` needs it.
R2. Model `JobPhoto` in `jobs/models.py`: `job` (FK to `Job`, `on_delete=CASCADE`,
    `related_name="photos"`), `image` (`ImageField`), `uploaded_at` (`auto_now_add`).
    Ordered by `uploaded_at`, then `id` (the first photo is the one the list shows, #3).
R3. `Job.MAX_PHOTOS = 5`, the one place for the limit (D6).
R4. One function checks and prepares an uploaded file: `prepare_photo(file)` in a new
    `jobs/photos.py`. It raises `ValidationError` with a message for the user, or returns a
    new file ready to store (D3). It checks, in this order:
    - size at most 5 MB, before the file is opened (an error names the limit);
    - Pillow can open it and its **real format** (read from the content, not from the file
      name or the type the browser sends) is JPEG, PNG or WebP (D4);
    - not more than Pillow's pixel limit (about 89 megapixels): a small file that unpacks to a
      gigantic picture ("decompression bomb") is refused, not opened.
R5. `prepare_photo` then:
    - turns the picture upright using its EXIF orientation (`ImageOps.exif_transpose`):
      phones save a portrait photo lying on its side plus a "rotate me" note in EXIF, so
      without this step removing EXIF would leave portrait photos sideways;
    - shrinks it to at most 1600 px on the long side, keeping the proportions; a smaller
      picture is not enlarged;
    - saves it as JPEG, quality 85, **without any EXIF** (no GPS, no camera, no date) (D5).
R6. The stored file gets a random name, `job_photos/<32 hex characters>.jpg` (D7). The
    original file name is not kept.
R7. When a `JobPhoto` row is deleted — on its own, with its job, or with the employer's
    account (cascade) — its file is deleted from storage too, after the database change is
    committed (D8).
R8. Local development: `MEDIA_ROOT = BASE_DIR / "media"`, `MEDIA_URL = "/media/"`;
    `config/urls.py` serves media files only when `DEBUG` is on (Django's `static()` helper
    does nothing otherwise). `media/` is already in `.gitignore`.
R9. Tests never touch the disk or the network: an autouse fixture in the root `conftest.py`
    switches the default storage to Django's `InMemoryStorage` (like `fast_password_hasher`).
R10. Admin: the job page in `/admin/` shows the job's photos as an inline (add, delete,
     at most `Job.MAX_PHOTOS`); an uploaded file goes through `prepare_photo` too (D9).
R11. Every UI string (error messages, labels) is wrapped in `gettext_lazy`.

### Out of scope (iteration 1)

- The employer's job form: iteration 2. The job list: iteration 3. Supabase: iteration 4.
- The detail page: #19 (D1).
- Recognising faces, number plates or house numbers in a photo: a photo can still show a
  person. Iteration 2 tells the employer what is removed and what is not (limitation for
  `docs/SECURITY.md`).

### Acceptance criteria (→ tests)

AC1. A JPEG, a PNG and a WebP are accepted; each comes back as a JPEG.
AC2. A text file named `photo.jpg`, and a GIF, are refused with an error message.
AC3. A file over 5 MB is refused, and the error names 5 MB.
AC4. A picture over the pixel limit is refused (the limit is lowered in the test, so it does
     not need a huge file).
AC5. A 4000 × 3000 picture comes back 1600 × 1200; a 3000 × 4000 one 1200 × 1600; an
     800 × 600 one stays 800 × 600.
AC6. A JPEG with GPS and camera EXIF comes back with no EXIF at all.
AC7. A photo stored on its side with EXIF orientation "rotate 90°" comes back upright
     (width and height swapped) and without EXIF.
AC8. The stored name matches `job_photos/<32 hex>.jpg`; the original name does not appear.
AC9. Deleting a photo, deleting its job, and deleting the employer each remove the file
     from storage.
AC10. `job.photos.all()` returns the photos oldest first.
AC11. In the admin, a job page with 5 photos does not offer a 6th; an uploaded photo there
      has no EXIF.

### Defaults for iteration 1 (object to any line)

Small choices with a default, per the rule from #18. Each has "Revisit when".

| | Default | Why | Rejected | Revisit when |
|---|---|---|---|---|
| D3 | All checks and processing in **one function**, `prepare_photo`, called by every form that takes a photo (admin now, job form in iteration 2) | Unit tests need no database and no view; one place to read at the defense | Processing in `JobPhoto.save()` (runs again on every save; errors there are not form errors) | a third place uploads photos |
| D4 | The format is read **from the content** by Pillow | A file name and the browser's type are typed by the sender and can lie | Checking the extension or `content_type` | — |
| D5 | Everything is stored as **JPEG, quality 85** | One format every browser and mail client shows; PNG screenshots shrink a lot | WebP (about 30 % smaller, but not every old tool opens it); keeping the original format | the free storage limit gets close: switch to WebP |
| D6 | The limit of 5 is checked **in forms** (admin inline, job form), not in the database | A database rule "at most 5 rows per job" needs a trigger; two uploads at the same second are not a real risk here | A database trigger | photos come from somewhere other than a form (an API) |
| D7 | Random file name | The original name can hold a person's name ("Familie_Maier_Bad.jpg") and two files with the same name would clash | `upload_to="job_photos/"` with the original name | — |
| D8 | Files are deleted by a **`post_delete` signal**, after commit (`transaction.on_commit`) | Django never deletes a file when its row goes, and a `delete()` method on the model is **not called** for a cascade or a queryset delete; the signal is. After commit, so a rolled-back delete does not lose the file | Overriding `JobPhoto.delete()`; a cleanup command (needs cron, paid on Render) | a job "delete" button for employers appears (today they only cancel; deletion is admin or account deletion) |
| D9 | Photos also in the **admin** | Iteration 1 can be tried in the browser before the job form exists; staff can remove a bad photo | Admin without photos | — |

the stored 1600 px photos **shrunk by CSS** | At most 5 on one page, so the size does not matter here; the list (iteration 3) is where it does | Small copies just for this page | — |
| D16 | With 5 photos the upload form **disappears**, a line says it is the maximum | The employer sees at once why nothing can be added | A disabled field | — |
| D17 | **All or nothing**: one bad file, none of the batch is saved | One clear message, nothing half done, simple code | Saving the good ones and reporting the bad one (two kinds of result to show) | employers often mix good and bad files |
| D18 | Errors come back as a **message after a redirect**, not as form errors on a re-rendered page | The add view would otherwise have to rebuild the whole edit page with the job form; a redirect reuses it. The photo form has one field, so there is nothing to keep | Re-rendering the edit page from the add view | the photo form gets more fields (captions) |
| D19 | "×" deletes **at once, no "Are you sure?"** | A photo is cheap to add again; one tap on a phone | A `confirm()` in JS, or a confirmation page | photos are deleted by mistake |## Iteration 2: upload and delete on the job's edit page

### How it works for the employer (D10)

1. "Post a job": the form as today, without photos. Above "Publish job" a line says that
   photos can be added after publishing (D13).
2. "Publish job" saves the job and opens **its edit page** (not "My jobs"), with the message
   "Job posted. You can add photos below."
3. The edit page is the job form as today, and under it a block "Photos (2 of 5)": the
   photos with a "×" button each, and a field to choose photos (several at once, D12) with
   an "Add photos" button.
4. Adding or deleting a photo reloads the same edit page with a message. The job's own
   fields are already saved, so nothing typed is lost (except unsaved edits, see D11).

```mermaid
sequenceDiagram
    actor E as Employer
    participant C as JobCreateView
    participant Ed as JobEditView (edit page)
    participant A as JobPhotoAddView
    participant D as JobPhotoDeleteView
    E->>C: POST "Publish job"
    C-->>E: 302 → /jobs/<pk>/edit/ "Job posted. You can add photos below."
    E->>Ed: GET edit page: job form + "Photos (0 of 5)"
    E->>A: POST /jobs/<pk>/photos/ (3 files)
    A-->>E: 302 → edit page "3 photos added."
    E->>D: POST /jobs/photos/<id>/delete/
    D-->>E: 302 → edit page "Photo deleted."
```

### Requirements

R12. `JobCreateView` redirects to the new job's edit page (`job_edit`), with the message
     "Job posted. You can add photos below." (D10). Today it goes to "My jobs" (#16 R11): that
     test changes.
R13. The "Post a job" page shows, above "Publish job": "You can add photos after you publish
     the job." (D13). The edit page does not.
R14. The edit page shows, under the job form and before "Back to my jobs", a block with the
     heading "Photos (N of 5)" and the job's photos in upload order, each as a small picture
     with a "×" delete button (D15). No photos: "No photos yet."
R15. Under the photos, a separate form (`enctype="multipart/form-data"`, its own `<form>`, not
     inside the job form): one file field that takes several files (`multiple`,
     `accept="image/jpeg,image/png,image/webp"`), the button "Add photos" and the hint
     "Location data is removed from photos." (from the mockup). With 5 photos the form is
     not shown; the text "That is the maximum of 5 photos." is (D16).
R16. `POST /jobs/<pk>/photos/` (`job_photo_add`): only the employer's own **open** job
     (`OwnOpenJobMixin`, like edit and cancel: otherwise 404; guests to login, workers 403).
     `JobPhotosForm` checks every file with `prepare_photo()` and that the photos already
     there plus the new ones are at most `Job.MAX_PHOTOS`.
     - All valid: all are saved, message "N photos added." (singular for 1), redirect to the
       edit page.
     - Any error: **none** is saved (D17); an error message names the file and the reason
       ("plan.gif: Upload a photo in JPEG, PNG or WebP format.") or how many more fit ("You
       can add 2 more photos."); redirect to the edit page (D18).
     - No file chosen: message "Choose at least one photo.", redirect.
     - GET: 405 (only POST).
R17. `POST /jobs/photos/<id>/delete/` (`job_photo_delete`): deletes the photo only if its job
     is the logged-in employer's own open job, otherwise 404. Message "Photo deleted.",
     redirect to the edit page. No confirmation (D19). GET: 405. The file goes by the signal
     of iteration 1.
R18. Unsaved changes (D11): when a field of the job form was changed and the employer leaves
     the page without "Save job" (adding a photo, deleting one, "Back", closing the tab), the
     browser asks whether to leave. A few lines of plain JavaScript in `job_form.html`; saving
     the job form does not ask.
R19. Every UI string is wrapped in `{% translate %}` / `gettext_lazy`; "N photos added." and
     "Photos (N of 5)" with plural forms where the number changes the words.

### Out of scope (iteration 2)

- Choosing photos already on the "Post a job" page (D10). Reordering photos, choosing a
  "main" photo, captions.
- Photos of a job that is not open (cancelled, filled): the edit page is for open jobs only
  (#16 D2), so they cannot be changed; they stay.
- Thumbnails on the job list: iteration 3.

### Acceptance criteria (→ tests)

AC12. "Publish job" redirects to `/jobs/<pk>/edit/` of the new job with "Job posted. You can
      add photos below."
AC13. The create page shows "You can add photos after you publish the job."; the edit page
      does not.
AC14. The edit page of a job with 2 photos shows "Photos (2 of 5)", both pictures and two
      delete forms posting to `job_photo_delete`; the upload form posts to `job_photo_add`
      with `multipart/form-data` and a `multiple` file field.
AC15. With 5 photos the upload form is not on the page and "That is the maximum of 5
      photos." is.
AC16. Posting 3 valid photos saves 3 photos without EXIF and says "3 photos added."
AC17. Posting 2 valid files and 1 GIF saves none and the message names the GIF's file name.
AC18. A job with 4 photos: posting 2 saves none and says "You can add 1 more photo."
AC19. Posting no file: "Choose at least one photo.", nothing saved.
AC20. Add and delete as another employer, or on a cancelled job: 404, nothing changes. As a
      guest: redirect to login; as a worker: 403.
AC21. Delete as the owner: the photo row and its file are gone, "Photo deleted.", redirect to
      the edit page.
AC22. GET on both URLs: 405.
AC23. `JobPhotosForm` unit tests: a list of valid files gives prepared JPEGs; the count check
      counts the photos already there.
AC24. The edit page contains the unsaved-changes script (its behaviour is checked in the M3
      E2E ticket #21, not here: only E2E runs JavaScript).

### Decisions (student, 2026-10-17)

D10. **Photos are added on the job's edit page, after the job is saved; "Publish" opens that
     page** (option C2). Options compared with their cost: A) one `multiple` field in the job
     form (as in the mockup; chosen files are lost when another field has an error, and a
     preview needs JS); B) five file fields (clumsy on a phone); C1) a separate "Photos" page
     after publishing; C2) the same, but the photo block is drawn under the job form on its
     edit page; C3) C2 without a reload, via HTMX (the "Back" problems of #18). The
     student's criteria: simple code, photos are never lost, ease of use; the mockups are
     drafts, small JS is fine, a job may have no photos. C2 needs no new page, only two small
     views that come back to the edit page; the job form and the photo form never share a
     request, so the "files lost on an error" problem cannot happen. The student's own
     idea: "after Save the add-photo part appears below". Rejected: A, B, C1, C3.
     **Revisit when** employers ask for photos on the first screen, or a preview before
     publishing.
D11. **The browser warns about unsaved changes** (option ii). Two forms on one page: an
     employer who edits the description and then adds a photo would lose the edit
     silently. About 5 lines of JS. Rejected: no warning (silent loss); saving the job
     form together with the photos (mixes the two forms again).
D12. **Several photos in one go** (`multiple`). Picking 3 photos once in the phone gallery is
     easier than three times. Costs a small `MultipleFileField` from the Django docs (Django
     has no field for several files). Rejected: one photo per upload.
D13. **A line on "Post a job" that photos come after publishing** (the student's idea), so
     the employer does not look for the photo field in vain.

### Defaults for iteration 2 (object to any line)

| | Default | Why | Rejected | Revisit when |
|---|---|---|---|---|
| D14 | Upload by choosing the files **and pressing "Add photos"**; no auto-upload on choose | Works without JS; the employer sees what was chosen before it goes | `onchange="this.form.submit()"` (one line of JS, one tap less) | employers forget to press the button |
| D15 | The edit page shows 

### Changes after looking at the edit page (student, 2026-10-17)

On a 360 px phone the photo block starts below the first screen; what the employer sees
after "Publish job" is the job form ending in a big "Save job" button. The student found it
confusing (does it save the photos? must I press it?), and the "Add photos" button had a
third colour. Options offered with their cost: a) rename the button, b) headings for the two
parts, c) jump to the photos after publishing, d) the save button inactive until something
changes, e) photos above the form. The student chose a, b, c and d, and then dropped the
"Edit job" title (D24).

R20. On the edit page the job form has the heading "Job details" and its button says "Save
     changes" (D20); there is no "Edit job" title above it, "Job details" is the page's
     `<h1>` (D24). The browser tab still says "Edit job". The create page keeps "Post a job" /
     "Publish job" without the heading.
R21. The photo block has `id="photos"`; publishing redirects to `/jobs/<pk>/edit/#photos`, so
     the browser scrolls to it (D21). Saving changes still goes to "My jobs".
R22. On the edit page "Save changes" is inactive until a field of the job form is changed;
     the same script that warns about unsaved changes (R18) turns it on (D22). Without
     JavaScript it stays active. A page shown again with errors keeps it active and counts as
     changed (the typed values are not saved yet).
R23. "Add photos" has the same colour as "Save changes" (`btn-primary`) (D23).

AC25. Publishing redirects to the edit page with `#photos`; the photo block has `id="photos"`.
AC26. The edit page shows "Job details" and "Save changes" and not "Save job"; the create
      page shows "Publish job" and not "Job details".
AC27. The edit page marks the job form as an edit (`data-edit`) for the script; the edit page
      shown again after an error marks it as having unsaved changes.
AC28. "Add photos" and "Save changes" both carry `btn-primary`.

D20. **"Save changes" and a "Job details" heading** (options a, b). The button names what it
     saves; the two headings make the page read as two parts with a button each.
     Rejected: "Save job" (could mean "save everything, photos too").
D21. **After publishing, the page opens at the photos** (option c): a `#photos` anchor in the
     redirect, no JavaScript. The form stays above for whoever wants it. Rejected: photos
     above the form (e: they would be in the way when only a date changes).
     **Revisit when** the detail page (#19) exists and "Publish" might rather show the job.
D22. **"Save changes" is inactive until something changes** (option d). An inactive button is
     not pressed "to be sure". Two lines added to the existing script; a page without
     JavaScript keeps the button active, so nothing breaks.
D23. **"Add photos" in the same colour as "Save changes"** (the student's choice over an
     outlined button): with D22 only one of the two looks active at a time.
D24. **No "Edit job" title on the edit page** (the student's idea): with "Job details" and
     "Photos" the page explains itself, and the form starts higher on a phone. "Job details"
     takes over the `<h1>` (one per page, for screen readers) in the size of "Photos".

## Iteration 3: thumbnail on the job list

Each card on the job list gets a square on the left: the job's first photo with "3 photos",
or a hard-hat placeholder with "No photo". The list loads small copies, not the big photos.

### Requirements

R24. `JobPhoto.thumbnail`: a second `ImageField`, stored as
     `job_photos/thumbs/<32 hex characters>.jpg`; may be empty (D29: photos saved before
     this field existed have none).
R25. `make_thumbnail(file)` in `jobs/photos.py`: a 300 × 300 square cut from the middle of
     the picture (like CSS `object-cover`), JPEG quality 85, no EXIF (D25, D29).
R26. `JobPhoto.save()` makes the thumbnail from `image` when the photo has an image and no
     thumbnail yet; saving again does not make a new one. Admin, the job form and tests all
     go through it.
R27. `JobPhoto.thumbnail_url`: the thumbnail's address, or the big photo's when there is no
     thumbnail (D29).
R28. Deleting a photo deletes both files (extends R7).
R29. Job list card (`_job_card.html`): a 72 px square on the left of the text (D29), rounded.
     - With photos: the first photo (`thumbnail_url`), cut to fill the square, and a label in
       its corner "1 photo" / "3 photos" (D27).
     - Without: `templates/jobs/_photo_placeholder.html`, a hard-hat icon (inline SVG drawn
       for the project, colours from the theme) and "No photo", pale on a muted background
       (D26). Kept as its own template for the detail page (#19).
     The text next to it may wrap ("Earthworks / digging" takes two lines at 360 px).
R30. `JobListView` loads the photos of all jobs on the page in one extra query
     (`prefetch_related("photos")`), so the number of database queries does not grow with
     the number of jobs (D28).
R31. Every UI string wrapped in `{% translate %}` / `{% blocktranslate count %}`.

### Out of scope (iteration 3)

- Thumbnails for photos stored before this iteration (only local test data): they show the
  big photo instead (R27).
- The map (#42) and the detail page (#19) use the same pieces later.

### Acceptance criteria (→ tests)

AC29. `make_thumbnail` turns a 4000 × 3000 and a 3000 × 4000 picture into 300 × 300 JPEGs
      without EXIF.
AC30. Saving a new `JobPhoto` stores a thumbnail under `job_photos/thumbs/<32 hex>.jpg`;
      saving it again keeps the same thumbnail.
AC31. Deleting a photo removes the photo file and the thumbnail file.
AC32. `thumbnail_url` is the thumbnail's address; with the thumbnail cleared, the photo's.
AC33. The list card of a job with 3 photos shows the first photo's thumbnail and "3 photos";
      with 1 photo "1 photo".
AC34. The list card of a job without photos shows "No photo" and the placeholder icon.
AC35. The home page with 2 jobs with photos and with 5 jobs with photos makes the same number
      of database queries.

### Decisions (student, 2026-10-17)

D25. **A small copy is made at upload** (option B). Options with their cost: A) the browser
     shrinks the 1600 px photo (up to 6–8 MB for 20 cards on mobile data); B) a 300 px copy
     at upload (~0.5 MB for 20 cards, most code: second field, migration, both files
     deleted); C) A with `loading="lazy"` (one attribute, ~1.5 MB at first). Rejected: A, C.
D26. **The placeholder is a hard hat** (the student asked for "something from construction"
     instead of my landscape). An experiment, not committed, showed a hard hat, a brick wall
     and a traffic cone on the real list at 360 px in both themes; the brick wall read like a
     table, the cone like road works. Rejected: an icon per job type (8+ icons to keep), the
     BauHelfer initials (say nothing), a plain empty square.
D27. **"3 photos" on the thumbnail**, as in the mockup: the worker sees at once how many
     photos there are. Until #19 there is no page that shows them all.
D28. **The list loads the photos in one query** (`prefetch_related`). Without it Django asks
     the database once per card: 20 more queries per page (the "N+1" problem). The test
     compares two page sizes, so it catches the problem itself, not one number.

### Defaults for iteration 3 (accepted)

| | Default | Why | Rejected | Revisit when |
|---|---|---|---|---|
| D29 | 300 × 300 cut from the middle; made in `JobPhoto.save()`; old photos fall back to the big photo; pale icon; a 72 px square; long job types may wrap | 72 px on a ×3 screen needs ~216 px; `save()` is the one place every photo passes; a data migration only for local test data is not worth its code; "nothing here" should not shout | A coloured icon; a 64 px square (still wraps); generating copies for old photos | photos exist in production before this iteration (they do not) |

## Iteration 4: production storage in Supabase

Production keeps uploaded photos in a Supabase Storage bucket through its S3 protocol (D2);
locally and in tests nothing changes (`media/`, in-memory). Only settings change: models,
forms and templates only know `photo.image.url`.

### Requirements

R32. New dependencies `django-storages[s3]` and `boto3` (approved in the ticket).
R33. `config/settings/production.py`: `STORAGES["default"]` is `storages.backends.s3.S3Storage`
     with these values from env variables (D33):
     - `MEDIA_S3_ENDPOINT_URL`: the bucket service's S3 address (Supabase: Storage → Settings
       → S3 Connection → Endpoint);
     - `MEDIA_S3_REGION`: its region (same page);
     - `MEDIA_S3_ACCESS_KEY_ID`, `MEDIA_S3_SECRET_ACCESS_KEY`: an S3 access key (secret);
     - `MEDIA_S3_BUCKET`: the bucket name, `job-photos`;
     - `MEDIA_PUBLIC_URL`: the address photos are shown from (Supabase:
       `<project-ref>.supabase.co/storage/v1/object/public/job-photos`).
R34. All six are **required** in production: a missing one stops the server at start with
     Django's "Set the … environment variable" error, like `DATABASE_URL` (D31).
R35. Photo addresses are plain public URLs on `MEDIA_PUBLIC_URL`, without a signature
     (`custom_domain`, D30: django-storages never signs those, so no `querystring_auth`
     setting is needed; the mutation check found that line had no effect); path-style
     addressing; files are never overwritten (random names anyway). `MEDIA_PUBLIC_URL` may be
     written with `https://` in front or `/` at the end (found in the manual check: the
     copied address brought `https://` along, which would break every photo silently).
R36. `.env.example` lists the six variables with comments; `render.yaml` lists them, the
     two secrets with `sync: false`.
R37. Local settings and tests do not change: `FileSystemStorage` in `media/`,
     `InMemoryStorage` in tests (R8, R9). No test touches the network.
R38. Before the PR is made ready: one manual upload with production storage settings against
     the real bucket (D33); the key used for it is deleted afterwards and Render gets a new
     one. Done 2026-10-17: photo and thumbnail uploaded, both public URLs answered
     `200 image/jpeg`, deleting the employer removed both files from the bucket.

### Out of scope (iteration 4)

- Photos may show a house number or a face, while #19 plans to hide the exact address until
  an application is accepted (D32): an open question for Docs sync, `docs/SECURITY.md`.
- Moving existing photos between storages (there are none in production yet).

### Acceptance criteria (→ tests)

AC36. With the six variables set, production's default storage is the S3 backend with the
      endpoint, region, keys, bucket and public address from them, unsigned URLs.
AC37. With any one of the six missing, loading the production settings fails with
      `ImproperlyConfigured` naming that variable.
AC38. The static files storage in production stays WhiteNoise's (the existing test, unchanged).
AC39. `.env.example` and `render.yaml` name all six variables; `render.yaml` marks the two
      secret ones `sync: false`.
AC40. Local settings still store uploads on disk in `media/` (FileSystemStorage).

### Decisions (student, 2026-10-17)

D30. **Public bucket.** Options with their cost: a public bucket gives every photo a fixed
     address the browser caches (2 settings); a private one gives a signed link that
     expires, made anew on every page, so the browser downloads the photo again each time
     and the free egress (~5 GB/month) goes faster. Photos are public on the job list anyway
     (#18 D1) and their names are random (128 bits). Rejected: private bucket.
     **Revisit when** photos should be visible only to some users.
D31. **Missing storage variables stop the server**, like a missing `DATABASE_URL`. The
     other option, falling back to the Render disk, would work until the next deploy and
     then lose every photo silently. Rejected: the fallback.
D32. **The "house number or face on a photo" question waits** (the student's choice): noted
     for Docs sync — M3 and `docs/SECURITY.md`. A one-line hint at the upload ("Avoid house
     numbers and faces.") was offered and not taken now.
     **Revisit when** #19 hides the address: a photo of the facade would show it anyway.

### Defaults for iteration 4 (accepted)

| | Default | Why | Rejected | Revisit when |
|---|---|---|---|---|
| D33 | Variable names `MEDIA_S3_*` / `MEDIA_PUBLIC_URL` (not `SUPABASE_*`); bucket `job-photos`; one manual upload before merge, then the key used for it is deleted and Render gets a new one (planned as two keys; the check ran with the first `bauhelfer-render` key, so that one was deleted and recreated for Render), the production key only on Render | Moving to R2 (D2) changes values, not names; tests never reach the network, and boto3 ≥ 1.36 sends new checksums some S3-compatible services refuse, which only a real upload shows; a leaked laptop `.env` must not hold the production key | `SUPABASE_*` names; no manual check; one shared key | the manual upload fails (then: boto3 client config `request_checksum_calculation="when_required"`) |

## Differences from the mockups

| Screen | Mockup | App | Why |
|---|---|---|---|
| Job detail | big photo with "1 / 3" | not in this ticket | D1, #19 |
| Post a job | "Photos (2 of 5)" with tiles and "Add" | no photos here; a line says they come after publishing; the block is on the edit page | D10, D13 |
| Post a job | "Add" tile with a camera icon | a file field and an "Add photos" button | D14 |
| Jobs list | "No photo" tile | a hard-hat icon with "No photo" | D26 |
