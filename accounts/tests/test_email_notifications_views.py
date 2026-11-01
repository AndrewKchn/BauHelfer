"""Integration tests: the "Email notifications" checkbox on the profile pages (#27).

Each test goes through the whole stack: middleware, URL, view, forms, template and database.
Spec: docs/specs/notifications.md, iteration 2 (R10, R11, R14, D4), acceptance criteria
AC10, AC13, AC14.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains

from accounts.models import EmployerProfile, WorkerProfile

pytestmark = [pytest.mark.django_db, pytest.mark.story(27)]

User = get_user_model()

# What the browser sends for a correctly filled profile form of each role, box unticked.
FORM_DATA = {
    "worker": {
        "name": "Ivan Petrov",
        "phone": "",
        "work_permit": "on",
        "team_size": "3",
        "skills": ["demolition"],
        "languages": ["ru"],
        "legal_status": "gewerbe",
    },
    "employer": {
        "name": "Anna Huber",
        "phone": "",
        "company_name": "Huber Fenster GmbH",
        "trades": ["drywall"],
    },
}


def make_user(role):
    """A user of `role` with a filled profile."""
    user = User.objects.create_user(
        email=f"{role}@example.com", password="x", role=role, name="Test User"
    )
    if role == "worker":
        WorkerProfile.objects.create(
            user=user,
            team_size=1,
            skills=["demolition"],
            languages=["ru"],
            legal_status="gewerbe",
        )
    else:
        EmployerProfile.objects.create(user=user, trades=["drywall"])
    return user


def checkbox(html):
    """The <input> tag of the "Email notifications" checkbox, or None."""
    match = re.search(r'<input[^>]*name="email_notifications"[^>]*>', html)
    return match and match.group()


@pytest.mark.parametrize("role", ["worker", "employer"])
def test_profile_form_has_the_checkbox_ticked(client, role):
    """The profile form of both roles shows "Email notifications", ticked (R10).

    The same form opens right after the role choice, so this is also "at signup" (D4).

    1. Log in as a new worker (or employer) and open the profile form
    2. Expect: a checkbox "email_notifications", ticked, labelled "Email notifications"
    """
    client.force_login(make_user(role))

    response = client.get(reverse(f"{role}_profile_edit"))

    tag = checkbox(response.content.decode())
    assert tag, "no email_notifications checkbox"
    assert "checked" in tag
    assertContains(response, "Email notifications")


@pytest.mark.parametrize("role", ["worker", "employer"])
def test_saving_the_profile_unticked_turns_the_emails_off(client, role):
    """Saving the profile form with the box unticked turns the emails off.

    1. Log in as a worker (or employer) and send the profile form without the box
    2. Expect: a redirect to the profile page; email_notifications is False
    """
    user = make_user(role)
    client.force_login(user)

    response = client.post(reverse(f"{role}_profile_edit"), FORM_DATA[role])

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.email_notifications is False


@pytest.mark.parametrize("role", ["worker", "employer"])
@pytest.mark.parametrize(("on", "text"), [(True, "On"), (False, "Off")])
def test_profile_page_says_whether_the_emails_are_on(client, role, on, text):
    """The profile page of both roles says "Email notifications" On or Off (R11).

    1. Log in as a worker (or employer) with the emails on (or off)
    2. Open the profile page
    3. Expect: "Email notifications" followed by "On" (or "Off")
    """
    user = make_user(role)
    user.email_notifications = on
    user.save()
    client.force_login(user)

    response = client.get(reverse(f"{role}_profile"))

    html = re.sub(r"\s+", " ", response.content.decode())
    assert re.search(rf"Email notifications</dt> <dd[^>]*>{text}</dd>", html), html


def test_password_reset_ignores_the_checkbox(client, mailoutbox):
    """Password emails are always sent, whatever the checkbox says (R14; AC13).

    1. Turn a confirmed worker's notifications off
    2. Ask for a password reset with their email
    3. Expect: one email, to them
    """
    user = make_user("worker")
    user.email_notifications = False
    user.email_verified_at = timezone.now()  # only confirmed addresses get it (D13)
    user.save()

    client.post(reverse("password_reset"), {"email": "worker@example.com"})

    assert [email.to for email in mailoutbox] == [["worker@example.com"]]


@pytest.mark.parametrize(
    ("role", "last_field"), [("worker", "legal_status"), ("employer", "trades")]
)
def test_checkbox_is_last_before_save(client, role, last_field):
    """The checkbox is a setting, so it comes after all profile fields (mine, D4).

    1. Log in as a worker (or employer) and open the profile form
    2. Expect: the checkbox comes after the last profile field and before "Save profile"
    """
    client.force_login(make_user(role))

    html = client.get(reverse(f"{role}_profile_edit")).content.decode()

    last = html.rindex(f'name="{last_field}"')
    box = html.index('name="email_notifications"')
    save = html.index("Save profile")
    assert last < box < save
