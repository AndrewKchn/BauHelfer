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
  empty = not confirmed, #13). Whether the user wants notification emails
  (`email_notifications`, #27), when the address was confirmed (`email_verified_at`; empty =
  no email goes there, #27, #81) and when the last confirmation link went out
  (`verification_sent_at`, #81).
- **Worker profile (#11):** team size, skills, spoken languages, legal status. No district or
  address: no feature needs it.
- **Employer profile (#12):** company name (optional), trades. No address, VAT or registration
  number.
- **Job (#15):** the job's address — for a private employer this is their home address. It is
  stored as entered; only the job's own employer sees it (#19), everyone else the district.
- **Job photos (#64):** pictures the employer uploads, without EXIF (no GPS, no camera data),
  under random file names.
- **Application (#22):** the job, the worker, a free-text message (≤ 500 characters; it may
  hold a phone number or a name), how many workers were offered and accepted, the status.
  Deleted with the job or the account (`CASCADE`); the data export (#44) has to include it.

The phone is checked for a callable format: `+` and a country code or `0` and a German area
code, 10–15 digits (`validate_phone` in [accounts/validators.py](../accounts/validators.py),
used on `User.phone`, so the profile forms and the admin both check it; tests in
[test_phone.py](../accounts/tests/test_phone.py) and
[test_phone_views.py](../accounts/tests/test_phone_views.py), incl.
`test_admin_rejects_a_wrong_phone`). It is a data-quality check, not a security one.

Everything is stored in the EU, see [Hosting](#hosting-and-secrets). Emails go out through
Brevo (France, EU), which receives each recipient's address and name, the job type and the
date, see [Email](#email-and-address-confirmation-27-81).

## Accounts (#9)

| Protection | How | Code | Tests |
|---|---|---|---|
| Passwords are never stored in plain text | Django saves a salted PBKDF2 hash (1,000,000 rounds) | [accounts/forms.py](../accounts/forms.py) `SignupForm` (Django's `UserCreationForm`) | `test_valid_signup_creates_user_with_hashed_password` in [test_forms.py](../accounts/tests/test_forms.py), `test_production_hashes_passwords_with_pbkdf2` in [tests/test_deploy.py](../tests/test_deploy.py) |
| No weak passwords | Django's four password validators: not like the email, at least 8 characters, not a common password, not only digits | `AUTH_PASSWORD_VALIDATORS` in [config/settings/base.py](../config/settings/base.py) | `test_signup_with_weak_password_is_rejected` in [test_forms.py](../accounts/tests/test_forms.py) |
| Forms cannot be sent from another site (CSRF) | Every form has a secret `{% csrf_token %}`; without it the answer is 403 | `CsrfViewMiddleware` in [base.py](../config/settings/base.py) | `test_register_needs_the_csrf_token_from_the_page` in [test_views.py](../accounts/tests/test_views.py) |
| Another site cannot log people out | Logout works only by POST (a form), not by a link or an image. The header's "Log out" is a POST form with `{% csrf_token %}` | Django's `LogoutView` in [accounts/urls.py](../accounts/urls.py); menu in [templates/base.html](../templates/base.html) | `test_logout_by_link_is_not_allowed` in [test_views.py](../accounts/tests/test_views.py), `test_menu_logout_button_is_inside_the_post_form` in [test_onboarding_views.py](../accounts/tests/test_onboarding_views.py) |
| Login does not tell who is registered | The same "Wrong email or password." for an unknown email and for a wrong password | `LoginForm` in [accounts/forms.py](../accounts/forms.py) | `test_login_with_unknown_email_shows_the_same_error_as_a_wrong_password` in [test_views.py](../accounts/tests/test_views.py) |
| Password reset does not tell who is registered | The same "Check your email" page for any address; an email goes only to real accounts with a confirmed address (#27) | Django's `PasswordResetView` with `ConfirmedPasswordResetForm` in [accounts/forms.py](../accounts/forms.py) | `test_password_reset_for_unknown_email_looks_the_same_but_sends_nothing` in [test_views.py](../accounts/tests/test_views.py), `test_password_reset_goes_only_to_a_confirmed_address` in [test_email_verified.py](../accounts/tests/test_email_verified.py), `test_reset_page_looks_the_same_whether_an_email_was_sent` in [test_email_verified_views.py](../accounts/tests/test_email_verified_views.py) |
| A reset link works only once | The link's token depends on the current password hash, so it dies when the password changes. It also expires after 3 days (Django's default) | Django's `PasswordResetConfirmView` in [accounts/urls.py](../accounts/urls.py) | `test_password_reset_link_works_only_once` in [test_views.py](../accounts/tests/test_views.py) |
| A session id known before login is useless (session fixation) | Django's `login()` gives the user a new session id | `RegisterView` in [accounts/views.py](../accounts/views.py), Django's `LoginView` | `test_login_gives_a_new_session_id` in [test_views.py](../accounts/tests/test_views.py) |
| Login never sends the user to another site (open redirect) | `?next=` is followed only for addresses on our own site. Since #20 an employer lands on "My jobs" by default; only the default page changed, `?next=` is still checked by Django | Django's `LoginView`; `LoginView.get_default_redirect_url` in [accounts/views.py](../accounts/views.py) | `test_login_ignores_a_next_link_to_another_site`, `test_login_goes_back_to_the_page_that_asked_for_it` in [test_views.py](../accounts/tests/test_views.py); `test_next_address_wins_for_an_employer` in [test_login_redirect_views.py](../accounts/tests/test_login_redirect_views.py) |
| Only staff can open the admin | Django admin checks `is_staff` | [accounts/admin.py](../accounts/admin.py) | `test_non_staff_user_cannot_open_admin` in [test_admin.py](../accounts/tests/test_admin.py) |

## Roles and profiles (#10–#13)

| Protection | How | Code | Tests |
|---|---|---|---|
| A user without a role can only choose one | `OnboardingMiddleware` sends a logged-in user without a role to the role choice from every page (deny by default; allowed: role choice, logout, `/admin/`; staff skipped) | [accounts/middleware.py](../accounts/middleware.py) | `test_user_without_role_is_sent_back_to_the_role_choice` in [test_onboarding_views.py](../accounts/tests/test_onboarding_views.py), [test_onboarding.py](../accounts/tests/test_onboarding.py) |
| The role is chosen once | `RoleSelectView` redirects users who already have a role, so a second POST cannot change it; `RoleForm` accepts only `role` (fields like `is_staff` are ignored) and only `employer` / `worker` | `RoleSelectView` in [accounts/views.py](../accounts/views.py), `RoleForm` in [accounts/forms.py](../accounts/forms.py) | `test_role_cannot_be_changed_by_posting_the_form_again` in [test_onboarding_views.py](../accounts/tests/test_onboarding_views.py) |
| Profile pages only for their role | Login, else 403: workers cannot open employer pages and the other way round; staff without a role get 403 | `RoleRequiredMixin` in [accounts/views.py](../accounts/views.py) | `test_employer_gets_403`, `test_admin_without_role_gets_403`, `test_guest_must_log_in` in [test_worker_profile_views.py](../accounts/tests/test_worker_profile_views.py); `test_worker_gets_403` in [test_employer_profile_views.py](../accounts/tests/test_employer_profile_views.py) |
| Users edit only their own profile | No id in the URL, the form has no `user` field, the view sets `profile.user = request.user`; user and profile are saved in one `transaction.atomic()`. One profile per user (database constraint) | `ProfileEditView` in [accounts/views.py](../accounts/views.py) | `test_worker_cannot_save_a_profile_for_someone_else`, `test_employer_cannot_create_a_worker_profile` in [test_worker_profile_views.py](../accounts/tests/test_worker_profile_views.py); `test_employer_cannot_save_a_profile_for_someone_else`, `test_worker_cannot_create_an_employer_profile` in [test_employer_profile_views.py](../accounts/tests/test_employer_profile_views.py); `test_user_cannot_have_two_profiles` in [test_worker_profile.py](../accounts/tests/test_worker_profile.py), [test_employer_profile.py](../accounts/tests/test_employer_profile.py) |
| Role and profile forms cannot be sent from another site | `{% csrf_token %}` in every form | [templates/accounts/](../templates/accounts/) | `test_role_choice_needs_the_csrf_token_from_the_page` in [test_onboarding_views.py](../accounts/tests/test_onboarding_views.py); `test_profile_form_needs_the_csrf_token_from_the_page` in both profile view test files |
| Profile cards show no contacts | The cards the other side sees (#19, #23) have no phone or email; contacts only after acceptance (#25) | [_worker_profile_card.html](../templates/accounts/_worker_profile_card.html), [_employer_profile_card.html](../templates/accounts/_employer_profile_card.html) | `test_profile_card_has_no_contact_details` in both profile view test files; end to end in a real browser: `test_worker_applies_and_the_employer_accepts_on_two_phones` in [tests/e2e/test_application_flows.py](../tests/e2e/test_application_flows.py) (#28) |
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
| The exact address only for the owner and an accepted worker | The public job page shows everyone else the district and "The exact address is shown after the employer accepts you." The view decides (`show_address`), not the template: the owner, and since #25 an accepted worker (see [Applications and contacts](#applications-and-contacts-2026)). The employer card has no phone or email | `JobDetailView.get_context_data` in [jobs/views.py](../jobs/views.py), [job_detail.html](../templates/jobs/job_detail.html) | `test_owner_sees_the_address`, `test_others_do_not_see_the_address`, `test_page_has_no_contact_details_of_the_employer` in [test_job_detail_views.py](../jobs/tests/test_job_detail_views.py); end to end: `test_worker_applies_and_the_employer_accepts_on_two_phones` in [tests/e2e/test_application_flows.py](../tests/e2e/test_application_flows.py) (#28) |
| "My jobs" shows the address and the applications only to their employer (#20) | The page lists only `request.user.jobs` and counts only their applications; the job list and the job page keep hiding the address | `MyJobsView.get_queryset` in [jobs/views.py](../jobs/views.py) | `test_my_jobs_lists_only_own_jobs` in [test_views.py](../jobs/tests/test_views.py); `test_each_job_counts_only_its_own_applications`, `test_card_shows_the_address_and_the_district` in [test_my_jobs_views.py](../jobs/tests/test_my_jobs_views.py) |

## Job photos (#64)

| Protection | How | Code | Tests |
|---|---|---|---|
| No location or camera data in photos | EXIF (incl. GPS) is removed from every photo and thumbnail before storing; photos on their side are turned upright first | `prepare_photo`, `make_thumbnail` in [jobs/photos.py](../jobs/photos.py) | `test_exif_is_removed`, `test_photo_on_its_side_is_turned_upright` in [test_photos.py](../jobs/tests/test_photos.py), `test_thumbnail_has_no_exif` in [test_thumbnails.py](../jobs/tests/test_thumbnails.py) |
| Only real pictures, no "decompression bombs" | The format is read from the content (JPEG / PNG / WebP only), max 5 MB checked before opening, Pillow's pixel limit; every photo is re-encoded, so no byte of the upload is stored as it came | [jobs/photos.py](../jobs/photos.py) | `test_text_file_named_jpg_is_refused`, `test_file_over_5_mb_is_refused`, `test_picture_over_pixel_limit_is_refused`, `test_cut_off_file_is_refused` in [test_photos.py](../jobs/tests/test_photos.py) |
| File names tell nothing | Random names: an original name can hold a person's name | `job_photo_path` in [jobs/models.py](../jobs/models.py) | `test_stored_name_is_random` in [test_job_photo_model.py](../jobs/tests/test_job_photo_model.py) |
| Files go with their row | A `post_delete` signal deletes both files after the commit, also when a job or an account is deleted | [jobs/models.py](../jobs/models.py) | `test_deleting_job_deletes_files`, `test_deleting_employer_deletes_files`, `test_file_stays_until_commit` in [test_job_photo_model.py](../jobs/tests/test_job_photo_model.py), `test_deleting_a_photo_deletes_both_files` in [test_thumbnails.py](../jobs/tests/test_thumbnails.py) |
| Only the owner of an open job adds or deletes photos | Others get 404, guests go to login, workers get 403; POST only, CSRF checked. The limit of 5 also holds for a hand-made admin POST (`validate_max`) | [jobs/views.py](../jobs/views.py), [jobs/admin.py](../jobs/admin.py) | `test_other_employer_gets_404`, `test_cancelled_job_gets_404`, `test_guest_is_sent_to_login`, `test_worker_gets_403`, `test_get_is_not_allowed`, `test_photo_forms_need_the_csrf_token` in [test_job_photo_views.py](../jobs/tests/test_job_photo_views.py); `test_admin_refuses_a_sixth_photo` in [test_job_photo_admin.py](../jobs/tests/test_job_photo_admin.py) |

## Applications and contacts (#20–#26)

| Protection | How | Code | Tests |
|---|---|---|---|
| Only a worker who may apply, once per job, to a job that takes applications | Guests go to login, employers get 403. The worker needs a profile and the work-permit confirmation (`User.can_apply()`); the job must be open and not started (`Job.accepts_applications`); one application per job (a check in the view + `UniqueConstraint`). The view checks it all again on POST, not only by hiding the form | `JobApplyView` (`WorkerRequiredMixin`) in [jobs/views.py](../jobs/views.py), `Application` in [jobs/models.py](../jobs/models.py) | `test_worker_who_cannot_apply_is_refused`, `test_job_that_takes_no_applications_refuses_the_post`, `test_second_application_to_the_same_job_is_refused` in [test_application_views.py](../jobs/tests/test_application_views.py); `test_database_refuses_a_second_application_to_the_same_job`, `test_database_refuses_a_message_over_500_characters` in [test_application.py](../jobs/tests/test_application.py) |
| The applications to a job only for its employer (#23) | The job page shows the list instead of the employer card to the job's own employer only. A worker who applied sees only their own application, never the other applicants; guests and other employers see the employer card | `JobDetailView.get_context_data` in [jobs/views.py](../jobs/views.py) | `test_worker_who_applied_does_not_see_the_other_applicants`, `test_other_employer_does_not_see_the_list`, `test_guest_sees_the_employer_card_and_no_list`, `test_page_shows_no_contact_details` in [test_applications_list_views.py](../jobs/tests/test_applications_list_views.py) |
| A worker's page only for an employer the worker applied to (#23) | `/accounts/workers/<pk>/` is found only among the workers who applied to one of the employer's jobs (any job status); everyone else gets 404, workers 403, guests go to login. No phone or email on it | `WorkerDetailView.get_queryset` in [accounts/views.py](../accounts/views.py) | `test_employer_the_worker_applied_to_sees_the_profile`, `test_other_employer_gets_404`, `test_worker_gets_403_also_for_their_own_page`, `test_worker_page_shows_no_contact_details` in [test_worker_detail_views.py](../accounts/tests/test_worker_detail_views.py) |
| Only the job's own employer accepts, rejects or cancels a worker (#24) | Everyone else gets 404, workers 403, guests go to login; POST only, CSRF checked. The job row is locked (`select_for_update`), so two taps cannot accept more workers than needed | `OwnApplicationMixin` in [jobs/views.py](../jobs/views.py), `Application._lock` in [jobs/models.py](../jobs/models.py) | `test_other_employer_gets_404`, `test_worker_gets_403`, `test_get_is_not_allowed` in [test_accept_reject_views.py](../jobs/tests/test_accept_reject_views.py) and [test_cancel_views.py](../jobs/tests/test_cancel_views.py); `test_accept_locks_the_job_row` in [test_accept_reject.py](../jobs/tests/test_accept_reject.py) |
| Only the worker withdraws their own application (#26) | Employers get 403, another worker's application 404, GET 405; the job row is locked as for accepting | `ApplicationWithdrawView` in [jobs/views.py](../jobs/views.py), `Application.withdraw` in [jobs/models.py](../jobs/models.py) | `test_other_workers_application_gets_404`, `test_employer_gets_403`, `test_get_is_not_allowed` in [test_withdraw_views.py](../jobs/tests/test_withdraw_views.py); `test_withdraw_reads_the_state_again_and_locks_the_job` in [test_withdraw.py](../jobs/tests/test_withdraw.py) |
| Contacts only after acceptance, and only until the job is over (#25, #26) | The job's exact address and each side's phone (if given) are shown only for an accepted application, until the day the job ends is over (Munich time). One rule, `Application.shows_contacts`, for the job page and "My applications". The email is never shown. Cancelling a job cancels its accepted applications, so their contacts disappear | `Application.shows_contacts`, `Job.cancel` in [jobs/models.py](../jobs/models.py); [_my_application_card.html](../templates/jobs/_my_application_card.html) | [test_contacts.py](../jobs/tests/test_contacts.py), [test_contacts_views.py](../jobs/tests/test_contacts_views.py); `test_accepted_card_shows_the_contact`, `test_no_contact_without_shows_contacts` in [test_my_applications_views.py](../jobs/tests/test_my_applications_views.py); end to end: `test_worker_applies_and_the_employer_accepts_on_two_phones` in [tests/e2e/test_application_flows.py](../tests/e2e/test_application_flows.py) (#28) |

## Email and address confirmation (#27, #81)

| Protection | How | Code | Tests |
|---|---|---|---|
| Email only to a confirmed address | No email at all goes to an address whose owner has not confirmed it (`email_verified_at` empty): a typo or someone else's address gets nothing | `send` in [jobs/notifications.py](../jobs/notifications.py), `ConfirmedPasswordResetForm` in [accounts/forms.py](../accounts/forms.py) | `test_no_email_to_an_unconfirmed_employer`, `test_no_email_to_an_unconfirmed_worker` in [test_notifications.py](../jobs/tests/test_notifications.py); `test_password_reset_goes_only_to_a_confirmed_address` in [test_email_verified.py](../accounts/tests/test_email_verified.py) |
| No contacts in emails | No phone, address or application message in any email; the person opens the site to see them | [jobs/notifications.py](../jobs/notifications.py), [templates/emails/](../templates/emails/) | `test_decision_emails_hold_no_contact_data`, `test_new_application_email_holds_no_contact_data` in [test_notifications.py](../jobs/tests/test_notifications.py) |
| A failed email breaks nothing and leaks nothing | The error is logged with ids and the exception class only, never the provider's error text (it can hold the address) | `send` in [jobs/notifications.py](../jobs/notifications.py) | `test_failed_email_is_logged_and_not_raised` in [test_notifications.py](../jobs/tests/test_notifications.py) |
| A new account works only after its owner confirms the address (#81) | The account is inactive until the owner opens the emailed link and presses "Confirm email". The token is Django's reset token with its own salt and `email_verified_at` in the hash: nothing stored, works once, expires after 3 days (`PASSWORD_RESET_TIMEOUT`), and a password reset link does not confirm an address | `EmailVerificationTokenGenerator` in [accounts/tokens.py](../accounts/tokens.py), `VerifyEmailView` in [accounts/views.py](../accounts/views.py) | `test_token_works_only_until_the_address_is_confirmed`, `test_token_expires_after_the_password_reset_timeout`, `test_password_reset_token_is_not_a_confirmation_token` in [test_email_verification.py](../accounts/tests/test_email_verification.py); `test_link_works_only_once` in [test_email_verification_views.py](../accounts/tests/test_email_verification_views.py) |
| Mail scanners cannot use up the link | Opening the link changes nothing; only the POST of the button confirms | `VerifyEmailView` in [accounts/views.py](../accounts/views.py) | `test_opening_the_link_only_shows_a_button` in [test_email_verification_views.py](../accounts/tests/test_email_verification_views.py) |
| Login and the resend page do not tell who is registered | The hint "Please confirm your email first" needs the right password; an account an admin turned off keeps the usual error. The resend page answers the same for every address and sends at most one link per account every 10 minutes | `LoginForm.get_invalid_login_error` in [accounts/forms.py](../accounts/forms.py), `User.can_get_verification_email` in [accounts/models.py](../accounts/models.py), `ResendVerificationView` in [accounts/views.py](../accounts/views.py) | `test_unconfirmed_account_with_a_wrong_password_gets_the_usual_error`, `test_blocked_account_with_a_confirmed_address_gets_the_usual_error`, `test_new_link_at_most_every_10_minutes` in [test_email_verification.py](../accounts/tests/test_email_verification.py); `test_resend_answers_the_same_and_sends_nothing` in [test_email_verification_views.py](../accounts/tests/test_email_verification_views.py) |
| Only superusers switch the confirmation off | The demo switch "Email verification required" (`SiteSettings`) is visible and changeable only by superusers, whatever permissions a staff user has | `SiteSettingsAdmin` in [accounts/admin.py](../accounts/admin.py) | `test_staff_without_superuser_cannot_see_or_change_the_switch` in [test_site_settings_views.py](../accounts/tests/test_site_settings_views.py) |

## Logs (#124, #137)

Everything goes to stdout, which Render shows in its Logs tab (`LOGGING` in
[config/settings/base.py](../config/settings/base.py), one handler on the root logger).

| Protection | How | Code | Tests |
|---|---|---|---|
| Our events carry ids only | Registration, failed login (also on `/admin/`, through the `user_login_failed` signal), job created / cancelled, application created, accepted, rejected, cancelled, withdrawn, emails sent or failed: `user_id=…`, `job_id=…`, `application_id=…`. The email typed at a failed login is never logged (`unknown account`), nor an application's message | `log_failed_login` in [accounts/signals.py](../accounts/signals.py), [accounts/views.py](../accounts/views.py), [jobs/views.py](../jobs/views.py) | `test_unknown_email_is_logged_without_the_email`, `test_failed_admin_login_is_logged_too` in [accounts/tests/test_logging.py](../accounts/tests/test_logging.py); `test_applying_is_logged_with_ids_and_without_the_message` in [jobs/tests/test_logging.py](../jobs/tests/test_logging.py); `test_accepting_and_filling_are_logged_with_ids_only` in [test_accept_reject_views.py](../jobs/tests/test_accept_reject_views.py) |
| Server errors reach the logs | Django prints a 500 with its traceback only with DEBUG on; our `LOGGING` sends it to stdout with DEBUG off too, once | `LOGGING` in [base.py](../config/settings/base.py) | `test_server_error_is_printed_to_stdout_with_debug_off`, `test_server_error_is_printed_once_with_debug_on`, `test_local_settings_do_not_change_the_production_levels` in [tests/test_logging.py](../tests/test_logging.py) |
| Request lines without personal data | gunicorn's access log is off (its default line starts with the visitor's IP). Our own line: method, path without the query string, status and time — no IP, no User-Agent, no Referer. The password reset link is logged as its URL pattern `/accounts/reset/<uidb64>/<token>/`, also when another middleware answers first. Render's health check and static files are not logged | `GUNICORN_CMD_ARGS` in [render.yaml](../render.yaml), `RequestLogMiddleware` in [config/middleware.py](../config/middleware.py) (production only); `docs/specs/request-logging.md` | `test_render_starts_gunicorn_without_an_access_log` in [tests/test_request_logging_setup.py](../tests/test_request_logging_setup.py); `test_password_reset_link_is_logged_without_uid_and_token`, `test_reset_link_is_hidden_when_a_middleware_answers_first`, `test_user_agent_and_referer_are_not_logged`, `test_query_string_is_not_logged`, `test_render_health_check_is_not_logged` in [tests/test_request_logging.py](../tests/test_request_logging.py) |

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
  Supabase, all in Frankfurt ([render.yaml](../render.yaml)); emails go through Brevo in France
  (#27).
- **Email key only on Render.** The Brevo key `bauhelfer-render` has only the "Transactional
  email" permission and lives only in Render's environment (`sync: false` in
  [render.yaml](../render.yaml)); production does not start without `BREVO_API_KEY` or
  `DEFAULT_FROM_EMAIL` (tests `test_production_does_not_start_without_an_email_variable`,
  `test_render_asks_for_the_email_variables` in
  [tests/test_email_production.py](../tests/test_email_production.py)). Locally and in tests the
  console backend is used, so no email leaves the computer.
- **Django Debug Toolbar never reaches the live site (#135).** It shows SQL with its values,
  settings and the request. It is a dev dependency (`uv sync --no-dev` on Render does not
  install it), added only in [config/settings/local.py](../config/settings/local.py), shown only
  with DEBUG on and to `INTERNAL_IPS = ["127.0.0.1"]`; [config/urls.py](../config/urls.py) adds
  `/__debug__/` only when the app is installed (tests `test_production_does_not_add_the_toolbar`,
  `test_the_test_run_does_not_add_the_toolbar` in
  [tests/test_debug_toolbar_settings.py](../tests/test_debug_toolbar_settings.py);
  `test_toolbar_hides_with_debug_off`, `test_urls_load_without_the_toolbar_package` in
  [tests/test_debug_toolbar_page.py](../tests/test_debug_toolbar_page.py)).
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
  address is registered. Accepted in #81 (`docs/specs/email-verification.md` D3): hiding it
  would mean emailing the owner on every attempt, and anyone could use that to flood a real
  person. Revisit with #91.
- **No login rate limiting.** Nothing stops many password guesses in a row; only the password
  validators make guessing harder. Until #91 the resend page can also send one email every
  10 minutes to an unconfirmed address. Planned: #91.
- **Address confirmation (#81):** accounts that are never confirmed stay in the database,
  inactive. One email goes to every address typed at signup, made-up ones included; Brevo
  blocks an address after a hard bounce. While the demo switch is off, new accounts are active
  but unconfirmed and get no email, password reset included, until they confirm with the
  resend page.
- **Email (#27):** (a) Brevo adds a List-Unsubscribe header; clicking "Unsubscribe" in Gmail puts
  the address on Brevo's blocklist, so no email reaches it any more, password reset included,
  while the site still shows the checkbox on. (b) Reply-To is the project mailbox, so users'
  replies land there. (c) 300 emails a day; above that, sending fails and is only logged.
  (d) A decision made in Django admin sends no email.
- **Logs (#124, #137):** Render keeps them 7 days (Hobby workspace) and silently drops lines
  above 6,000 per minute per instance. Only the events listed above are checked for personal
  data: a new `logger.info(user.email)` elsewhere would fail no test. Django's own
  `django.request` lines (404, 500) still hold the full path: if the reset page itself crashes,
  the 500 line holds the uid and token (visible only in the Render dashboard; the token dies
  with a password change or after 3 days; revisit when such a line shows up). A 404 path is
  logged as typed. Anyone can send the User-Agent `Render/1.0` and get no request line (our
  events and Django's 4xx/5xx lines still appear).
- **Django Debug Toolbar with `runserver 0.0.0.0`.** `local.py` with DEBUG on is meant for one's
  own machine; started that way, the toolbar is still shown only to 127.0.0.1.
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
- **A filled job cannot be cancelled.** Cancelling works only for open jobs (`Job.cancel`); an
  open job with accepted workers can be cancelled, and their applications become "cancelled",
  but no email tells them. Revisit in #37, which changes what happens to filled jobs.
- **Two applications at the same instant** by the same worker: the second gets a 500 from the
  unique constraint instead of a message; the data stays right (`docs/specs/application.md`
  D5).
- **A status changed in Django admin skips the rules:** no filling, no closing, no email
  (`docs/specs/accept-reject.md` D17).
- **The browser's `confirm()`** before Reject, Cancel and Withdraw guards against a mistake, not
  an attack: the server checks every POST anyway.
- **A work permit cleared by an admin** leaves the worker's applications as they are; they show
  a red "Work permit not confirmed" chip, and the employer can still accept. Decided in #96:
  rare, and checking papers is the employer's duty anyway (see the work permit above).
- **A phone that was seen cannot be taken back.** Hiding it after the job only stops the site
  from showing it. Phones given before #25 were saved without the "who sees it" hint (but shown
  to no one until then).
- **Edit and cancel accept an open job that is already over.** #26 only hides the links;
  revisit in #37.
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
