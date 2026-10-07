"""Integration tests: employer profile pages through the Django test client (#12).

Each test goes through the whole stack: middleware, URL, view, forms, template and database.
Acceptance criteria AC1-AC10 from docs/specs/employer-profile.md (AC9, the menu link, is
checked in test_onboarding_views.py; AC11, base.html, for all templates in tests/).
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

from accounts.models import EmployerProfile

pytestmark = [pytest.mark.django_db, pytest.mark.story(12)]

User = get_user_model()


@pytest.fixture
def employer():
    """An employer who has not filled in the profile yet."""
    return User.objects.create_user(
        email="anna@example.com", password="x", role="employer"
    )


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the employer."""
    client.force_login(employer)
    return client


def make_profile(user, **fields):
    """Save a filled profile for `user`; `fields` replace the defaults."""
    values = {
        "company_name": "Huber Fenster GmbH",
        "trades": ["window_fitting", "drywall"],
        **fields,
    }
    return EmployerProfile.objects.create(user=user, **values)


def form_data(**fields):
    """What the browser sends for a correctly filled profile form."""
    return {
        "name": "Anna Huber",
        "phone": "+49 170 7654321",
        "company_name": "Huber Fenster GmbH",
        "trades": ["window_fitting", "drywall"],
        **fields,
    }


# AC1: no profile yet


def test_profile_page_without_profile_opens_the_form(employer_client):
    """An employer without a profile is sent from the profile page to the form.

    1. Log in as an employer without a profile
    2. Open "My company"
    3. Expect: redirect to the profile form
    """
    response = employer_client.get(reverse("employer_profile"))

    assertRedirects(response, reverse("employer_profile_edit"))


def test_empty_form_for_a_new_employer(employer_client):
    """The form for a new employer shows all fields and extends the site layout.

    1. Log in as an employer without a profile
    2. Open the profile form
    3. Expect: status 200, the site layout, a field for each profile item,
       trade checkboxes and the hint for private persons
    """
    response = employer_client.get(reverse("employer_profile_edit"))

    assert response.status_code == 200
    assertTemplateUsed(response, "base.html")
    for field in ("name", "phone", "company_name", "trades"):
        assertContains(response, f'name="{field}"')
    assertContains(response, 'type="checkbox"')
    assertContains(response, "Private person")
    assertContains(response, "Leave empty if you hire as a private person.")


# AC2: first save


def test_saving_the_form_creates_the_profile(employer_client, employer):
    """Filling in the form creates the profile and saves name and phone.

    1. Log in as an employer without a profile
    2. Send the form: Anna Huber, Huber Fenster GmbH, window fitting + drywall
    3. Expect: redirect to "My company" with the message "Profile saved."
    4. Expect: one profile with these values; name and phone saved on the user
    """
    response = employer_client.post(
        reverse("employer_profile_edit"), form_data(), follow=True
    )

    assertRedirects(response, reverse("employer_profile"))
    assertContains(response, "Profile saved.")
    profile = EmployerProfile.objects.get()
    assert profile.user == employer
    assert profile.company_name == "Huber Fenster GmbH"
    assert profile.trades == ["window_fitting", "drywall"]
    employer.refresh_from_db()
    assert employer.name == "Anna Huber"
    assert employer.phone == "+49 170 7654321"


# AC3: editing


def test_form_shows_the_saved_values(employer_client, employer):
    """The form of an employer with a profile is filled with the saved values.

    1. Log in as an employer with a profile (Huber Fenster GmbH, window fitting + drywall)
    2. Open the profile form
    3. Expect: the company name, window fitting and drywall ticked, painting not
    """
    profile = make_profile(employer)

    response = employer_client.get(reverse("employer_profile_edit"))

    assert response.context["profile_form"].instance == profile
    assertContains(response, 'value="Huber Fenster GmbH"')
    assertContains(
        response, 'value="window_fitting" class="checkbox" id="id_trades_0" checked'
    )
    assertContains(
        response, 'value="drywall" class="checkbox" id="id_trades_1" checked'
    )
    assertNotContains(
        response, 'value="painting" class="checkbox" id="id_trades_3" checked'
    )


