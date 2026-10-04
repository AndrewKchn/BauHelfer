"""Unit tests for the registration form (#9)."""

import pytest
from django.contrib.auth import get_user_model

from accounts.forms import SignupForm

pytestmark = pytest.mark.django_db

User = get_user_model()

GOOD_PASSWORD = "Gerüst-2026-Munich"


def signup_data(**overrides):
    """Valid form data; tests change one field to check one rule."""
    data = {
        "email": "anna@example.com",
        "password1": GOOD_PASSWORD,
        "password2": GOOD_PASSWORD,
    }
    data.update(overrides)
    return data


def test_signup_form_asks_only_email_and_password():
    # Role comes in onboarding (#10), work permit in #13, name and phone in the profile.
    assert list(SignupForm().fields) == ["email", "password1", "password2"]


def test_valid_signup_creates_user_with_hashed_password():
    form = SignupForm(data=signup_data())

    assert form.is_valid(), form.errors
    user = form.save()

    assert user.email == "anna@example.com"
    assert user.password != GOOD_PASSWORD  # stored as a hash
    assert user.check_password(GOOD_PASSWORD)
    assert user.role == ""  # chosen later, in onboarding (#10)
    assert not user.is_staff


def test_signup_stores_email_lowercase():
    form = SignupForm(data=signup_data(email="Anna@Example.COM"))

    assert form.is_valid(), form.errors
    assert form.save().email == "anna@example.com"


def test_signup_with_taken_email_is_rejected_in_any_case():
    User.objects.create_user(email="anna@example.com", password=GOOD_PASSWORD)

    form = SignupForm(data=signup_data(email="ANNA@example.com"))

    assert not form.is_valid()
    assert "email" in form.errors


@pytest.mark.parametrize(
    "email",
    [
        "not-an-email",  # no @
        "anna@",  # no domain
        "@example.com",  # no name
        "anna@example",  # domain without a dot
        "anna@@example.com",  # two @
        "anna smith@example.com",  # space
    ],
)
def test_signup_with_invalid_email_is_rejected(email):
    # Checks the format only; whether the mailbox exists is checked by a link (#81).
    form = SignupForm(data=signup_data(email=email))

    assert not form.is_valid()
    assert "email" in form.errors


def test_signup_with_different_passwords_is_rejected():
    form = SignupForm(data=signup_data(password2="Something-else-2026"))

    assert not form.is_valid()
    assert "password2" in form.errors


def test_signup_with_weak_password_is_rejected():
    # Django's password validators: too short, too common, only digits.
    form = SignupForm(data=signup_data(password1="12345678", password2="12345678"))

    assert not form.is_valid()
    assert "password2" in form.errors
