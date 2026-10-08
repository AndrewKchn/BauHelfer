"""Integration tests: worker profile pages through the Django test client (#11).

Each test goes through the whole stack: middleware, URL, view, forms, template and database.
Acceptance criteria AC1-AC12 from docs/specs/worker-profile.md (AC11, the menu link, is
checked in test_onboarding_views.py).
"""

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import Client
from django.urls import reverse
from pytest_django.asserts import (
    assertContains,
    assertNotContains,
    assertRedirects,
    assertTemplateUsed,
)

from accounts.models import WorkerProfile

pytestmark = [pytest.mark.django_db, pytest.mark.story(11)]

User = get_user_model()


@pytest.fixture
def worker():
    """A worker who has not filled in the profile yet."""
    return User.objects.create_user(
        email="ivan@example.com", password="x", role="worker"
    )


@pytest.fixture
def worker_client(client, worker):
    """A browser logged in as the worker."""
    client.force_login(worker)
    return client


def make_profile(user, **fields):
    """Save a filled profile for `user`; `fields` replace the defaults."""
    values = {
        "team_size": 3,
        "skills": ["demolition", "carrying"],
        "languages": ["ru", "de"],
        "legal_status": "gewerbe",
        **fields,
    }
    return WorkerProfile.objects.create(user=user, **values)


def form_data(**fields):
    """What the browser sends for a correctly filled profile form."""
    return {
        "name": "Ivan Petrov",
        "phone": "+49 170 1234567",
        "work_permit": "on",  # required since #13
        "team_size": "3",
        "skills": ["demolition", "carrying"],
        "languages": ["ru", "de"],
        "legal_status": "gewerbe",
        **fields,
    }


# AC1: no profile yet


def test_profile_page_without_profile_opens_the_form(worker_client):
    """A worker without a profile is sent from the profile page to the form.

    1. Log in as a worker without a profile
    2. Open "My profile"
    3. Expect: redirect to the profile form
    """
    response = worker_client.get(reverse("worker_profile"))

    assertRedirects(response, reverse("worker_profile_edit"))


def test_empty_form_for_a_new_worker(worker_client):
    """The form for a new worker shows all fields and extends the site layout.

    1. Log in as a worker without a profile
    2. Open the profile form
    3. Expect: status 200, the site layout, a field for each profile item
    """
    response = worker_client.get(reverse("worker_profile_edit"))

    assert response.status_code == 200
    assertTemplateUsed(response, "base.html")
    for field in ("name", "phone", "team_size", "skills", "languages", "legal_status"):
        assertContains(response, f'name="{field}"')
    assertContains(response, "Bricklayer&#x27;s helper")
    assertContains(response, 'type="checkbox"')
    assertContains(response, 'type="radio"')


# AC2: first save


def test_saving_the_form_creates_the_profile(worker_client, worker):
    """Filling in the form creates the profile and saves name and phone.

    1. Log in as a worker without a profile
    2. Send the form: Ivan Petrov, crew of 3, demolition + carrying, ru + de, Gewerbe
    3. Expect: redirect to "My profile" with the message "Profile saved."
    4. Expect: one profile with these values; name and phone saved on the user
    """
    response = worker_client.post(
        reverse("worker_profile_edit"), form_data(), follow=True
    )

    assertRedirects(response, reverse("worker_profile"))
    assertContains(response, "Profile saved.")
    profile = WorkerProfile.objects.get()
    assert profile.user == worker
    assert profile.team_size == 3
    assert profile.skills == ["demolition", "carrying"]
    assert profile.languages == ["ru", "de"]
    assert profile.legal_status == "gewerbe"
    worker.refresh_from_db()
    assert worker.name == "Ivan Petrov"
    assert worker.phone == "+49 170 1234567"


# AC3: editing


def test_form_shows_the_saved_values(worker_client, worker):
    """The form of a worker with a profile is filled with the saved values.

    1. Log in as a worker with a profile (crew of 3, demolition + carrying)
    2. Open the profile form
    3. Expect: team size 3, demolition and carrying ticked, painting not
    """
    profile = make_profile(worker)

    response = worker_client.get(reverse("worker_profile_edit"))

    assert response.context["profile_form"].instance == profile
    assertContains(response, 'value="3"')
    assertContains(
        response, 'value="demolition" class="checkbox" id="id_skills_0" checked'
    )
    assertContains(
        response, 'value="carrying" class="checkbox" id="id_skills_2" checked'
    )
    assertNotContains(
        response, 'value="painting" class="checkbox" id="id_skills_9" checked'
    )


