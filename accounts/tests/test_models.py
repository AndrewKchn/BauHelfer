"""Unit tests: the custom User model and its manager (#8)."""

import pytest
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.story(8)]

User = get_user_model()


def test_auth_user_model_is_custom():
    """Django uses our User model, not its built-in one.

    1. Read the AUTH_USER_MODEL setting
    2. Expect: "accounts.User"
    """
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_email_is_the_login_field_and_username_is_gone():
    """People log in with their email; there is no username field.

    1. Look at the User model
    2. Expect: the login field is email
    3. Expect: no username field
    """
    assert User.USERNAME_FIELD == "email"
    with pytest.raises(FieldDoesNotExist):
        User._meta.get_field("username")


def test_create_user_with_email_and_password():
    """A new account is created from an email and a password.

    1. Create a user with email and password
    2. Expect: the password is stored as a hash and works
    3. Expect: active, not staff, not superuser
    """
    user = User.objects.create_user(email="anna@example.com", password="s3cret-pass")

    assert user.email == "anna@example.com"
    assert user.check_password("s3cret-pass")
    assert user.is_active
    assert not user.is_staff
    assert not user.is_superuser


def test_create_user_without_email_raises():
    """An account cannot be created without an email.

    1. Create a user with an empty email
    2. Expect: an error
    """
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="s3cret-pass")


def test_email_is_stored_lowercase():
    """Anna@Example.COM is saved as anna@example.com.

    1. Create a user with capital letters in the email
    2. Expect: the email is saved in lowercase
    """
    user = User.objects.create_user(email="Anna@Example.COM", password="s3cret-pass")

    assert user.email == "anna@example.com"


def test_email_is_unique_ignoring_case():
    """The same email in other capitals cannot get a second account.

    1. Create anna@example.com
    2. Create ANNA@example.com
    3. Expect: the database refuses the second one
    """
    User.objects.create_user(email="anna@example.com", password="s3cret-pass")

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="ANNA@example.com", password="other-pass")


def test_new_user_defaults():
    """A new account starts with no name, phone or role, in English.

    1. Create a user with only email and password
    2. Expect: empty name, phone and role (the role comes in onboarding, #10)
    3. Expect: language English, no work-permit confirmation date
    """
    user = User.objects.create_user(email="anna@example.com", password="s3cret-pass")

    assert user.name == ""
    assert user.phone == ""
    assert user.role == ""  # chosen later, in onboarding (#10)
    assert user.preferred_language == "en"
    assert (
        user.work_permit_confirmed_at is None
    )  # confirmed in the worker profile (#13)


def test_extra_fields_are_saved():
    """Name, phone, role, language and work permit are saved.

    1. Create a user with all profile fields
    2. Read the user again from the database
    3. Expect: every field has the saved value
    """
    confirmed_at = timezone.now()
    user = User.objects.create_user(
        email="anna@example.com",
        password="s3cret-pass",
        name="Anna Kowalska",
        phone="+49 151 1234567",
        role=User.Role.WORKER,
        preferred_language="pl",
        work_permit_confirmed_at=confirmed_at,
    )
    user.refresh_from_db()

    assert user.name == "Anna Kowalska"
    assert user.phone == "+49 151 1234567"
    assert user.role == "worker"
    assert user.preferred_language == "pl"
    assert user.work_permit_confirmed_at == confirmed_at


def test_role_choices():
    """A user is either an employer or a worker.

    1. Look at the role choices
    2. Expect: exactly employer and worker
    """
    assert set(User.Role.values) == {"employer", "worker"}


def test_unknown_role_is_rejected_by_validation():
    """A role other than employer or worker is refused.

    1. Make a user with the role "boss"
    2. Validate the user
    3. Expect: an error on the role field
    """
    user = User(email="anna@example.com", role="boss")
    user.set_password("s3cret-pass")

    with pytest.raises(ValidationError) as error:
        user.full_clean()
    assert "role" in error.value.message_dict


def test_language_choices_are_the_seven_site_languages():
    """The preferred language is one of the 7 site languages.

    1. Look at the language choices
    2. Expect: DE, EN, RU, UK, PL, RO, TR
    """
    field = User._meta.get_field("preferred_language")

    assert {code for code, _label in field.choices} == {
        "de",
        "en",
        "ru",
        "uk",
        "pl",
        "ro",
        "tr",
    }


def test_create_superuser():
    """An admin account has admin rights and no role.

    1. Create a superuser
    2. Expect: staff and superuser rights, empty role
    """
    admin = User.objects.create_superuser(
        email="admin@example.com", password="s3cret-pass"
    )

    assert admin.is_staff
    assert admin.is_superuser
    assert admin.role == ""


def test_create_superuser_must_be_staff():
    """An admin without staff rights cannot be created.

    1. Create a superuser with is_staff=False
    2. Expect: an error
    """
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="admin@example.com", password="s3cret-pass", is_staff=False
        )


def test_str_is_email():
    """A user is shown by their email, e.g. in the admin.

    1. Turn a user into text
    2. Expect: their email
    """
    user = User(email="anna@example.com")

    assert str(user) == "anna@example.com"


def test_authenticate_with_email_ignoring_case():
    """Login finds the account with the email in any capitals.

    1. An account anna@example.com exists
    2. Log in as Anna@Example.com with the right password
    3. Expect: that account
    4. Log in with a wrong password
    5. Expect: no account
    """
    user = User.objects.create_user(email="anna@example.com", password="s3cret-pass")

    assert authenticate(email="Anna@Example.com", password="s3cret-pass") == user
    assert authenticate(email="anna@example.com", password="wrong") is None
