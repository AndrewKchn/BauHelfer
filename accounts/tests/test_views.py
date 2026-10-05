"""Integration tests: account pages through the Django test client (view + form + DB) (#9)."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from pytest_django.asserts import assertContains, assertRedirects, assertTemplateUsed

pytestmark = [pytest.mark.django_db, pytest.mark.story(9)]

User = get_user_model()

PASSWORD = "Gerüst-2026-Munich"
NEW_PASSWORD = "Neues-Passwort-2027"


@pytest.fixture
def user():
    """An existing account to log in with."""
    return User.objects.create_user(email="anna@example.com", password=PASSWORD)


def is_logged_in(client):
    """True if the test client's session belongs to a logged-in user."""
    return "_auth_user_id" in client.session


@pytest.mark.parametrize(
    "name", ["register", "login", "password_reset", "password_reset_done"]
)
def test_account_pages_open_and_use_the_base_layout(client, name):
    """Signup, login and password reset pages open in the site layout.

    1. Open the page
    2. Expect: status 200 and the shared layout base.html
    """
    response = client.get(reverse(name))

    assert response.status_code == 200
    assertTemplateUsed(response, "base.html")


# Registration


def test_register_creates_user_logs_in_and_welcomes(client):
    """After signup the user is logged in and welcomed on the home page.

    1. Sign up as Ben@Example.com
    2. Expect: redirect to home; ben@example.com is saved and logged in
    3. Expect: "Welcome to BauHelfer!" and the email in the header
    """
    response = client.post(
        reverse("register"),
        {"email": "Ben@Example.com", "password1": PASSWORD, "password2": PASSWORD},
        follow=True,
    )

    assertRedirects(response, reverse("home"))
    assert User.objects.filter(email="ben@example.com").exists()
    assert is_logged_in(client)
    assertContains(response, "Welcome to BauHelfer!")
    assertContains(response, "ben@example.com")  # shown in the header


def test_register_with_errors_shows_them_and_saves_nothing(client):
    """Signup with mistakes shows the errors and saves nothing.

    1. Sign up with "anna@" and two different passwords
    2. Expect: the page again with both errors and red borders
    3. Expect: no user saved, nobody logged in
    """
    response = client.post(
        reverse("register"),
        {"email": "anna@", "password1": PASSWORD, "password2": "something-else"},
    )

    assert response.status_code == 200
    assert not User.objects.exists()
    assert not is_logged_in(client)
    assertContains(response, "Enter a valid email address.")
    assertContains(response, "The two password fields didn")  # apostrophe is escaped
    assertContains(response, "input-error")


