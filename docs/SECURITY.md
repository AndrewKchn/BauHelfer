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

All in [accounts/models.py](../accounts/models.py):

- **Account:** email, password (as a hash), name, phone (optional), role, preferred language,
  and when a worker confirmed being allowed to work in Germany (`work_permit_confirmed_at`;
  empty = not confirmed, #13).
- **Worker profile (#11):** team size, skills, spoken languages, legal status. No district or
  address: no feature needs it.
- **Employer profile (#12):** company name (optional), trades. No address, VAT or registration
  number.

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
- **Data stays in the EU.** The web service runs on Render and the database on Supabase, both in
  Frankfurt ([render.yaml](../render.yaml)).
- **Only allowed host names.** Production answers only on the name Render gives the service
  (`ALLOWED_HOSTS` in [production.py](../config/settings/production.py); tests
  `test_production_allows_the_host_name_render_gives_the_service` and
  `test_production_without_render_adds_no_empty_host`).
- **No CDN.** CSS and HTMX are served from our own server, so no third party sees our visitors or
  can change the code they run (`test_layout_loads_css_and_htmx`,
  `test_htmx_file_is_served_in_the_chosen_version` in
  [tests/test_base_layout.py](../tests/test_base_layout.py)).

## Tests

- **Fast password hashing only in tests.** The root [conftest.py](../conftest.py) switches tests
  to one MD5 round (the run went from ~2 min to ~30 s); production keeps PBKDF2, checked by
  `test_production_hashes_passwords_with_pbkdf2` in [tests/test_deploy.py](../tests/test_deploy.py).
- **`DJANGO_ALLOW_ASYNC_UNSAFE`** is set only in [tests/e2e/conftest.py](../tests/e2e/conftest.py)
  (Playwright's event loop), never in the site settings.
- **Playwright traces stay local.** `test-results/` holds everything the E2E tests typed,
  passwords included, so it is in [.gitignore](../.gitignore).

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
- **Only the phone format is checked:** "+49 (0)151 …" passes, though some phones cannot dial
  the "(0)". Decided not to add a rule for it.
