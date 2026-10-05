"""Unit tests: account pages setup — URLs, redirects, email, form template (#9)."""

import pytest
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import resolve_url
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.forms import SignupForm
from config.settings import base

pytestmark = [pytest.mark.django_db, pytest.mark.story(9)]


@pytest.mark.parametrize(
    ("name", "path"),
    [
        ("register", "/accounts/register/"),
        ("login", "/accounts/login/"),
        ("logout", "/accounts/logout/"),
        ("password_reset", "/accounts/password-reset/"),
        ("password_reset_done", "/accounts/password-reset/done/"),
        ("password_reset_complete", "/accounts/reset/done/"),
    ],
)
def test_account_urls(name, path):
    """Every account page has its address under /accounts/.

    1. Look up each page by its name, e.g. "login"
    2. Expect: the agreed address, e.g. /accounts/login/
    """
    assert reverse(name) == path


def test_password_reset_confirm_url():
    """The link in the reset email looks like /accounts/reset/<uid>/<token>/.

    1. Build the address from a user id and a token
    2. Expect: /accounts/reset/MQ/abc-123/
    """
    url = reverse("password_reset_confirm", kwargs={"uidb64": "MQ", "token": "abc-123"})

    assert url == "/accounts/reset/MQ/abc-123/"


def test_login_and_logout_redirects():
    """After login and logout the user lands on the home page.

    1. Read the login settings
    2. Expect: the login page is "login"
    3. Expect: after login and after logout the user goes to "home"
    """
    assert resolve_url(settings.LOGIN_URL) == reverse("login")
    assert resolve_url(settings.LOGIN_REDIRECT_URL) == reverse("home")
    assert resolve_url(settings.LOGOUT_REDIRECT_URL) == reverse("home")


def test_emails_are_printed_to_the_console_until_smtp_is_set_up():
    """Emails are printed to the console until real sending in #27.

    1. Read the email backend setting
    2. Expect: the console backend
    """
    # Real sending comes with email notifications (#27). Tests use Django's in-memory backend.
    assert base.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"


def test_password_reset_email_contains_the_reset_link():
    """The reset email contains the link to set a new password.

    1. Render the reset email for a user id and a token
    2. Expect: the full https link to /accounts/reset/<uid>/<token>/
    """
    context = {
        "protocol": "https",
        "domain": "bauhelfer.example",
        "uid": "MQ",
        "token": "abc-123",
        "email": "anna@example.com",
    }

    text = render_to_string("registration/password_reset_email.txt", context)

    assert "https://bauhelfer.example/accounts/reset/MQ/abc-123/" in text


def test_form_template_shows_field_errors_next_to_the_field():
    """A wrong field shows its error right under it, with a red border.

    1. Fill the signup form with an invalid email
    2. Render the shared form template
    3. Expect: the field label, its error and the red border class
    """
    form = SignupForm(data={"email": "not-an-email", "password1": "", "password2": ""})
    form.is_valid()

    html = render_to_string("_form_fields.html", {"form": form})

    assert str(form.fields["email"].label) in html
    assert form.errors["email"][0] in html
    assert "input-error" in html  # daisyUI red border on the wrong field


def test_form_template_shows_errors_that_belong_to_no_field():
    """An error of the whole form (e.g. wrong password) shows on top.

    1. Fill the login form with a wrong password
    2. Render the shared form template
    3. Expect: the error in a red box with role="alert"
    """
    # A wrong password at login is an error of the whole form, not of one field.
    form = AuthenticationForm(
        data={"username": "anna@example.com", "password": "wrong"}
    )
    form.is_valid()

    html = render_to_string("_form_fields.html", {"form": form})

    assert form.non_field_errors()[0] in html
    assert 'role="alert"' in html
