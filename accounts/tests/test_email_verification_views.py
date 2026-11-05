"""Integration tests: signup, the confirmation link and the login hint (#81).

Each test goes through the whole stack: middleware, URL, view, form, template and database.
Spec: docs/specs/email-verification.md, iteration 1 (R1–R6), acceptance criteria AC1–AC5,
AC8, AC10.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pytest_django.asserts import assertContains, assertRedirects

pytestmark = [pytest.mark.django_db, pytest.mark.story(81)]

User = get_user_model()

PASSWORD = "Gerüst-2026-Munich"
FAILING_BACKEND = "jobs.tests.test_notifications.FailingBackend"


def sign_up(client, email="ben@example.com", **kwargs):
    """Send the signup form for `email`."""
    return client.post(
        reverse("register"),
        {"email": email, "password1": PASSWORD, "password2": PASSWORD},
        **kwargs,
    )


def link_path(email):
    """The path of the confirmation link in `email`'s body."""
    match = re.search(r"https?://testserver(/accounts/verify/\S+/)", email.body)
    assert match, email.body
    return match.group(1)


def is_logged_in(client):
    """True if the test client's session belongs to a logged-in user."""
    return "_auth_user_id" in client.session


def test_signup_creates_an_inactive_account_and_sends_the_link(client, mailoutbox):
    """Signup saves an inactive, unconfirmed account and emails the link (AC1).

    1. Sign up as Ben@Example.com
    2. Expect: a redirect to the "check your email" page; nobody is logged in
    3. Expect: ben@example.com is saved, inactive and unconfirmed
    4. Expect: one email to ben@example.com with an absolute link to the confirm page
    """
    response = sign_up(client, email="Ben@Example.com")

    assertRedirects(response, reverse("register_done"))
    assert not is_logged_in(client)
    user = User.objects.get(email="ben@example.com")
    assert not user.is_active
    assert user.email_verified_at is None
    [email] = mailoutbox
    assert email.to == ["ben@example.com"]
    assert link_path(email).startswith("/accounts/verify/")


def test_done_page_shows_the_address(client):
    """The "check your email" page names the address the link went to (AC2, D7).

    1. Sign up as ben@example.com, follow the redirect
    2. Expect: the page names ben@example.com and says to open the link
    """
    response = sign_up(client, follow=True)

    assertContains(response, "ben@example.com")
    assertContains(response, "Open it to activate your account.")


def test_opening_the_link_only_shows_a_button(client, mailoutbox):
    """Opening the link changes nothing: a mail scanner would open it too (AC3, D6).

    1. Sign up, take the link from the email
    2. Open it (GET)
    3. Expect: the page has a "Confirm email" button that posts to the same link
    4. Expect: the account is still inactive and unconfirmed, nobody is logged in
    """
    sign_up(client)
    path = link_path(mailoutbox[0])

    response = client.get(path)

    assertContains(response, "Confirm email")
    assertContains(response, 'method="post"')
    user = User.objects.get()
    assert not user.is_active
    assert user.email_verified_at is None
    assert not is_logged_in(client)


def test_confirming_activates_the_account_and_logs_in(client, mailoutbox):
    """The button confirms the address, activates the account and logs in (AC4).

    1. Sign up, take the link from the email
    2. Press "Confirm email" (POST to the link)
    3. Expect: a redirect to the role choice with "Your email is confirmed."
    4. Expect: the account is active, confirmed and logged in
    """
    sign_up(client)
    path = link_path(mailoutbox[0])

    response = client.post(path, follow=True)

    assertRedirects(response, reverse("role_select"))
    assertContains(response, "Your email is confirmed.")
    user = User.objects.get()
    assert user.is_active
    assert user.email_verified_at is not None
    assert is_logged_in(client)


def test_link_works_only_once(client, mailoutbox):
    """A used link shows the "invalid" page and changes nothing (AC5).

    1. Sign up and confirm with the link
    2. In another browser, open the same link and press the button again
    3. Expect: "This link is invalid or has expired" both times, nobody logged in there
    4. Expect: the confirmation date has not changed
    """
    sign_up(client)
    path = link_path(mailoutbox[0])
    client.post(path)
    confirmed_at = User.objects.get().email_verified_at
    other = Client()

    for response in (other.get(path), other.post(path)):
        assertContains(response, "This link is invalid or has expired")
    assert not is_logged_in(other)
    assert User.objects.get().email_verified_at == confirmed_at


@pytest.mark.parametrize("uid", ["real", "unknown"])
def test_wrong_link_shows_the_invalid_page(client, uid):
    """A made-up link, for a real or an unknown user, shows the "invalid" page (R5).

    1. Create an inactive user
    2. Open a link with their id and a wrong token, or with an id that is not base64
    3. Expect: status 200 and "This link is invalid or has expired"
    """
    user = User.objects.create_user(
        email="ben@example.com", password=PASSWORD, is_active=False
    )
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk)) if uid == "real" else "x!"
    path = reverse("verify_email", args=[uidb64, "abc-def"])

    response = client.get(path)

    assertContains(response, "This link is invalid or has expired")


def test_login_before_confirming_shows_the_hint(client):
    """Logging in before confirming asks to confirm the email first (AC8).

    1. Sign up as ben@example.com, do not open the link
    2. Log in with the right password
    3. Expect: "Please confirm your email first." and nobody is logged in
    """
    sign_up(client)

    response = client.post(
        reverse("login"), {"username": "ben@example.com", "password": PASSWORD}
    )

    assertContains(response, "Please confirm your email first.")
    assert not is_logged_in(client)


def test_failed_email_keeps_the_account_and_logs_no_address(client, settings, caplog):
    """A failed send is logged without the address; signup still finishes (AC10, D9).

    1. Use an email backend that raises an error naming the address
    2. Sign up as ben@example.com
    3. Expect: a redirect to the "check your email" page; the account exists
    4. Expect: an ERROR record with the user id, and no address in any record
    """
    settings.EMAIL_BACKEND = FAILING_BACKEND

    response = sign_up(client)

    assertRedirects(response, reverse("register_done"))
    user = User.objects.get()
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert [r.getMessage() for r in errors] == [
        f"Verification email failed: user_id={user.pk} error=ConnectionError"
    ]
    assert "@example.com" not in caplog.text
