# Spec: job photos (#64)

Status: **agreed for iteration 1**. D1 and D2 decided by the student on 2026-10-16; the
iteration 1 defaults (D3–D9) accepted by the student the same day, before any tests.

## Goal

Employers attach up to 5 photos to a job, so workers see the scope of the work (amount of
debris, floor, access) before they apply. Photos are personal data more often than it seems:
a phone photo carries the GPS position of the place where it was taken, so the location is
removed before a photo is stored.

The ticket comes in four iterations, each with its own failing tests → code → integration
tests:

1. **Photo model and processing:** `JobPhoto`, checking a file, resizing, removing EXIF,
   storing locally in `media/`. Visible in the admin only.
2. **Upload and delete in the job form** (employer).
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

## Iteration 2: upload and delete in the job form (to decide before its tests)

Open questions, criteria first:

- How several files arrive: one `<input type="file" multiple>` (the mockup's "Add" tile),
  five separate inputs, or a separate photo page after the job is saved.
- A file is chosen but the form has another error (date in the past): the browser does not
  send a file twice, so the employer would have to choose it again.
- Delete a photo on the edit page: a checkbox per photo saved with the form, or a button per
  photo that deletes it at once (POST).
- The hint under the photos: "Location data is removed from photos." (mockup).

## Iteration 3: thumbnail on the job list (to decide before its tests)

- The list shows 20 cards: 20 photos of 300 KB is 6 MB on a phone. Store a small copy
  (about 400 px) next to each photo at upload, or let the browser shrink the big one.
- The mockup's "3 photos" on the thumbnail and the "No photo" tile.

## Iteration 4: production storage (to decide before its tests)

- Public bucket (a fixed address per photo, cacheable) or private (a link that expires,
  made by the S3 backend on every page).
- Env variables for `.env.example` and Render; check the current free limit.

## Differences from the mockups

| Screen | Mockup | App | Why |
|---|---|---|---|
| Job detail | big photo with "1 / 3" | not in this ticket | D1, #19 |
| Post a job | "Photos (2 of 5)" with tiles and "Add" | decided in iteration 2 | — |
| Jobs list | thumbnail with "3 photos", "No photo" tile | decided in iteration 3 | — |
