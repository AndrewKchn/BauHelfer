"""Unit tests: the registration and login forms (#9)."""

import pytest
from django.contrib.auth import get_user_model

from accounts.forms import LoginForm, SignupForm

pytestmark = [pytest.mark.django_db, pytest.mark.story(9)]

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
    """Signup asks only for the email and the password twice.

    1. Open an empty signup form
    2. Expect: fields email, password1, password2 and nothing else
    """
    # Role comes in onboarding (#10); name, phone and work permit (#13) in the profile.
    assert list(SignupForm().fields) == ["email", "password1", "password2"]


def test_valid_signup_creates_user_with_hashed_password():
    """A valid signup creates a user with a hashed password and no role.

    1. Submit an email and a strong password twice
    2. Expect: a new user; the password is stored as a hash and works
    3. Expect: no role yet (#10), no admin rights
    """
    form = SignupForm(data=signup_data())

    assert form.is_valid(), form.errors
    user = form.save()

    assert user.email == "anna@example.com"
    assert user.password != GOOD_PASSWORD  # stored as a hash
    assert user.check_password(GOOD_PASSWORD)
    assert user.role == ""  # chosen later, in onboarding (#10)
    assert not user.is_staff


def test_signup_stores_email_lowercase():
    """Anna@Example.COM signs up as anna@example.com.

    1. Sign up with capital letters in the email
    2. Expect: the email is saved in lowercase
    """
    form = SignupForm(data=signup_data(email="Anna@Example.COM"))

    assert form.is_valid(), form.errors
    assert form.save().email == "anna@example.com"


def test_signup_with_taken_email_is_rejected_in_any_case():
    """An email that is already registered is refused, in any capitals.

    1. anna@example.com exists
    2. Sign up as ANNA@example.com
    3. Expect: an error on the email field
    """
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
    """Addresses that are not emails are refused (no @, no domain…).

    1. Sign up with a broken address, e.g. "anna@"
    2. Expect: an error on the email field
    """
    # Checks the format only; whether the mailbox exists is checked by a link (#81).
    form = SignupForm(data=signup_data(email=email))

    assert not form.is_valid()
    assert "email" in form.errors


def test_signup_with_different_passwords_is_rejected():
    """The two passwords must match.

    1. Sign up with two different passwords
    2. Expect: an error on the second password
    """
    form = SignupForm(data=signup_data(password2="Something-else-2026"))

    assert not form.is_valid()
    assert "password2" in form.errors


def test_signup_with_weak_password_is_rejected():
    """A weak password like 12345678 is refused.

    1. Sign up with 12345678 twice
    2. Expect: an error from Django's password rules
    """
    # Django's password validators: too short, too common, only digits.
    form = SignupForm(data=signup_data(password1="12345678", password2="12345678"))

    assert not form.is_valid()
    assert "password2" in form.errors


def test_login_error_does_not_say_the_email_is_case_sensitive():
    """A wrong login says only "Wrong email or password.".

    1. anna@example.com exists
    2. Log in with a wrong password
    3. Expect: exactly "Wrong email or password.", nothing about capitals
    """
    # Django's default text says "both fields may be case-sensitive"; our email is not.
    User.objects.create_user(email="anna@example.com", password=GOOD_PASSWORD)
    form = LoginForm(data={"username": "anna@example.com", "password": "wrong"})

    assert not form.is_valid()
    error = form.non_field_errors()[0]
    assert error == "Wrong email or password."
