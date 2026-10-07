"""Integration tests: role choice and onboarding through the Django test client (#10).

Each test goes through the whole stack: middleware, URL, view, form, template and database.
Acceptance criteria AC1-AC9 from docs/specs/onboarding.md.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from pytest_django.asserts import (
    assertContains,
    assertNotContains,
    assertRedirects,
    assertTemplateUsed,
)

pytestmark = [pytest.mark.django_db, pytest.mark.story(10)]

User = get_user_model()

PASSWORD = "Gerüst-2026-Munich"


@pytest.fixture
def newbie():
    """A registered user who has not chosen a role yet."""
    return User.objects.create_user(email="newbie@example.com", password=PASSWORD)


def user_with_role(role):
    """A user who finished onboarding as worker or employer."""
    return User.objects.create_user(
        email=f"{role}@example.com", password=PASSWORD, role=role
    )


# AC1: after signup


def test_signup_leads_to_the_role_choice(client):
    """A new user goes from signup straight to the role choice.

    1. Sign up as ben@example.com
    2. Expect: redirect to the role choice page
    3. Expect: the page asks "Who are you?" and shows the welcome message
    """
    response = client.post(
        reverse("register"),
        {"email": "ben@example.com", "password1": PASSWORD, "password2": PASSWORD},
        follow=True,
    )

    assertRedirects(response, reverse("role_select"))
    assertContains(response, "Who are you?")
    assertContains(response, "Welcome to BauHelfer!")


# AC2, AC3: a user without a role cannot skip the choice


@pytest.mark.parametrize("url_name", ["home", "worker_profile_edit", "password_reset"])
def test_user_without_role_is_sent_back_to_the_role_choice(client, newbie, url_name):
    """A user without a role cannot open other pages.

    1. Log in as a user without a role
    2. Open the home page / a profile page / password reset
    3. Expect: redirect to the role choice page
    """
    client.force_login(newbie)

    response = client.get(reverse(url_name))

    assertRedirects(response, reverse("role_select"))


def test_role_choice_page_shows_two_choices(client, newbie):
    """The role choice page shows both choices as buttons in one form.

    1. Log in as a user without a role
    2. Open the role choice page
    3. Expect: status 200, the site layout and two submit buttons with role values
    """
    client.force_login(newbie)

    response = client.get(reverse("role_select"))

    assert response.status_code == 200
    assertTemplateUsed(response, "base.html")
    assertContains(response, 'name="role" value="employer"')
    assertContains(response, 'name="role" value="worker"')
    assertContains(response, "I need workers")
    assertContains(response, "I am looking for work")


def test_user_without_role_can_log_out(client, newbie):
    """Logout still works before a role is chosen.

    1. Log in as a user without a role
    2. Press "Log out"
    3. Expect: redirect to home, not logged in
    """
    client.force_login(newbie)

    response = client.post(reverse("logout"))

    assertRedirects(response, reverse("home"))
    assert "_auth_user_id" not in client.session


# AC4, AC5: admins and guests are not affected


def test_admin_without_role_can_use_the_site_and_the_admin(client):
    """An admin has no role and is never sent to the role choice.

    1. Log in as a staff user without a role
    2. Open the home page and /admin/
    3. Expect: both open with status 200
    """
    admin = User.objects.create_superuser(email="boss@example.com", password=PASSWORD)
    client.force_login(admin)

    assert client.get(reverse("home")).status_code == 200
    assert client.get(reverse("admin:index")).status_code == 200


def test_guest_sees_the_home_page(client):
    """A guest is not sent to the role choice.

    1. Open the home page without logging in
    2. Expect: status 200
    """
    assert client.get(reverse("home")).status_code == 200


@pytest.mark.parametrize(
    "url_name", ["role_select", "worker_profile_edit", "employer_profile_edit"]
)
def test_guest_must_log_in_for_onboarding_pages(client, url_name):
    """The role choice and profile pages need a login.

    1. Without logging in, open the role choice / a profile page
    2. Expect: redirect to login, coming back to that page afterwards
    """
    url = reverse(url_name)

    response = client.get(url)

    assertRedirects(response, f"{reverse('login')}?next={url}")


# AC6, AC7: choosing a role


@pytest.mark.parametrize(
    ("role", "url_name"),
    [("worker", "worker_profile_edit"), ("employer", "employer_profile_edit")],
)
def test_choosing_a_role_saves_it_and_opens_the_profile(client, newbie, role, url_name):
    """Choosing a role saves it and opens the profile form of that role.

    1. Log in as a user without a role
    2. Press "I am looking for work" / "I need workers"
    3. Expect: redirect to the worker / employer profile form
    4. Expect: the role is saved in the database
    """
    client.force_login(newbie)

    response = client.post(reverse("role_select"), {"role": role})

    assertRedirects(response, reverse(url_name))
    newbie.refresh_from_db()
    assert newbie.role == role


def test_choosing_an_unknown_role_shows_an_error(client, newbie):
    """A made-up role value is rejected and nothing is saved.

    1. Log in as a user without a role
    2. Send the role form with role = "admin" (not one of the buttons)
    3. Expect: the page again with an error; the role is still empty
    """
    client.force_login(newbie)

    response = client.post(reverse("role_select"), {"role": "admin"})

    assert response.status_code == 200
    assertContains(response, "Select a valid choice.")
    newbie.refresh_from_db()
    assert newbie.role == ""


@pytest.mark.story(88)
def test_role_choice_needs_the_csrf_token_from_the_page(newbie):
    """The role form only works with the CSRF token from our own page.

    1. Log in with a client that checks CSRF like a real browser
    2. Send the role form without the token
    3. Expect: 403 Forbidden; the role is still empty
    """
    # Another site could otherwise choose a role for a logged-in visitor.
    client = Client(enforce_csrf_checks=True)
    client.force_login(newbie)

    response = client.post(reverse("role_select"), {"role": "worker"})

    assert response.status_code == 403
    newbie.refresh_from_db()
    assert newbie.role == ""


# AC8: the role is chosen once


@pytest.mark.parametrize(
    ("role", "url_name"),
    [("worker", "worker_profile_edit"), ("employer", "employer_profile_edit")],
)
def test_user_with_a_role_skips_the_role_choice(client, role, url_name):
    """A user who has a role is sent from the role choice to their profile.

    1. Log in as a worker / employer
    2. Open the role choice page
    3. Expect: redirect to the worker / employer profile form
    """
    client.force_login(user_with_role(role))

    response = client.get(reverse("role_select"))

    assertRedirects(response, reverse(url_name))


def test_role_cannot_be_changed_by_posting_the_form_again(client):
    """A worker cannot become an employer by sending the role form.

    1. Log in as a worker
    2. Send the role form with role = employer (e.g. with curl)
    3. Expect: redirect to the worker profile; the role is still worker
    """
    worker = user_with_role("worker")
    client.force_login(worker)

    response = client.post(reverse("role_select"), {"role": "employer"})

    assertRedirects(response, reverse("worker_profile_edit"))
    worker.refresh_from_db()
    assert worker.role == "worker"


# AC9: navigation by role


@pytest.mark.parametrize(
    ("role", "shown", "hidden", "url_name"),
    [
        # Since #11 the worker's link opens the profile page, not the form.
        ("worker", "My profile", "My company", "worker_profile"),
        ("employer", "My company", "My profile", "employer_profile_edit"),
    ],
)
def test_menu_shows_the_profile_link_of_the_role(client, role, shown, hidden, url_name):
    """The menu links to the profile of the user's own role only.

    1. Log in as a worker / employer
    2. Open the home page
    3. Expect: "My profile" / "My company" linking to that profile, not the other one
    """
    client.force_login(user_with_role(role))

    response = client.get(reverse("home"))

    assertContains(response, shown)
    assertContains(response, f'href="{reverse(url_name)}"')
    assertNotContains(response, hidden)


def test_menu_has_no_role_links_before_the_role_is_chosen(client, newbie):
    """Before choosing a role the menu offers only logout.

    1. Log in as a user without a role
    2. Open the role choice page
    3. Expect: "Log out" in the menu, no "My profile" or "My company"
    """
    client.force_login(newbie)

    response = client.get(reverse("role_select"))

    assertContains(response, "Log out")
    assertNotContains(response, "My profile")
    assertNotContains(response, "My company")


def test_menu_logout_buttons_send_the_post_form(client):
    """Both "Log out" buttons (phone menu and desktop row) send the logout POST form.

    1. Log in as a worker and open the home page
    2. Expect: one POST form to the logout URL with a CSRF token
    3. Expect: two "Log out" buttons that submit that form
    """
    client.force_login(user_with_role("worker"))

    response = client.get(reverse("home"))

    assertContains(
        response,
        f'<form id="logout-form" method="post" action="{reverse("logout")}"',
        count=1,
    )
    assertContains(response, 'name="csrfmiddlewaretoken"')
    assertContains(response, 'type="submit" form="logout-form"', count=2)
