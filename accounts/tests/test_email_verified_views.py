"""Integration tests: password reset and Django admin with confirmed addresses (#27).

Each test goes through the whole stack: middleware, URL, view, form, template and database.
Spec: docs/specs/notifications.md, iteration 3 (R21, R22, D13), acceptance criteria AC18,
AC19.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.story(27)]

User = get_user_model()

PASSWORD = "Gerüst-2026-Munich"


@pytest.mark.parametrize(("confirmed", "emails"), [(True, 1), (False, 0)])
def test_reset_page_looks_the_same_whether_an_email_was_sent(
    client, mailoutbox, confirmed, emails
):
    """An unconfirmed account gets no reset email, and the page does not tell (R21).

    The same "Check your email" page as for an unknown address: the form must not reveal
    which addresses have an account.

    1. Create a worker, with a confirmed address or without
    2. Send the password reset form with that address
    3. Expect: a redirect to the "email sent" page in both cases
    4. Expect: one email for the confirmed account, none for the unconfirmed one
    """
    User.objects.create_user(
        email="ivan@example.com",
        password=PASSWORD,
        role="worker",
        email_verified_at=timezone.now() if confirmed else None,
    )

    response = client.post(reverse("password_reset"), {"email": "ivan@example.com"})

    assert response.status_code == 302
    assert response.url == reverse("password_reset_done")
    assert len(mailoutbox) == emails


@pytest.fixture
def admin_client_(client):
    """A browser logged in as a superuser."""
    admin = User.objects.create_superuser(email="admin@example.com", password=PASSWORD)
    client.force_login(admin)
    return client


def test_admin_shows_the_confirmation_and_the_checkbox(admin_client_):
    """A user's admin page has both email fields (R22).

    1. Open the admin page of a worker
    2. Expect: the fields email_verified_at and email_notifications
    """
    user = User.objects.create_user(email="ivan@example.com", password=PASSWORD)

    response = admin_client_.get(reverse("admin:accounts_user_change", args=[user.pk]))

    fields = response.context["adminform"].form.fields
    assert "email_verified_at" in fields
    assert "email_notifications" in fields


def test_admin_confirms_a_demo_account(admin_client_):
    """A superuser confirms an address by hand, e.g. a demo account (R22; AC19).

    1. Create a worker with an unconfirmed address
    2. On the user's admin page, set the confirmation to 1 November 2026, 10:00
    3. Expect: email_verified_at is that moment
    """
    user = User.objects.create_user(email="ivan@example.com", password=PASSWORD)

    response = admin_client_.post(
        reverse("admin:accounts_user_change", args=[user.pk]),
        {
            "email": "ivan@example.com",
            "preferred_language": "en",
            "is_active": "on",
            "email_notifications": "on",
            # A date and time field is shown as two inputs: date and time.
            "email_verified_at_0": "2026-11-01",
            "email_verified_at_1": "10:00:00",
            "date_joined_0": user.date_joined.strftime("%Y-%m-%d"),
            "date_joined_1": user.date_joined.strftime("%H:%M:%S"),
        },
    )

    assert response.status_code == 302, response.context["adminform"].form.errors
    user.refresh_from_db()
    local = timezone.localtime(user.email_verified_at)
    assert (local.date().isoformat(), local.strftime("%H:%M")) == (
        "2026-11-01",
        "10:00",
    )
