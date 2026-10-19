# Security

What BauHelfer protects, how, where in the code, and which tests check it. Written for
reviewers and anyone reading the code. Updated whenever a ticket touches security or personal
data.

Most protections come from Django itself. Our part is to switch them on, not to replace them
with our own code, and to keep tests that fail if someone breaks them.

## Reporting a vulnerability

Please **do not open a public issue**. Use **"Report a vulnerability"** on the repository's
[Security tab](https://github.com/AndrewKchn/BauHelfer/security). Only the maintainer sees the
report. This is a student project without a bug bounty; reports are answered as soon as
possible, and the fix is published before the details.

## Personal data we store

In [accounts/models.py](../accounts/models.py) and [jobs/models.py](../jobs/models.py):

- **Account:** email, password (as a hash), name, phone (optional), role, preferred language,
  and when a worker confirmed being allowed to work in Germany (`work_permit_confirmed_at`;
  empty = not confirmed, #13).
- **Worker profile (#11):** team size, skills, spoken languages, legal status. No district or
  address: no feature needs it.
- **Employer profile (#12):** company name (optional), trades. No address, VAT or registration
  number.
- **Job (#15):** the job's address — for a private employer this is their home address. It is
  stored as entered; only the job's own employer sees it (#19), everyone else the district.
- **Job photos (#64):** pictures the employer uploads, without EXIF (no GPS, no camera data),
  under random file names.

The phone is checked for a callable format: `+` and a country code or `0` and a German area
code, 10–15 digits (`validate_phone` in [accounts/validators.py](../accounts/validators.py),
used on `User.phone`, so the profile forms and the admin both check it; tests in
[test_phone.py](../accounts/tests/test_phone.py) and
[test_phone_views.py](../accounts/tests/test_phone_views.py), incl.
`test_admin_rejects_a_wrong_phone`). It is a data-quality check, not a security one.

Everything is stored in the EU, see [Hosting](#hosting-and-secrets).

## Accounts (#9)

| Protection | How | Code | Tests |
|---|---|---|---|
| Passwords are never stored in plain text | Django saves a salted PBKDF2 hash (1,000,000 rounds) | [accounts/forms.py](../accounts/forms.py) `SignupForm` (Django's `UserCreationForm`) | `test_valid_signup_creates_user_with_hashed_password` in [test_forms.py](../accounts/tests/test_forms.py), `test_production_hashes_passwords_with_pbkdf2` in [tests/test_deploy.py](../tests/test_deploy.py) |
| No weak passwords | Django's four password validators: not like the email, at least 8 characters, not a common password, not only digits | `AUTH_PASSWORD_VALIDATORS` in [config/settings/base.py](../config/settings/base.py) | `test_signup_with_weak_password_is_rejected` in [test_forms.py](../accounts/tests/test_forms.py) |
| Forms cannot be sent from another site (CSRF) | Every form has a secret `{% csrf_token %}`; without it the answer is 403 | `CsrfViewMiddleware` in [base.py](../config/settings/base.py) | `test_register_needs_the_csrf_token_from_the_page` in [test_views.py](../accounts/tests/test_views.py) |
| Another site cannot log people out | Logout works only by POST (a form), not by a link or an image. The header's "Log out" is a POST form with `{% csrf_token %}` | Django's `LogoutView` in [accounts/urls.py](../accounts/urls.py); menu in [templates/base.html](../templates/base.html) | `test_logout_by_link_is_not_allowed` in [test_views.py](../accounts/tests/test_views.py), `test_menu_logout_button_is_inside_the_post_form` in [test_onboarding_views.py](../accounts/tests/test_onboarding_views.py) |
| Login does not tell who is registered | The same "Wrong email or password." for an unknown email and for a wrong password | `LoginForm` in [accounts/forms.py](../accounts/forms.py) | `test_login_with_unknown_email_shows_the_same_error_as_a_wrong_password` in [test_views.py](../accounts/tests/test_views.py) |
| Password reset does not tell who is registered | The same "Check your email" page for any address; an email goes only to real accounts | Django's `PasswordResetView` in [accounts/urls.py](../accounts/urls.py) | `test_password_reset_for_unknown_email_looks_the_same_but_sends_nothing` in [test_views.py](../accounts/tests/test_views.py) |
| A reset link works only once | The link's token depends on the current password hash, so it dies when the password changes. It also expires after 3 days (Django's default) | Django's `PasswordResetConfirmView` in [accounts/urls.py](../accounts/urls.py) | `test_password_reset_link_works_only_once` in [test_views.py](../accounts/tests/test_views.py) |
| A session id known before login is useless (session fixation) | Django's `login()` gives the user a new session id | `RegisterView` in [accounts/views.py](../accounts/views.py), Django's `LoginView` | `test_login_gives_a_new_session_id` in [test_views.py](../accounts/tests/test_views.py) |
| Login never sends the user to another site (open redirect) | `?next=` is followed only for addresses on our own site | Django's `LoginView` in [accounts/urls.py](../accounts/urls.py) | `test_login_ignores_a_next_link_to_another_site`, `test_login_goes_back_to_the_page_that_asked_for_it` in [test_views.py](../accounts/tests/test_views.py) |
| Only staff can open the admin | Django admin checks `is_staff` | [accounts/admin.py](../accounts/admin.py) | `test_non_staff_user_cannot_open_admin` in [test_admin.py](../accounts/tests/test_admin.py) |

## Roles and profiles (#10–#13)

| Protection | How | Code | Tests |
|---|---|---|---|
| A user without a role can only choose one | `OnboardingMiddleware` sends a logged-in user without a role to the role choice from every page (deny by default; allowed: role choice, logout, `/admin/`; staff skipped) | [accounts/middleware.py](../accounts/middleware.py) | `test_user_without_role_is_sent_back_to_the_role_choice` in [test_onboarding_views.py](../accounts/tests/test_onboarding_views.py), [test_onboarding.py](../accounts/tests/test_onboarding.py) |
| The role is chosen once | `RoleSelectView` redirects users who already have a role, so a second POST cannot change it; `RoleForm` accepts only `role` (fields like `is_staff` are ignored) and only `employer` / `worker` | `RoleSelectView` in [accounts/views.py](../accounts/views.py), `RoleForm` in [accounts/forms.py](../accounts/forms.py) | `test_role_cannot_be_changed_by_posting_the_form_again` in [test_onboarding_views.py](../accounts/tests/test_onboarding_views.py) |
| Profile pages only for their role | Login, else 403: workers cannot open employer pages and the other way round; staff without a role get 403 | `RoleRequiredMixin` in [accounts/views.py](../accounts/views.py) | `test_employer_gets_403`, `test_admin_without_role_gets_403`, `test_guest_must_log_in` in [test_worker_profile_views.py](../accounts/tests/test_worker_profile_views.py); `test_worker_gets_403` in [test_employer_profile_views.py](../accounts/tests/test_employer_profile_views.py) |
| Users edit only their own profile | No id in the URL, the form has no `user` field, the view sets `profile.user = request.user`; user and profile are saved in one `transaction.atomic()`. One profile per user (database constraint) | `ProfileEditView` in [accounts/views.py](../accounts/views.py) | `test_worker_cannot_save_a_profile_for_someone_else`, `test_employer_cannot_create_a_worker_profile` in [test_worker_profile_views.py](../accounts/tests/test_worker_profile_views.py); `test_employer_cannot_save_a_profile_for_someone_else`, `test_worker_cannot_create_an_employer_profile` in [test_employer_profile_views.py](../accounts/tests/test_employer_profile_views.py); `test_user_cannot_have_two_profiles` in [test_worker_profile.py](../accounts/tests/test_worker_profile.py), [test_employer_profile.py](../accounts/tests/test_employer_profile.py) |
| Role and profile forms cannot be sent from another site | `{% csrf_token %}` in every form | [templates/accounts/](../templates/accounts/) | `test_role_choice_needs_the_csrf_token_from_the_page` in [test_onboarding_views.py](../accounts/tests/test_onboarding_views.py); `test_profile_form_needs_the_csrf_token_from_the_page` in both profile view test files |
| Profile cards show no contacts | The cards the other side sees (#19, #23) have no phone or email; contacts only after acceptance (#25) | [_worker_profile_card.html](../templates/accounts/_worker_profile_card.html), [_employer_profile_card.html](../templates/accounts/_employer_profile_card.html) | `test_profile_card_has_no_contact_details` in both profile view test files |
| Invalid team sizes never reach the database | 1–10 in the form and as a `CheckConstraint` in the database | `WorkerProfile` in [accounts/models.py](../accounts/models.py) | `test_database_rejects_team_size_outside_1_to_10` in [test_worker_profile.py](../accounts/tests/test_worker_profile.py) |
| Only workers confirm the work permit, and the date is private | The required checkbox is only in the worker form (`WorkerUserForm`); employers are never asked. The date is shown only on the worker's own page; the card says only "Confirmed by the worker" / "Not confirmed". An admin can clear it. A data migration kept existing confirmations | `work_permit_confirmed_at`, `can_apply()` in [accounts/models.py](../accounts/models.py), `WorkerUserForm` in [accounts/forms.py](../accounts/forms.py), [0004_work_permit_confirmed_at.py](../accounts/migrations/0004_work_permit_confirmed_at.py) | `test_form_without_the_box_is_invalid`, `test_can_apply`, `test_migration_keeps_existing_confirmations` in [test_work_permit.py](../accounts/tests/test_work_permit.py); `test_profile_is_not_saved_without_the_box`, `test_employer_form_has_no_work_permit_box`, `test_profile_card_shows_confirmation_without_date`, `test_admin_shows_and_clears_the_confirmation` in [test_work_permit_views.py](../accounts/tests/test_work_permit_views.py) |

## Jobs (#15–#19)

| Protection | How | Code | Tests |
|---|---|---|---|
| Only employers post, edit and cancel jobs | Guests go to login, workers get 403; posting needs a company profile first | `EmployerRequiredMixin` (on `RoleRequiredMixin` from #12) in [jobs/views.py](../jobs/views.py) | `test_guest_is_sent_to_login`, `test_worker_gets_403` in [test_views.py](../jobs/tests/test_views.py) |
| An employer changes only their own open jobs, and learns nothing about others | Edit and cancel look the job up only in `request.user.jobs.open()`: another employer's job or a job that is not open gives **404, not 403**, so the answer does not reveal that it exists. One query for GET and POST | `OwnOpenJobMixin.get_queryset` in [jobs/views.py](../jobs/views.py) | `test_other_employer_gets_404`, `test_job_that_is_not_open_gives_404` in [test_views.py](../jobs/tests/test_views.py) |
| Owner and status cannot be posted | The form has no `employer` or `status` field: the view sets `employer = request.user`, the model sets `status = open`; extra POST fields are ignored | `JobForm` in [jobs/forms.py](../jobs/forms.py), [jobs/views.py](../jobs/views.py) | `test_posted_fields_for_owner_and_status_are_ignored` in [test_views.py](../jobs/tests/test_views.py), `test_form_fields` in [test_forms.py](../jobs/tests/test_forms.py) |
| Cancelling only on purpose | POST only; the GET page only asks. The row stays with `status = cancelled` | `JobCancelView` in [jobs/views.py](../jobs/views.py) | `test_cancel_page_asks_first`, `test_owner_cancels_a_job` in [test_views.py](../jobs/tests/test_views.py) |
| Job forms cannot be sent from another site | `{% csrf_token %}` in all three forms. The test client skips the CSRF check by default, so one test sends a POST without the token and one checks that each page puts it in its form | [templates/jobs/](../templates/jobs/) | `test_job_forms_need_the_csrf_token`, `test_job_form_pages_carry_the_csrf_token` in [test_views.py](../jobs/tests/test_views.py) |
| No job below the minimum wage (MiLoG) | The rate is checked against the minimum wage of the job's **date** (13.90 € in 2026, 14.60 € from 2027); the model validator keeps the lowest rate | `MINIMUM_WAGES` in [base.py](../config/settings/base.py), `minimum_wage_on` in [jobs/models.py](../jobs/models.py), `JobForm.clean` in [jobs/forms.py](../jobs/forms.py) | [test_minimum_wage.py](../jobs/tests/test_minimum_wage.py); `test_rate_one_cent_below_minimum_wage_of_the_date_is_rejected`, `test_same_rate_is_accepted_before_the_rise` in [test_forms.py](../jobs/tests/test_forms.py) |
| Invalid jobs never reach the database | `hours` and `workers_needed` stay 1–10 as `CheckConstraint`s; the employer field offers only users with the employer role; deleting an employer deletes their jobs | `Job` in [jobs/models.py](../jobs/models.py) | `test_out_of_range_is_rejected_by_database`, `test_only_employers_can_be_chosen_as_employer`, `test_deleting_employer_deletes_their_jobs` in [test_models.py](../jobs/tests/test_models.py) |
| The public job list shows no personal data | Guests see the list too. A card shows job type, rate, district, date, time and workers — **never the address, the description or the employer**. Only open jobs that have not started | [_job_card.html](../templates/jobs/_job_card.html), `JobListView` in [jobs/views.py](../jobs/views.py), `upcoming()` in [jobs/models.py](../jobs/models.py) | `test_card_shows_what_a_worker_needs_and_no_address`, `test_home_page_hides_jobs_that_are_not_open` in [test_job_list_views.py](../jobs/tests/test_job_list_views.py) |
| Filter values cannot do harm | A GET form (changes nothing, so no CSRF token needed). Every value is checked against the fixed lists; one that is not listed (`?district=moon`) is ignored without an error. Values go only into the ORM | `JobFilterForm` in [jobs/forms.py](../jobs/forms.py) | `test_a_value_that_is_not_listed_is_ignored_without_an_error`, `test_filter_form_is_a_get_form_with_a_show_button` in [test_job_list_views.py](../jobs/tests/test_job_list_views.py); `test_a_value_that_is_not_listed_makes_only_that_field_invalid` in [test_job_filter.py](../jobs/tests/test_job_filter.py) |
| The exact address only for the owner | The public job page shows everyone else the district and "The exact address is shown after the employer accepts you." The view decides (`show_address`), not the template, so #25 adds the accepted worker in one place. The employer card has no phone or email | `JobDetailView.get_context_data` in [jobs/views.py](../jobs/views.py), [job_detail.html](../templates/jobs/job_detail.html) | `test_owner_sees_the_address`, `test_others_do_not_see_the_address`, `test_page_has_no_contact_details_of_the_employer` in [test_job_detail_views.py](../jobs/tests/test_job_detail_views.py) |
| "Apply" checks the role on the server | Not only a hidden button: guests go to login, employers get 403, GET gives 405 (a stub until #22) | `JobApplyView` (`WorkerRequiredMixin`) in [jobs/views.py](../jobs/views.py) | `test_apply_stub_sends_guest_to_login`, `test_apply_stub_refuses_employers`, `test_apply_stub_refuses_get` in [test_job_detail_views.py](../jobs/tests/test_job_detail_views.py) |

## Job photos (#64)

| Protection | How | Code | Tests |
|---|---|---|---|
| No location or camera data in photos | EXIF (incl. GPS) is removed from every photo and thumbnail before storing; photos on their side are turned upright first | `prepare_photo`, `make_thumbnail` in [jobs/photos.py](../jobs/photos.py) | `test_exif_is_removed`, `test_photo_on_its_side_is_turned_upright` in [test_photos.py](../jobs/tests/test_photos.py), `test_thumbnail_has_no_exif` in [test_thumbnails.py](../jobs/tests/test_thumbnails.py) |
| Only real pictures, no "decompression bombs" | The format is read from the content (JPEG / PNG / WebP only), max 5 MB checked before opening, Pillow's pixel limit; every photo is re-encoded, so no byte of the upload is stored as it came | [jobs/photos.py](../jobs/photos.py) | `test_text_file_named_jpg_is_refused`, `test_file_over_5_mb_is_refused`, `test_picture_over_pixel_limit_is_refused`, `test_cut_off_file_is_refused` in [test_photos.py](../jobs/tests/test_photos.py) |
| File names tell nothing | Random names: an original name can hold a person's name | `job_photo_path` in [jobs/models.py](../jobs/models.py) | `test_stored_name_is_random` in [test_job_photo_model.py](../jobs/tests/test_job_photo_model.py) |
| Files go with their row | A `post_delete` signal deletes both files after the commit, also when a job or an account is deleted | [jobs/models.py](../jobs/models.py) | `test_deleting_job_deletes_files`, `test_deleting_employer_deletes_files`, `test_file_stays_until_commit` in [test_job_photo_model.py](../jobs/tests/test_job_photo_model.py), `test_deleting_a_photo_deletes_both_files` in [test_thumbnails.py](../jobs/tests/test_thumbnails.py) |
| Only the owner of an open job adds or deletes photos | Others get 404, guests go to login, workers get 403; POST only, CSRF checked. The limit of 5 also holds for a hand-made admin POST (`validate_max`) | [jobs/views.py](../jobs/views.py), [jobs/admin.py](../jobs/admin.py) | `test_other_employer_gets_404`, `test_cancelled_job_gets_404`, `test_guest_is_sent_to_login`, `test_worker_gets_403`, `test_get_is_not_allowed`, `test_photo_forms_need_the_csrf_token` in [test_job_photo_views.py](../jobs/tests/test_job_photo_views.py); `test_admin_refuses_a_sixth_photo` in [test_job_photo_admin.py](../jobs/tests/test_job_photo_admin.py) |

## Django defaults we rely on

Not tested separately, because they are Django's own behaviour and not our settings:

- **XSS:** templates escape every value, so text a user typed is shown as text, not run as code.
- **SQL injection:** we use the ORM only, which sends values separately from the SQL query.
- **Clickjacking:** `XFrameOptionsMiddleware` ([base.py](../config/settings/base.py)) stops other
  sites from showing our pages in a hidden frame. It is part of the deploy check below.

## HTTPS in production (#5)

Locally the traffic never leaves the computer and `runserver` has no HTTPS, so these settings
are on only in [config/settings/production.py](../config/settings/production.py):

| Setting | Why |
|---|---|
| `SECURE_PROXY_SSL_HEADER` | Render's proxy handles HTTPS and passes the request on as http, with a header saying it was https. Without trusting that header, the redirect below would loop forever |
| `SECURE_SSL_REDIRECT` | Every `http://` request is sent to `https://` |
| `SECURE_HSTS_SECONDS = 3600` | The browser remembers to use only HTTPS for one hour. Short on purpose until HTTPS is confirmed working; to be raised later |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Cookies only travel over HTTPS, never as plain text on public Wi-Fi |
| `DEBUG = False` | Error pages do not show code, paths or settings |

Tests in [tests/test_deploy.py](../tests/test_deploy.py):
`test_production_uses_https_only` checks the values above, and
`test_production_passes_the_django_deploy_check` runs Django's own checklist
(`manage.py check --deploy`). Both are needed: the checklist does not look at
`SECURE_PROXY_SSL_HEADER`, but it covers about 15 other points. Two of its warnings are
accepted on purpose, see [Known limitations](#known-limitations).

## Hosting and secrets

- **No secrets in the repo.** `SECRET_KEY` and `DATABASE_URL` come from environment variables
  and have no default, so the app does not start without them
  ([base.py](../config/settings/base.py)). Locally they live in `.env`, which is in
  [.gitignore](../.gitignore); [.env.example](../.env.example) has only placeholders. On Render
  the secret key is generated once by Render ([render.yaml](../render.yaml)); CI uses a dummy key
  ([ci.yml](../.github/workflows/ci.yml)).
- **Data stays in the EU.** The web service runs on Render, the database and the job photos on
  Supabase, all in Frankfurt ([render.yaml](../render.yaml)).
- **Photo storage keys only on Render.** The S3 key pair of Supabase Storage bypasses Supabase's
  row-level security, so it lives only in Render's environment (`sync: false` in
  [render.yaml](../render.yaml)), never in the repo; production does not start without the six
  `MEDIA_*` variables ([production.py](../config/settings/production.py); tests
  `test_production_does_not_start_without_a_storage_variable`,
  `test_render_asks_for_the_storage_variables` in
  [tests/test_media_production.py](../tests/test_media_production.py)).
- **Only allowed host names.** Production answers only on the name Render gives the service
  (`ALLOWED_HOSTS` in [production.py](../config/settings/production.py); tests
  `test_production_allows_the_host_name_render_gives_the_service` and
  `test_production_without_render_adds_no_empty_host`).
- **No CDN.** CSS and HTMX are served from our own server, so no third party sees our visitors or
  can change the code they run (`test_layout_loads_css_and_htmx`,
  `test_htmx_file_is_served_in_the_chosen_version` in
  [tests/test_base_layout.py](../tests/test_base_layout.py)). Job photos are the exception: the
  browser loads them from Supabase's public address (`MEDIA_PUBLIC_URL`), so Supabase — already
  our database host, in the EU — sees the IP address of visitors of pages with photos.

## Tests

- **Fast password hashing only in tests.** The root [conftest.py](../conftest.py) switches tests
  to one MD5 round (the run went from ~2 min to ~30 s); production keeps PBKDF2, checked by
  `test_production_hashes_passwords_with_pbkdf2` in [tests/test_deploy.py](../tests/test_deploy.py).
- **`DJANGO_ALLOW_ASYNC_UNSAFE`** is set only in [tests/e2e/conftest.py](../tests/e2e/conftest.py)
  (Playwright's event loop), never in the site settings.
- **Playwright traces hold only test data.** `test-results/` holds everything the E2E tests
  typed, passwords included, so it is in [.gitignore](../.gitignore). Since #21 a failed CI run
  uploads it as the `playwright-traces` artifact, which anyone signed in to GitHub can download
  from this public repo: the E2E tests use made-up accounts only, never real data.
- **Photos never go to a real bucket in tests.** The root [conftest.py](../conftest.py) switches
  file storage to memory (`in_memory_file_storage`); the production storage settings are tested
  with made-up values and no network ([tests/test_media_production.py](../tests/test_media_production.py)).

## Repository and CI

- **`main` is protected** (ruleset "Protect main"): no direct pushes, no force pushes, no
  deleting; every change goes through a pull request, and the CI check `test` (ruff + pytest)
  must be green before merging.
- **Deploy only after green CI:** Render deploys `main` only when the checks pass
  (`autoDeployTrigger: checksPass` in [render.yaml](../render.yaml)).
- **CI can only read:** the workflow's token may read the code and issues, nothing else
  (`permissions` in [ci.yml](../.github/workflows/ci.yml)).
- **Private vulnerability reporting** is on, see
  [Reporting a vulnerability](#reporting-a-vulnerability).

## Known limitations

- **Signup shows that an email is taken** ("User with this Email already exists.",
  `test_register_with_taken_email_shows_an_error`). Someone could use it to check whether an
  address is registered. Planned fix: email verification at signup (#81), so signup always
  answers "check your email".
- **No login rate limiting.** Nothing stops many password guesses in a row; only the password
  validators make guessing harder.
  Planned: #91.
- **Emails go to the console.** Until SMTP is set up (#27), password reset emails, including the
  reset link, are printed to the terminal and the Render logs instead of being sent.
- **HSTS only for one hour, no subdomains, no preload list.** The site lives on
  `bauhelfer.onrender.com`, a subdomain of Render's domain. The preload list needs our own
  domain, which is not on the free plan. These are the two accepted deploy-check warnings
  (`security.W005`, `security.W021`).
- **The work permit is the worker's own statement**, not a document check: anyone can tick the
  box. Employers remain responsible for checking papers before hiring (SchwarzArbG, AufenthG
  § 4a); BauHelfer does not claim otherwise.
- **Phone numbers saved before #109 are not re-checked.** A validator runs only when a form is
  saved, so an old wrong number stays until the user edits the profile. Today the database has
  only test accounts. With real users: count the invalid numbers, fix only the unambiguous ones
  in a data migration, ask users to correct the rest, never delete silently; a database
  constraint last.
- **A filled job cannot be cancelled yet.** Cancelling works only for open jobs; what happens
  to accepted workers is decided in #24.
- **The address is hidden in text only.** A job photo can still show a house number, a facade,
  a face or a number plate (`docs/specs/job-photos.md` D32). Decided in #95 to keep it simple
  for now: no upload hint, no private photos.
- **Photos are public.** The bucket is public: anyone with a photo's address can open it. The
  names are random (128 bits) and the job list is public anyway (`docs/specs/job-photos.md`
  D30).
- **Cancelled and past jobs keep a public page** with district, date and description, and their
  photos stay until the job or the account is deleted. Revisit with data minimisation in M7.
- **Only the phone format is checked:** "+49 (0)151 …" passes, though some phones cannot dial
  the "(0)". Decided not to add a rule for it.
