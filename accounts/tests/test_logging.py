"""Integration tests: signup and failed logins are logged with the user id only (#124).

A failed login is caught by Django's user_login_failed signal, so the admin login counts
too. The email a person typed must never reach the logs: they are personal data.
"""

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.story(124)]

User = get_user_model()

PASSWORD = "Gerüst-2026-Munich"


@pytest.fixture
def user():
    """An existing worker account."""
    return User.objects.create_user(
        email="anna@example.com", password=PASSWORD, role=User.Role.WORKER
    )


def app_records(caplog):
    """The records our accounts app wrote, without Django's own ones."""
    return [r for r in caplog.records if r.name.startswith("accounts")]


def test_signup_is_logged_with_the_new_user_id(client, caplog):
    """Signup writes one INFO record with the new user's id and no email.

    1. Sign up as ben@example.com
    2. Expect: one INFO record "User registered: user_id=<id>"
    3. Expect: the email is in no record
    """
    client.post(
        reverse("register"),
        {"email": "ben@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )

    user = User.objects.get()
    [record] = app_records(caplog)
    assert record.levelname == "INFO"
    assert record.getMessage() == f"User registered: user_id={user.pk}"
    assert "ben@example.com" not in caplog.text


def test_wrong_password_is_logged_as_a_warning_with_the_user_id(client, user, caplog):
    """A wrong password on the login page writes one WARNING with the user id.

    1. Log in as anna@example.com with a wrong password
    2. Expect: one WARNING record "Failed login: user_id=<id>"
    3. Expect: the email is in no record
    """
    client.post(reverse("login"), {"username": "anna@example.com", "password": "wrong"})

    [record] = app_records(caplog)
    assert record.levelname == "WARNING"
    assert record.getMessage() == f"Failed login: user_id={user.pk}"
    assert "anna@example.com" not in caplog.text


def test_failed_login_finds_the_user_in_any_capitalisation(user, caplog):
    """The user id is found as login finds the user: the email in any capitalisation.

    1. Call authenticate() with ANNA@Example.com and a wrong password
    2. Expect: the record names Anna's user id
    """
    authenticate(None, username="ANNA@Example.com", password="wrong")

    [record] = app_records(caplog)
    assert record.getMessage() == f"Failed login: user_id={user.pk}"


def test_unknown_email_is_logged_without_the_email(client, caplog):
    """A login with an email nobody registered is logged without that email.

    1. Log in as nobody@example.com
    2. Expect: one WARNING record "Failed login: unknown account"
    3. Expect: the email is in no record
    """
    client.post(
        reverse("login"), {"username": "nobody@example.com", "password": "wrong"}
    )

    [record] = app_records(caplog)
    assert record.levelname == "WARNING"
    assert record.getMessage() == "Failed login: unknown account"
    assert "nobody@example.com" not in caplog.text


def test_failed_admin_login_is_logged_too(client, user, caplog):
    """A wrong password on /admin/ is logged like one on our login page.

    1. Log in to the admin as anna@example.com with a wrong password
    2. Expect: one WARNING record "Failed login: user_id=<id>"
    """
    client.post(
        reverse("admin:login"), {"username": "anna@example.com", "password": "wrong"}
    )

    [record] = app_records(caplog)
    assert record.levelname == "WARNING"
    assert record.getMessage() == f"Failed login: user_id={user.pk}"


def test_successful_login_writes_no_warning(client, user, caplog):
    """A correct login is not a failed one.

    1. Log in as anna@example.com with the right password
    2. Expect: no record from the accounts app
    """
    client.post(
        reverse("login"), {"username": "anna@example.com", "password": PASSWORD}
    )

    assert app_records(caplog) == []
