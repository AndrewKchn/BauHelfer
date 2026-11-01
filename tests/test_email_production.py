"""Unit tests: production sends email through Brevo's HTTP API, other settings never (#27).

Spec: docs/specs/notifications.md, iteration 3 (R15-R17, D1, D12), acceptance criteria
AC15, AC16. The production settings are loaded with made-up values; nothing here reaches
the network: the one real call is the manual check in the PR.
"""

import re

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import get_connection
from django.test import override_settings

# media_env is the autouse fixture of test_deploy.py; imported, pytest uses it here too, so
# every test starts with the variables set, as on Render.
from tests.test_deploy import (
    EMAIL_ENV,
    load_production_settings,
    media_env,  # noqa: F401
)

pytestmark = [pytest.mark.story(27)]


def test_production_sends_through_brevos_api():
    """Production uses anymail's Brevo backend: HTTPS, not the SMTP ports Render blocks (D1).

    1. Set the email variables; load the production settings
    2. Expect: EMAIL_BACKEND is anymail's Brevo backend
    3. Expect: the API key and the sender come from BREVO_API_KEY and DEFAULT_FROM_EMAIL
    """
    production = load_production_settings()

    assert production.EMAIL_BACKEND == "anymail.backends.brevo.EmailBackend"
    assert production.ANYMAIL["BREVO_API_KEY"] == EMAIL_ENV["BREVO_API_KEY"]
    assert production.DEFAULT_FROM_EMAIL == EMAIL_ENV["DEFAULT_FROM_EMAIL"]


def test_brevo_backend_reads_the_key_from_the_settings():
    """anymail finds the key where production puts it: a misspelt name fails only on Render.

    1. Load the production settings; use their EMAIL_BACKEND and ANYMAIL
    2. Build the email connection Django would use
    3. Expect: the backend holds the key from BREVO_API_KEY
    """
    production = load_production_settings()

    with override_settings(ANYMAIL=production.ANYMAIL):
        connection = get_connection(production.EMAIL_BACKEND)

    assert connection.api_key == EMAIL_ENV["BREVO_API_KEY"]


@pytest.mark.parametrize("name", list(EMAIL_ENV))
def test_production_does_not_start_without_an_email_variable(monkeypatch, name):
    """Without the key or the sender, production stops at start (R17, D12).

    Otherwise the site would run and every email would fail, seen only in the logs.

    1. Remove BREVO_API_KEY (or DEFAULT_FROM_EMAIL)
    2. Load the production settings
    3. Expect: ImproperlyConfigured naming the variable
    """
    monkeypatch.delenv(name)

    with pytest.raises(ImproperlyConfigured, match=name):
        load_production_settings()


def test_render_asks_for_the_email_variables():
    """render.yaml lists both variables; Render asks for their values (R16).

    1. Read render.yaml
    2. Expect: each variable followed by "sync: false" (the value is set in the dashboard,
       never in the repo)
    """
    text = (settings.BASE_DIR / "render.yaml").read_text()

    for name in EMAIL_ENV:
        assert re.search(rf"key: {name}\s+sync: false", text), name


def test_local_settings_print_emails_to_the_terminal():
    """Locally, emails are printed by runserver, never sent (AC16).

    1. Read EMAIL_BACKEND of the local settings module (tests replace the live setting)
    2. Expect: Django's console backend
    """
    from config.settings import local

    assert local.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"


def test_tests_keep_emails_in_memory():
    """Tests never send: pytest-django keeps every email in a list (AC16).

    1. Read the live EMAIL_BACKEND during a test
    2. Expect: Django's in-memory backend
    """
    assert settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend"
