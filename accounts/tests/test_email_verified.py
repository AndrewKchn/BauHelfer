"""Unit tests: emails go only to confirmed addresses (#27).

Spec: docs/specs/notifications.md, iteration 3 (R19, R21, D13), acceptance criteria AC17,
AC18. #81 fills the field from a link; here it is set by hand, as an admin would.
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.forms import ConfirmedPasswordResetForm

pytestmark = [pytest.mark.django_db, pytest.mark.story(27)]

User = get_user_model()


def make_user(email, confirmed):
    """A worker; with `confirmed`, their address is confirmed now."""
    return User.objects.create_user(
        email=email,
        password="x",
        role="worker",
        email_verified_at=timezone.now() if confirmed else None,
    )


def test_new_account_is_unconfirmed():
    """A new account has no confirmation date: nobody has shown the address is theirs.

    1. Create a user
    2. Expect: email_verified_at is empty
    """
    user = User.objects.create_user(email="anna@example.com", password="x")

    assert user.email_verified_at is None


def test_password_reset_goes_only_to_a_confirmed_address():
    """The reset form finds a confirmed account and skips an unconfirmed one (R21).

    Django's form sends one email per account get_users() returns.

    1. Create Anna (confirmed) and Ivan (not)
    2. Ask the reset form for the accounts of each address
    3. Expect: Anna's account for her address; nothing for Ivan's
    """
    anna = make_user("anna@example.com", confirmed=True)
    make_user("ivan@example.com", confirmed=False)
    form = ConfirmedPasswordResetForm()

    assert list(form.get_users("anna@example.com")) == [anna]
    assert list(form.get_users("ivan@example.com")) == []