def test_editing_changes_the_same_profile(worker_client, worker):
    """Saving the form again changes the existing profile, it does not add one.

    1. Log in as a worker with a profile (crew of 3)
    2. Send the form with team size 1 and only painting
    3. Expect: still exactly one profile, now with team size 1 and painting
    """
    profile = make_profile(worker)

    worker_client.post(
        reverse("worker_profile_edit"), form_data(team_size="1", skills=["painting"])
    )

    assert WorkerProfile.objects.count() == 1
    profile.refresh_from_db()
    assert profile.team_size == 1
    assert profile.skills == ["painting"]


# AC4-AC7: wrong input


def test_all_errors_are_shown_at_once(worker_client, worker):
    """Errors in both forms are shown together, and nothing is saved.

    1. Log in as a worker without a profile
    2. Send the form with an empty name, team size 0 and no skills
    3. Expect: the form again with an error at each of these fields
    4. Expect: no profile, the name is still empty
    """
    response = worker_client.post(
        reverse("worker_profile_edit"), form_data(name="", team_size="0", skills=[])
    )

    assert response.status_code == 200
    assert "name" in response.context["user_form"].errors
    assert {"team_size", "skills"} <= set(response.context["profile_form"].errors)
    assertContains(response, "Ensure this value is greater than or equal to 1.")
    assert WorkerProfile.objects.count() == 0
    worker.refresh_from_db()
    assert worker.name == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("team_size", "11"),
        ("languages", []),
        ("legal_status", "freelancer"),
        ("skills", ["juggling"]),
    ],
)
def test_wrong_value_is_not_saved(worker_client, field, value):
    """A single wrong value keeps the whole form from being saved.

    1. Log in as a worker without a profile
    2. Send the form with team size 11 / no language / an unknown status / skill
    3. Expect: the form again with an error at that field; no profile saved
    """
    response = worker_client.post(
        reverse("worker_profile_edit"), form_data(**{field: value})
    )

    assert response.status_code == 200
    assert field in response.context["profile_form"].errors
    assert WorkerProfile.objects.count() == 0


def test_phone_may_stay_empty(worker_client, worker):
    """A worker can save the profile without a phone number.

    1. Log in as a worker without a profile
    2. Send the form with an empty phone
    3. Expect: redirect to "My profile"; the profile is saved
    """
    response = worker_client.post(reverse("worker_profile_edit"), form_data(phone=""))

    assertRedirects(response, reverse("worker_profile"))
    assert WorkerProfile.objects.filter(user=worker).exists()


# AC8: profile page


def test_profile_page_shows_all_fields(worker_client, worker):
    """The profile page shows every field in readable words.

    1. Log in as a worker with name, phone and a profile (crew of 3, Gewerbe)
    2. Open "My profile"
    3. Expect: name, "Crew of 3", skill and language names, legal status, email,
       phone and an "Edit profile" link
    """
    worker.name = "Ivan Petrov"
    worker.phone = "+49 170 1234567"
    worker.save()
    make_profile(worker)

    response = worker_client.get(reverse("worker_profile"))

    assert response.status_code == 200
    assertTemplateUsed(response, "base.html")
    for text in (
        "Ivan Petrov",
        "Crew of 3",
        "Demolition",
        "Carrying materials",
        "Russian",
        "German",
        "Self-employed (Gewerbe)",
        "ivan@example.com",
        "+49 170 1234567",
    ):
        assertContains(response, text)
    assertContains(response, f'href="{reverse("worker_profile_edit")}"')


def test_profile_page_without_phone(worker_client, worker):
    """An empty phone is shown as "not given", not as a blank.

    1. Log in as a worker with a profile and no phone
    2. Open "My profile"
    3. Expect: "not given" next to the phone
    """
    make_profile(worker)

    response = worker_client.get(reverse("worker_profile"))

    assertContains(response, "not given")


def test_profile_card_has_no_contact_details(worker):
    """The card employers will see (#23) shows no phone or email.

    1. Render the profile card for a worker with a phone
    2. Expect: the name is there, the phone and the email are not
    """
    # Contacts are revealed only after an application is accepted (#25).
    worker.name = "Ivan Petrov"
    worker.phone = "+49 170 1234567"
    worker.save()
    profile = make_profile(worker)

    html = render_to_string("accounts/_worker_profile_card.html", {"profile": profile})

    assert "Ivan Petrov" in html
    assert "+49 170 1234567" not in html
    assert "ivan@example.com" not in html


