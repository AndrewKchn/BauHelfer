"""Integration tests: the demo switch at signup and in Django admin (#81).

Each test goes through the whole stack: middleware, URL, view, form, template and database.
Spec: docs/specs/email-verification.md, iteration 3 (R14, R15, D14), acceptance criteria
AC18–AC21.
"""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from pytest_django.asserts import assertContains, assertRedirects

from accounts.models import SiteSettings

pytestmark = [pytest.mark.django_db, pytest.mark.story(81)]

User = get_user_model()

PASSWORD = "Gerüst-2026-Munich"


@pytest.fixture
def switch():
    """The SiteSettings row, verification on."""
    return SiteSettings.load()


def change_url(switch):
    """The admin page of the one SiteSettings row."""
    return reverse("admin:accounts_sitesettings_change", args=[switch.pk])


def test_signup_with_the_switch_off_logs_in_at_once(client, mailoutbox, switch):
    """With verification off, signup works as before #81: active, logged in, no email (AC18).

    1. Turn the switch off
    2. Sign up as ben@example.com
    3. Expect: a redirect to the role choice with the welcome message
    4. Expect: Ben is active, logged in, unconfirmed; no email went out
    """
    switch.email_verification_required = False
    switch.save()

    response = client.post(
        reverse("register"),
        {"email": "ben@example.com", "password1": PASSWORD, "password2": PASSWORD},
        follow=True,
    )

    assertRedirects(response, reverse("role_select"))
    assertContains(response, "Welcome to BauHelfer! Your account is ready.")
    user = User.objects.get()
    assert user.is_active
    assert user.email_verified_at is None
    assert "_auth_user_id" in client.session
    assert mailoutbox == []


def test_superuser_turns_the_switch_off_in_admin(client, switch):
    """A superuser changes the switch in admin, and the history records it (AC19).

    1. Log in as a superuser, open "Site settings", untick the switch, save
    2. Expect: a redirect; the switch is off
    3. Expect: one CHANGE entry by that superuser in admin's history
    """
    admin = User.objects.create_superuser(email="admin@example.com", password=PASSWORD)
    client.force_login(admin)

    response = client.post(
        change_url(switch), {"_save": "Save"}
    )  # box not ticked = off

    assert response.status_code == 302
    assert SiteSettings.load().email_verification_required is False
    assert LogEntry.objects.filter(
        user=admin, object_id=str(switch.pk), action_flag=CHANGE
    ).exists()


def test_staff_without_superuser_cannot_see_or_change_the_switch(client, switch):
    """Staff who is not a superuser gets 403, even with every permission (AC20, D14).

    1. Log in as a staff user with add / change / delete / view permission on SiteSettings
    2. Open the change page; post the form with the switch off
    3. Expect: 403 both times; the switch is still on
    """
    staff = User.objects.create_user(
        email="staff@example.com", password=PASSWORD, is_staff=True
    )
    staff.user_permissions.set(
        Permission.objects.filter(content_type__model="sitesettings")
    )
    client.force_login(staff)

    assert client.get(change_url(switch)).status_code == 403
    assert client.post(change_url(switch), {"_save": "Save"}).status_code == 403
    assert SiteSettings.load().email_verification_required is True


def test_nobody_adds_or_deletes_the_row(client, switch):
    """Not even a superuser can add a second row or delete the one row (AC21).

    1. Log in as a superuser
    2. Open the add page and the delete page of the row
    3. Expect: 403 both times; still one row
    """
    admin = User.objects.create_superuser(email="admin@example.com", password=PASSWORD)
    client.force_login(admin)

    add = client.get(reverse("admin:accounts_sitesettings_add"))
    delete = client.get(reverse("admin:accounts_sitesettings_delete", args=[switch.pk]))

    assert add.status_code == 403
    assert delete.status_code == 403
    assert SiteSettings.objects.count() == 1