def test_register_with_taken_email_shows_an_error(client, user):
    """Signup with a registered email shows an error, no new account.

    1. anna@example.com exists
    2. Sign up as ANNA@example.com
    3. Expect: "User with this Email already exists.", still one account
    """
    response = client.post(
        reverse("register"),
        {"email": "ANNA@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )

    assert response.status_code == 200
    assertContains(response, "User with this Email already exists.")
    assert User.objects.count() == 1


def test_logged_in_user_is_sent_away_from_register(client, user):
    """A logged-in user who opens signup goes to the home page.

    1. Log in
    2. Open the signup page
    3. Expect: redirect to home
    """
    client.force_login(user)

    response = client.get(reverse("register"))

    assertRedirects(response, reverse("home"))


# Login and logout


def test_header_shows_login_and_register_to_guests(client):
    """A guest sees Log in and Register in the header, not Log out.

    1. Open the home page without logging in
    2. Expect: links to login and register, no "Log out"
    """
    response = client.get(reverse("home"))

    assertContains(response, f'href="{reverse("login")}"')
    assertContains(response, f'href="{reverse("register")}"')
    assert "Log out" not in response.text


def test_login_with_email_in_any_case(client, user):
    """Login works with the email in any capitals.

    1. anna@example.com exists
    2. Log in as ANNA@Example.com
    3. Expect: redirect to home, logged in, "Log out" in the header
    """
    response = client.post(
        reverse("login"),
        {"username": "ANNA@Example.com", "password": PASSWORD},
        follow=True,
    )

    assertRedirects(response, reverse("home"))
    assert is_logged_in(client)
    assertContains(response, "Log out")


def test_login_with_wrong_password_shows_an_error(client, user):
    """Wrong password: the user sees an error and stays logged out.

    1. anna@example.com exists
    2. Log in with that email and a wrong password
    3. Expect: "Wrong email or password." in a red alert box
    4. Expect: the user is not logged in
    """
    response = client.post(
        reverse("login"), {"username": "anna@example.com", "password": "wrong"}
    )

    assert response.status_code == 200
    assert not is_logged_in(client)
    assertContains(response, "Wrong email or password.")
    assert "Note that both fields may be case-sensitive" not in response.text
    assertContains(response, 'role="alert"')


def test_login_goes_back_to_the_page_that_asked_for_it(client, user):
    """After login the user returns to the page that asked for it.

    1. Log in from /accounts/login/?next=/admin/
    2. Expect: redirect to /admin/
    """
    response = client.post(
        f"{reverse('login')}?next=/admin/",
        {"username": "anna@example.com", "password": PASSWORD, "next": "/admin/"},
    )

    assert response.status_code == 302
    assert response.url == "/admin/"


def test_logged_in_user_is_sent_away_from_login(client, user):
    """A logged-in user who opens the login page goes to the home page.

    1. Log in
    2. Open the login page
    3. Expect: redirect to home
    """
    client.force_login(user)

    response = client.get(reverse("login"))

    assertRedirects(response, reverse("home"))


def test_logout_logs_out_and_goes_home(client, user):
    """Log out ends the session and goes to the home page.

    1. Log in
    2. Press "Log out" (a POST form)
    3. Expect: redirect to home, not logged in
    """
    client.force_login(user)

    response = client.post(reverse("logout"))

    assertRedirects(response, reverse("home"))
    assert not is_logged_in(client)


def test_logout_by_link_is_not_allowed(client, user):
    """Logout only by POST: a link on another site cannot log people out.

    1. Log in
    2. Open /accounts/logout/ as a link (GET)
    3. Expect: 405, still logged in
    """
    # Only POST: a link or an image on another site must not log people out.
    client.force_login(user)

    response = client.get(reverse("logout"))

    assert response.status_code == 405
    assert is_logged_in(client)


# Password reset


def get_reset_link():
    """The path of the reset link from the only email that was sent."""
    assert len(mail.outbox) == 1
    match = re.search(r"http://testserver(/accounts/reset/\S+/)", mail.outbox[0].body)
    assert match, mail.outbox[0].body
    return match.group(1)


def test_password_reset_full_flow(client, user):
    """A user resets a forgotten password with the link from the email.

    1. Ask for a reset link for anna@example.com
    2. Expect: one email to Anna, subject "Reset your BauHelfer password"
    3. Open the link and save a new password
    4. Expect: the new password works, the old one does not
    """
    # 1. Ask for the link: an email goes to the user.
    response = client.post(reverse("password_reset"), {"email": "anna@example.com"})
    assertRedirects(response, reverse("password_reset_done"))
    assert mail.outbox[0].to == ["anna@example.com"]
    assert mail.outbox[0].subject == "Reset your BauHelfer password"

    # 2. Open the link: Django hides the token from the address bar and shows the form.
    response = client.get(get_reset_link(), follow=True)
    assertContains(response, "Set a new password")

    # 3. Save the new password.
    response = client.post(
        response.redirect_chain[-1][0],
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assertRedirects(response, reverse("password_reset_complete"))

    # 4. The new password works, the old one does not.
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert not user.check_password(PASSWORD)


def test_password_reset_link_works_only_once(client, user):
    """A reset link stops working after the password is changed.

    1. Ask for a link and use it to set a new password
    2. Open the same link again
    3. Expect: "Link is not valid"
    """
    client.post(reverse("password_reset"), {"email": "anna@example.com"})
    link = get_reset_link()
    response = client.get(link, follow=True)
    client.post(
        response.redirect_chain[-1][0],
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )

    response = client.get(link, follow=True)

    assertContains(response, "Link is not valid")


def test_password_reset_new_passwords_must_match(client, user):
    """The two new passwords must match, otherwise nothing changes.

    1. Open the reset link from the email
    2. Enter two different new passwords
    3. Expect: an error with a red border; the old password still works
    """
    client.post(reverse("password_reset"), {"email": "anna@example.com"})
    response = client.get(get_reset_link(), follow=True)

    response = client.post(
        response.redirect_chain[-1][0],
        {"new_password1": NEW_PASSWORD, "new_password2": "something-else"},
    )

    assert response.status_code == 200
    assertContains(response, "input-error")
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


def test_password_reset_for_unknown_email_looks_the_same_but_sends_nothing(client):
    """Reset for an unknown email looks the same but sends nothing.

    1. Ask for a reset link for nobody@example.com
    2. Expect: the same "Check your email" page
    3. Expect: no email is sent
    """
    # Same answer as for a real account, so nobody can find out who is registered.
    response = client.post(reverse("password_reset"), {"email": "nobody@example.com"})

    assertRedirects(response, reverse("password_reset_done"))
    assert mail.outbox == []