# AC9: who may open the pages


@pytest.mark.parametrize("url_name", ["worker_profile", "worker_profile_edit"])
def test_employer_gets_403(client, url_name):
    """An employer cannot open the worker profile pages.

    1. Log in as an employer
    2. Open "My profile" / the form of a worker
    3. Expect: 403 Forbidden
    """
    employer = User.objects.create_user(
        email="boss@example.com", password="x", role="employer"
    )
    client.force_login(employer)

    assert client.get(reverse(url_name)).status_code == 403


def test_employer_cannot_create_a_worker_profile(client):
    """Sending the worker form as an employer saves nothing.

    1. Log in as an employer
    2. Send a filled worker profile form
    3. Expect: 403 Forbidden; no profile saved
    """
    employer = User.objects.create_user(
        email="boss@example.com", password="x", role="employer"
    )
    client.force_login(employer)

    response = client.post(reverse("worker_profile_edit"), form_data())

    assert response.status_code == 403
    assert WorkerProfile.objects.count() == 0


@pytest.mark.parametrize("url_name", ["worker_profile", "worker_profile_edit"])
def test_admin_without_role_gets_403(client, url_name):
    """An admin has no role, so the worker pages are closed to them too.

    1. Log in as a staff user without a role
    2. Open "My profile" / the form of a worker
    3. Expect: 403 Forbidden (admins edit profiles in /admin/)
    """
    admin = User.objects.create_superuser(email="admin@example.com", password="x")
    client.force_login(admin)

    assert client.get(reverse(url_name)).status_code == 403


@pytest.mark.parametrize("url_name", ["worker_profile", "worker_profile_edit"])
def test_guest_must_log_in(client, url_name):
    """A guest is sent to login, and back to the page afterwards.

    1. Without logging in, open "My profile" / the profile form
    2. Expect: redirect to login with ?next= that page
    """
    url = reverse(url_name)

    response = client.get(url)

    assertRedirects(response, f"{reverse('login')}?next={url}")


# AC10: only one's own profile


def test_worker_cannot_save_a_profile_for_someone_else(worker_client, worker):
    """A "user" field sent with the form is ignored.

    1. Another worker, Olga, exists without a profile
    2. Log in as Ivan and send the form with user = Olga's id (e.g. with curl)
    3. Expect: the profile is Ivan's; Olga still has none
    """
    olga = User.objects.create_user(
        email="olga@example.com", password="x", role="worker"
    )

    worker_client.post(reverse("worker_profile_edit"), form_data(user=olga.pk))

    assert WorkerProfile.objects.get().user == worker
    assert not WorkerProfile.objects.filter(user=olga).exists()


@pytest.mark.story(88)
def test_profile_form_needs_the_csrf_token_from_the_page(worker):
    """The profile form only works with the CSRF token from our own page.

    1. Log in with a client that checks CSRF like a real browser
    2. Send a filled profile form without the token
    3. Expect: 403 Forbidden; no profile saved
    """
    # Another site could otherwise change the profile of a logged-in visitor.
    client = Client(enforce_csrf_checks=True)
    client.force_login(worker)

    response = client.post(reverse("worker_profile_edit"), form_data())

    assert response.status_code == 403
    assert WorkerProfile.objects.count() == 0


# AC12: admin


def test_admin_shows_the_profile_on_the_worker_page(client, worker):
    """The admin page of a worker shows their profile with checkboxes.

    1. A worker with a profile exists
    2. Log in as admin and open that worker in /admin/
    3. Expect: the "Worker profile" section with skill checkboxes
    """
    make_profile(worker)
    client.force_login(
        User.objects.create_superuser(email="admin@example.com", password="x")
    )

    response = client.get(reverse("admin:accounts_user_change", args=[worker.pk]))

    assertContains(response, "Worker profile")
    assertContains(response, 'name="worker_profile-0-skills"')
    assertContains(response, 'type="checkbox"')


def test_admin_shows_no_worker_profile_for_an_employer(client):
    """An employer's admin page has no worker profile section.

    1. An employer exists
    2. Log in as admin and open that employer in /admin/
    3. Expect: no worker profile fields
    """
    employer = User.objects.create_user(
        email="boss@example.com", password="x", role="employer"
    )
    client.force_login(
        User.objects.create_superuser(email="admin@example.com", password="x")
    )

    response = client.get(reverse("admin:accounts_user_change", args=[employer.pk]))

    assert response.status_code == 200
    assertNotContains(response, "worker_profile-0-skills")