def test_editing_changes_the_same_profile(employer_client, employer):
    """Saving the form again changes the existing profile, it does not add one.

    1. Log in as an employer with a profile (Huber Fenster GmbH)
    2. Send the form with no company and only "private person"
    3. Expect: still exactly one profile, now without company and with "private person"
    """
    profile = make_profile(employer)

    employer_client.post(
        reverse("employer_profile_edit"),
        form_data(company_name="", trades=["private_person"]),
    )

    assert EmployerProfile.objects.count() == 1
    profile.refresh_from_db()
    assert profile.company_name == ""
    assert profile.trades == ["private_person"]


# AC4, AC5: wrong input


def test_all_errors_are_shown_at_once(employer_client, employer):
    """Errors in both forms are shown together, and nothing is saved.

    1. Log in as an employer without a profile
    2. Send the form with an empty name and no trade
    3. Expect: the form again with an error at both fields
    4. Expect: no profile, the name is still empty
    """
    response = employer_client.post(
        reverse("employer_profile_edit"), form_data(name="", trades=[])
    )

    assert response.status_code == 200
    assert "name" in response.context["user_form"].errors
    assert "trades" in response.context["profile_form"].errors
    assert EmployerProfile.objects.count() == 0
    employer.refresh_from_db()
    assert employer.name == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [("trades", ["astronaut"]), ("company_name", "x" * 151)],
)
def test_wrong_value_is_not_saved(employer_client, field, value):
    """A single wrong value keeps the whole form from being saved.

    1. Log in as an employer without a profile
    2. Send the form with an unknown trade / a company name of 151 characters
    3. Expect: the form again with an error at that field; no profile saved
    """
    response = employer_client.post(
        reverse("employer_profile_edit"), form_data(**{field: value})
    )

    assert response.status_code == 200
    assert field in response.context["profile_form"].errors
    assert EmployerProfile.objects.count() == 0


def test_private_person_without_company_and_phone(employer_client, employer):
    """A private person can save the profile with only a name and a trade.

    1. Log in as an employer without a profile
    2. Send the form with no company, no phone and the trade "private person"
    3. Expect: redirect to "My company"; the profile is saved
    """
    response = employer_client.post(
        reverse("employer_profile_edit"),
        form_data(company_name="", phone="", trades=["private_person"]),
    )

    assertRedirects(response, reverse("employer_profile"))
    assert EmployerProfile.objects.filter(user=employer).exists()


# AC6: profile page


def test_profile_page_shows_all_fields(employer_client, employer):
    """The profile page shows every field in readable words.

    1. Log in as an employer with name, phone and a profile (Huber Fenster GmbH)
    2. Open "My company"
    3. Expect: company, contact person, trade names, email, phone
       and an "Edit profile" link
    """
    employer.name = "Anna Huber"
    employer.phone = "+49 170 7654321"
    employer.save()
    make_profile(employer)

    response = employer_client.get(reverse("employer_profile"))

    assert response.status_code == 200
    assertTemplateUsed(response, "base.html")
    for text in (
        "Huber Fenster GmbH",
        "Anna Huber",
        "Window fitting",
        "Drywall",
        "anna@example.com",
        "+49 170 7654321",
    ):
        assertContains(response, text)
    assertContains(response, f'href="{reverse("employer_profile_edit")}"')


def test_profile_page_of_a_private_person(employer_client, employer):
    """Without a company there is no empty "Company" row, and no phone shows "not given".

    1. Log in as an employer named Anna Huber, no company, no phone
    2. Open "My company"
    3. Expect: the name, no "Company" row, "not given" next to the phone
    """
    employer.name = "Anna Huber"
    employer.save()
    make_profile(employer, company_name="", trades=["private_person"])

    response = employer_client.get(reverse("employer_profile"))

    assertContains(response, "Anna Huber")
    assertNotContains(response, ">Company</dt>")
    assertContains(response, "not given")


def test_profile_card_has_no_contact_details(employer):
    """The card workers will see (#19) shows no phone or email.

    1. Render the profile card for an employer with a phone
    2. Expect: company and name are there, the phone and the email are not
    """
    # Contacts are revealed only after an application is accepted (#25).
    employer.name = "Anna Huber"
    employer.phone = "+49 170 7654321"
    employer.save()
    profile = make_profile(employer)

    html = render_to_string(
        "accounts/_employer_profile_card.html", {"profile": profile}
    )

    assert "Huber Fenster GmbH" in html
    assert "Anna Huber" in html
    assert "+49 170 7654321" not in html
    assert "anna@example.com" not in html


# AC7: who may open the pages


