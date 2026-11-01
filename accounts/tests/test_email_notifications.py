"""Unit tests: the "Email notifications" checkbox on the user and in the profile form (#27).

Spec: docs/specs/notifications.md, iteration 2 (R9, R10, D3, D4), acceptance criteria AC9,
AC10. The pages are in test_email_notifications_views.py; what the emails do with it in
jobs/tests/test_notifications.py.
"""

import pytest
from django.contrib.auth import get_user_model

from accounts.forms import NameAndPhoneForm, WorkerUserForm

pytestmark = [pytest.mark.django_db, pytest.mark.story(27)]

User = get_user_model()


@pytest.fixture
def user():
    """A new employer, as the signup and the role choice leave them."""
    return User.objects.create_user(
        email="anna@example.com", password="x", role="employer", name="Anna Huber"
    )


def test_new_user_gets_the_emails(user):
    """A new account has the notifications on: the emails are the point of them (D3).

    1. Create a user
    2. Expect: email_notifications is True
    """
    assert user.email_notifications is True


@pytest.mark.parametrize("form_class", [NameAndPhoneForm, WorkerUserForm])
def test_profile_form_shows_the_checkbox_ticked(user, form_class):
    """The name-and-phone form of both roles has the checkbox, ticked for a new user.

    1. Build the employer's form (NameAndPhoneForm), then the worker's (WorkerUserForm)
    2. Expect: a field "email_notifications", ticked
    """
    form = form_class(instance=user)

    assert "email_notifications" in form.fields
    assert form["email_notifications"].value() is True


def test_unticking_the_checkbox_turns_the_emails_off(user):
    """A browser sends nothing for an unticked box, and that saves "off".

    1. Send the employer's name form without "email_notifications"
    2. Expect: the form is valid; the user has email_notifications False
    """
    form = NameAndPhoneForm({"name": "Anna Huber", "phone": ""}, instance=user)

    assert form.is_valid(), form.errors
    form.save()
    user.refresh_from_db()
    assert user.email_notifications is False


def test_ticking_the_checkbox_turns_the_emails_on_again(user):
    """A user who turned them off can turn them on again.

    1. Turn Anna's notifications off
    2. Send her name form with "email_notifications" ticked
    3. Expect: email_notifications is True
    """
    user.email_notifications = False
    user.save()

    form = NameAndPhoneForm(
        {"name": "Anna Huber", "phone": "", "email_notifications": "on"}, instance=user
    )

    assert form.is_valid(), form.errors
    form.save()
    user.refresh_from_db()
    assert user.email_notifications is True
