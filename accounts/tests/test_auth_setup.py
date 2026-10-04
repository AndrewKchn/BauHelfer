"""Unit tests for the account pages setup: URLs, redirects, email, form template (#9)."""

import pytest
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import resolve_url
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.forms import SignupForm
from config.settings import base

pytestmark = pytest.mark.django_db


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
    assert reverse(name) == path


def test_password_reset_confirm_url():
    url = reverse("password_reset_confirm", kwargs={"uidb64": "MQ", "token": "abc-123"})

    assert url == "/accounts/reset/MQ/abc-123/"


def test_login_and_logout_redirects():
    assert resolve_url(settings.LOGIN_URL) == reverse("login")
    assert resolve_url(settings.LOGIN_REDIRECT_URL) == reverse("home")
    assert resolve_url(settings.LOGOUT_REDIRECT_URL) == reverse("home")


def test_emails_are_printed_to_the_console_until_smtp_is_set_up():
    # Real sending comes with email notifications (#27). Tests use Django's in-memory backend.
    assert base.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"


def test_password_reset_email_contains_the_reset_link():
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
    form = SignupForm(data={"email": "not-an-email", "password1": "", "password2": ""})
    form.is_valid()

    html = render_to_string("_form_fields.html", {"form": form})

    assert str(form.fields["email"].label) in html
    assert form.errors["email"][0] in html
    assert "input-error" in html  # daisyUI red border on the wrong field


def test_form_template_shows_errors_that_belong_to_no_field():
    # A wrong password at login is an error of the whole form, not of one field.
    form = AuthenticationForm(
        data={"username": "anna@example.com", "password": "wrong"}
    )
    form.is_valid()

    html = render_to_string("_form_fields.html", {"form": form})

    assert form.non_field_errors()[0] in html
    assert 'role="alert"' in html