@pytest.mark.parametrize("url_name", ["employer_profile", "employer_profile_edit"])
def test_worker_gets_403(client, url_name):
    """A worker cannot open the employer profile pages.

    1. Log in as a worker
    2. Open "My company" / the form of an employer
    3. Expect: 403 Forbidden
    """
    worker = User.objects.create_user(
        email="ivan@example.com", password="x", role="worker"
    )
    client.force_login(worker)

    assert client.get(reverse(url_name)).status_code == 403


def test_worker_cannot_create_an_employer_profile(client):
    """Sending the employer form as a worker saves nothing.

    1. Log in as a worker
    2. Send a filled employer profile form
    3. Expect: 403 Forbidden; no profile saved
    """
    worker = User.objects.create_user(
        email="ivan@example.com", password="x", role="worker"
    )
    client.force_login(worker)

    response = client.post(reverse("employer_profile_edit"), form_data())

    assert response.status_code == 403
    assert EmployerProfile.objects.count() == 0


@pytest.mark.parametrize("url_name", ["employer_profile", "employer_profile_edit"])
def test_admin_without_role_gets_403(client, url_name):
    """An admin has no role, so the employer pages are closed to them too.

    1. Log in as a staff user without a role
    2. Open "My company" / the form of an employer
    3. Expect: 403 Forbidden (admins edit profiles in /admin/)
    """
    admin = User.objects.create_superuser(email="admin@example.com", password="x")
    client.force_login(admin)

    assert client.get(reverse(url_name)).status_code == 403


@pytest.mark.parametrize("url_name", ["employer_profile", "employer_profile_edit"])
def test_guest_must_log_in(client, url_name):
    """A guest is sent to login, and back to the page afterwards.

    1. Without logging in, open "My company" / the profile form
    2. Expect: redirect to login with ?next= that page
    """
    url = reverse(url_name)

    response = client.get(url)

    assertRedirects(response, f"{reverse('login')}?next={url}")


# AC8: only one's own profile


def test_employer_cannot_save_a_profile_for_someone_else(employer_client, employer):
    """A "user" field sent with the form is ignored.

    1. Another employer, Max, exists without a profile
    2. Log in as Anna and send the form with user = Max's id (e.g. with curl)
    3. Expect: the profile is Anna's; Max still has none
    """
    max_ = User.objects.create_user(
        email="max@example.com", password="x", role="employer"
    )

    employer_client.post(reverse("employer_profile_edit"), form_data(user=max_.pk))

    assert EmployerProfile.objects.get().user == employer
    assert not EmployerProfile.objects.filter(user=max_).exists()


@pytest.mark.story(88)
def test_profile_form_needs_the_csrf_token_from_the_page(employer):
    """The profile form only works with the CSRF token from our own page.

    1. Log in with a client that checks CSRF like a real browser
    2. Send a filled profile form without the token
    3. Expect: 403 Forbidden; no profile saved
    """
    # Another site could otherwise change the profile of a logged-in visitor.
    client = Client(enforce_csrf_checks=True)
    client.force_login(employer)

    response = client.post(reverse("employer_profile_edit"), form_data())

    assert response.status_code == 403
    assert EmployerProfile.objects.count() == 0


# AC10: admin


def test_admin_shows_the_profile_on_the_employer_page(client, employer):
    """The admin page of an employer shows their profile with trade checkboxes.

    1. An employer with a profile exists
    2. Log in as admin and open that employer in /admin/
    3. Expect: the "Employer profile" section with trade checkboxes, no worker profile
    """
    make_profile(employer)
    client.force_login(
        User.objects.create_superuser(email="admin@example.com", password="x")
    )

    response = client.get(reverse("admin:accounts_user_change", args=[employer.pk]))

    assertContains(response, "Employer profile")
    assertContains(response, 'name="employer_profile-0-trades"')
    assertContains(response, 'type="checkbox"')
    assertNotContains(response, "worker_profile-0-skills")


def test_admin_shows_no_employer_profile_for_a_worker(client):
    """A worker's admin page has no employer profile section.

    1. A worker exists
    2. Log in as admin and open that worker in /admin/
    3. Expect: no employer profile fields
    """
    worker = User.objects.create_user(
        email="ivan@example.com", password="x", role="worker"
    )
    client.force_login(
        User.objects.create_superuser(email="admin@example.com", password="x")
    )

    response = client.get(reverse("admin:accounts_user_change", args=[worker.pk]))

    assert response.status_code == 200
    assertNotContains(response, "employer_profile-0-trades")
