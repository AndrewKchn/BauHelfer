"""Unit tests for the custom User model and its manager (#8)."""

import pytest
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_auth_user_model_is_custom():
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_email_is_the_login_field_and_username_is_gone():
    assert User.USERNAME_FIELD == "email"
    with pytest.raises(FieldDoesNotExist):
        User._meta.get_field("username")


def test_create_user_with_email_and_password():
    user = User.objects.create_user(email="anna@example.com", password="s3cret-pass")

    assert user.email == "anna@example.com"
    assert user.check_password("s3cret-pass")
    assert user.is_active
    assert not user.is_staff
    assert not user.is_superuser


def test_create_user_without_email_raises():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="s3cret-pass")


def test_email_is_stored_lowercase():
    user = User.objects.create_user(email="Anna@Example.COM", password="s3cret-pass")

    assert user.email == "anna@example.com"


def test_email_is_unique_ignoring_case():
    User.objects.create_user(email="anna@example.com", password="s3cret-pass")

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="ANNA@example.com", password="other-pass")


def test_new_user_defaults():
    user = User.objects.create_user(email="anna@example.com", password="s3cret-pass")

    assert user.name == ""
    assert user.phone == ""
    assert user.role == ""  # chosen later, in onboarding (#10)
    assert user.preferred_language == "en"
    assert user.work_permit_confirmed is False


def test_extra_fields_are_saved():
    user = User.objects.create_user(
        email="anna@example.com",
        password="s3cret-pass",
        name="Anna Kowalska",
        phone="+49 151 1234567",
        role=User.Role.WORKER,
        preferred_language="pl",
        work_permit_confirmed=True,
    )
    user.refresh_from_db()

    assert user.name == "Anna Kowalska"
    assert user.phone == "+49 151 1234567"
    assert user.role == "worker"
    assert user.preferred_language == "pl"
    assert user.work_permit_confirmed is True


def test_role_choices():
    assert set(User.Role.values) == {"employer", "worker"}


def test_unknown_role_is_rejected_by_validation():
    user = User(email="anna@example.com", role="boss")
    user.set_password("s3cret-pass")

    with pytest.raises(ValidationError) as error:
        user.full_clean()
    assert "role" in error.value.message_dict


def test_language_choices_are_the_seven_site_languages():
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
    admin = User.objects.create_superuser(
        email="admin@example.com", password="s3cret-pass"
    )

    assert admin.is_staff
    assert admin.is_superuser
    assert admin.role == ""


def test_create_superuser_must_be_staff():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="admin@example.com", password="s3cret-pass", is_staff=False
        )


def test_str_is_email():
    user = User(email="anna@example.com")

    assert str(user) == "anna@example.com"


def test_authenticate_with_email_ignoring_case():
    user = User.objects.create_user(email="anna@example.com", password="s3cret-pass")

    assert authenticate(email="Anna@Example.com", password="s3cret-pass") == user
    assert authenticate(email="anna@example.com", password="wrong") is None
