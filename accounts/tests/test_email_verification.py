"""Unit tests: the confirmation link's token, the login hint and who gets a new link (#81).

Spec: docs/specs/email-verification.md, iteration 1 (R4, R6, D2, D5) and iteration 2 (R9,
R10, D10, D11), acceptance criteria AC5–AC9, AC13, AC15.
"""

from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone

from accounts.emails import send_verification_email
from accounts.forms import LoginForm
from accounts.tokens import email_verification_token

pytestmark = [pytest.mark.django_db, pytest.mark.story(81)]

User = get_user_model()

PASSWORD = "Gerüst-2026-Munich"


def make_user(active=False, confirmed=False):
    """A user as signup leaves them (inactive, unconfirmed), or changed by the flags."""
    return User.objects.create_user(
        email="ben@example.com",
        password=PASSWORD,
        is_active=active,
        email_verified_at=timezone.now() if confirmed else None,
    )


# The token (R4, D5)


def test_token_of_a_new_account_is_valid():
    """A fresh token is accepted for the account it was made for.

    1. Create an inactive, unconfirmed user
    2. Make a token for them
    3. Expect: the generator accepts it
    """
    user = make_user()

    token = email_verification_token.make_token(user)

    assert email_verification_token.check_token(user, token)


def test_token_works_only_until_the_address_is_confirmed():
    """After the address is confirmed, the same token is refused (AC5).

    1. Make a token for an unconfirmed user
    2. Confirm the address and activate the account, as the link does
    3. Expect: the token is refused
    """
    user = make_user()
    token = email_verification_token.make_token(user)

    user.email_verified_at = timezone.now()
    user.is_active = True
    user.save()

    assert not email_verification_token.check_token(user, token)


def test_token_expires_after_the_password_reset_timeout(monkeypatch):
    """A token older than PASSWORD_RESET_TIMEOUT is refused (AC6).

    1. Make a token now
    2. Move the generator's clock one second past the timeout
    3. Expect: the token is refused
    """
    user = make_user()
    token = email_verification_token.make_token(user)
    later = email_verification_token._now() + timedelta(
        seconds=settings.PASSWORD_RESET_TIMEOUT + 1
    )

    monkeypatch.setattr(email_verification_token, "_now", lambda: later)

    assert not email_verification_token.check_token(user, token)


def test_password_reset_token_is_not_a_confirmation_token():
    """A reset token does not confirm an address, and the other way round (AC7).

    1. Make a password reset token and a confirmation token for the same user
    2. Expect: each generator refuses the other's token
    """
    user = make_user()
    reset_token = default_token_generator.make_token(user)
    confirm_token = email_verification_token.make_token(user)

    assert not email_verification_token.check_token(user, reset_token)
    assert not default_token_generator.check_token(user, confirm_token)


# The login hint (R6, D2)


def login_form(password=PASSWORD):
    """The login form, sent with Ben's email and `password`."""
    return LoginForm(data={"username": "ben@example.com", "password": password})


def test_unconfirmed_account_with_the_right_password_gets_the_hint():
    """The right password on an unconfirmed account asks to confirm the email (AC8).

    1. Create an inactive, unconfirmed user
    2. Send the login form with the right password
    3. Expect: the form is invalid with the "unconfirmed" error and its text
    """
    make_user()

    form = login_form()

    assert not form.is_valid()
    assert form.has_error("__all__", code="unconfirmed")
    assert "Please confirm your email first." in form.non_field_errors()[0]


def test_unconfirmed_account_with_a_wrong_password_gets_the_usual_error():
    """A wrong password tells nothing about the account (AC8).

    1. Create an inactive, unconfirmed user
    2. Send the login form with a wrong password
    3. Expect: the usual "invalid_login" error, not the hint
    """
    make_user()

    form = login_form(password="wrong")

    assert not form.is_valid()
    assert form.has_error("__all__", code="invalid_login")
    assert not form.has_error("__all__", code="unconfirmed")


def test_blocked_account_with_a_confirmed_address_gets_the_usual_error():
    """An account an admin turned off is not told to confirm its email (AC9).

    1. Create an inactive user whose address is confirmed
    2. Send the login form with the right password
    3. Expect: the usual "invalid_login" error, not the hint
    """
    make_user(confirmed=True)

    form = login_form()

    assert not form.is_valid()
    assert form.has_error("__all__", code="invalid_login")
    assert not form.has_error("__all__", code="unconfirmed")


# Who may get a new link (iteration 2: R9, R10, D10, D11)


@pytest.mark.parametrize(
    ("minutes_ago", "allowed"), [(None, True), (9.98, False), (10.02, True)]
)
def test_new_link_at_most_every_10_minutes(minutes_ago, allowed):
    """An unconfirmed account gets a new link only 10 minutes after the last one (AC13).

    1. Create an unconfirmed user whose last link went out never / 9.98 / 10.02 min ago
    2. Expect: a new link is allowed / refused / allowed
    """
    user = make_user()
    if minutes_ago is not None:
        user.verification_sent_at = timezone.now() - timedelta(minutes=minutes_ago)

    assert user.can_get_verification_email() is allowed


@pytest.mark.parametrize(
    ("active", "confirmed", "allowed"),
    [(False, False, True), (True, False, True), (True, True, False)],
)
def test_only_unconfirmed_accounts_get_a_link(active, confirmed, allowed):
    """Any unconfirmed account, active or not, may get a link; a confirmed one not (D11).

    1. Create an inactive unconfirmed / active unconfirmed / confirmed user
    2. Expect: a link is allowed / allowed / refused
    """
    user = make_user(active=active, confirmed=confirmed)

    assert user.can_get_verification_email() is allowed


def test_successful_send_records_the_time(rf, mailoutbox):
    """After the email went out, the user remembers when (R10, AC15).

    1. Send the confirmation email to a new user
    2. Expect: one email and verification_sent_at is set
    """
    user = make_user()

    send_verification_email(rf.get("/"), user)

    user.refresh_from_db()
    assert len(mailoutbox) == 1
    assert user.verification_sent_at is not None


def test_failed_send_leaves_the_time_empty(rf, settings):
    """A failed send records nothing, so the user may try again at once (R10, AC15).

    1. Use an email backend that raises
    2. Send the confirmation email to a new user
    3. Expect: verification_sent_at stays empty
    """
    settings.EMAIL_BACKEND = "jobs.tests.test_notifications.FailingBackend"
    user = make_user()

    send_verification_email(rf.get("/"), user)

    user.refresh_from_db()
    assert user.verification_sent_at is None
