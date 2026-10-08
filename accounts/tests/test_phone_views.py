"""Integration tests: the phone check on the profile pages and in the admin (#109).

Each test goes through the whole stack: URL, view, forms, template and database.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from pytest_django.asserts import assertContains

from accounts.models import EmployerProfile, WorkerProfile

pytestmark = [pytest.mark.django_db, pytest.mark.story(109)]

User = get_user_model()

ERROR = (
    "Enter the number with a country code, e.g. +49 151 12345678, "
    "or with an area code, e.g. 0151 12345678."
)
HINT = "For example +49 151 12345678 or 0151 12345678."

# What the browser sends for a correctly filled profile form, per role.
FORMS = {
    "worker": (
        "worker_profile_edit",
        WorkerProfile,
        {
            "name": "Ivan Petrov",
            "work_permit": "on",
            "team_size": "3",
            "skills": ["demolition"],
            "languages": ["ru", "de"],
            "legal_status": "gewerbe",
        },
    ),
    "employer": (
        "employer_profile_edit",
        EmployerProfile,
        {
            "name": "Anna Huber",
            "company_name": "Huber Fenster GmbH",
            "trades": ["drywall"],
        },
    ),
}


@pytest.fixture(params=["worker", "employer"])
def user(request):
    """A worker or an employer without a phone and without a profile."""
    return User.objects.create_user(
        email=f"{request.param}@example.com", password="x", role=request.param
    )


@pytest.fixture
def logged_in_client(client, user):
    """A browser logged in as that user."""
    client.force_login(user)
    return client


def test_wrong_phone_is_not_saved(logged_in_client, user):
    """A phone without a code shows the error with both formats; nothing is saved.

    1. Log in as a worker / an employer without a profile
    2. Send the profile form with the phone "call my brother"
    3. Expect: the form again with the error showing both formats
    4. Expect: no profile saved, the phone is still empty
    """
    url_name, profile_model, data = FORMS[user.role]

    response = logged_in_client.post(
        reverse(url_name), {**data, "phone": "call my brother"}
    )

    assertContains(response, ERROR)
    assert profile_model.objects.count() == 0
    user.refresh_from_db()
    assert user.phone == ""


def test_phone_is_saved_as_entered(logged_in_client, user):
    """A valid number is saved exactly as typed.

    1. Log in as a worker / an employer without a profile
    2. Send the profile form with the phone "0151-123/456 78"
    3. Expect: a redirect; the profile is saved; the phone is "0151-123/456 78"
    """
    url_name, profile_model, data = FORMS[user.role]

    response = logged_in_client.post(
        reverse(url_name), {**data, "phone": "0151-123/456 78"}
    )

    assert response.status_code == 302
    assert profile_model.objects.count() == 1
    user.refresh_from_db()
    assert user.phone == "0151-123/456 78"


def test_profile_form_has_a_tel_input_and_a_hint(logged_in_client, user):
    """The profile form shows the phone as a tel input with the format hint.

    1. Log in as a worker / an employer
    2. Open the profile form
    3. Expect: the phone input has type="tel"; the hint shows both formats
    """
    url_name, _, _ = FORMS[user.role]

    response = logged_in_client.get(reverse(url_name))

    assertContains(response, 'type="tel" name="phone"')
    assertContains(response, HINT)


def test_admin_rejects_a_wrong_phone(client):
    """The admin uses the same check, because it is on the model.

    1. A user exists; an admin is logged in
    2. Save the user's admin page with the phone "abc"
    3. Expect: the page again with an error on phone; the phone is not saved
    """
    admin = User.objects.create_superuser(email="admin@example.com", password="x")
    user = User.objects.create_user(email="anna@example.com", password="x")
    client.force_login(admin)

    response = client.post(
        reverse("admin:accounts_user_change", args=[user.pk]),
        {
            "email": "anna@example.com",
            "phone": "abc",
            "preferred_language": "en",
            "is_active": "on",
            "date_joined_0": user.date_joined.strftime("%Y-%m-%d"),
            "date_joined_1": user.date_joined.strftime("%H:%M:%S"),
        },
    )

    assert response.status_code == 200
    assert "phone" in response.context["adminform"].form.errors
    user.refresh_from_db()
    assert user.phone == ""
