"""Unit tests: the settings the live server on Render depends on (#5)."""

import importlib

import pytest
from django.conf import settings
from django.core.checks import Tags, run_checks
from django.core.management.utils import get_random_secret_key
from django.test import override_settings

pytestmark = pytest.mark.story(5)


def load_production_settings():
    """Import production.py fresh, so it sees the environment set by the test."""
    from config.settings import production

    return importlib.reload(production)


def test_whitenoise_middleware_comes_right_after_security_middleware():
    """WhiteNoise sits right after SecurityMiddleware, as its docs require.

    1. Look at the middleware list
    2. Expect: WhiteNoise directly after SecurityMiddleware
    """
    # WhiteNoise docs: directly after SecurityMiddleware, before everything else.
    security = "django.middleware.security.SecurityMiddleware"
    whitenoise = "whitenoise.middleware.WhiteNoiseMiddleware"

    position = settings.MIDDLEWARE.index(security)
    assert settings.MIDDLEWARE[position + 1] == whitenoise


def test_collectstatic_writes_to_staticfiles_folder():
    """collectstatic copies static files into the staticfiles/ folder.

    1. Read STATIC_ROOT
    2. Expect: <project>/staticfiles
    """
    assert settings.STATIC_ROOT == settings.BASE_DIR / "staticfiles"


def test_production_serves_compressed_static_files_with_hashed_names():
    """Production serves static files compressed, with hashed names.

    1. Load the production settings
    2. Expect: WhiteNoise's compressed manifest storage (browsers can cache files)
    """
    production = load_production_settings()

    backend = production.STORAGES["staticfiles"]["BACKEND"]
    assert backend == "whitenoise.storage.CompressedManifestStaticFilesStorage"


def test_production_allows_the_host_name_render_gives_the_service(monkeypatch):
    """The live site accepts the host name that Render gives it.

    1. Set RENDER_EXTERNAL_HOSTNAME to bauhelfer.onrender.com
    2. Load the production settings
    3. Expect: that host is allowed
    """
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "bauhelfer.onrender.com")

    production = load_production_settings()

    assert "bauhelfer.onrender.com" in production.ALLOWED_HOSTS


def test_production_without_render_adds_no_empty_host(monkeypatch):
    """Without Render's host name no empty host is allowed.

    1. Remove RENDER_EXTERNAL_HOSTNAME
    2. Load the production settings
    3. Expect: no empty entry in ALLOWED_HOSTS
    """
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)

    production = load_production_settings()

    assert "" not in production.ALLOWED_HOSTS


@pytest.mark.story(88)
def test_production_uses_https_only():
    """Production sends everything over HTTPS and keeps DEBUG off.

    1. Load the production settings
    2. Expect: Render's HTTPS header is trusted, http redirects to https, HSTS is on
    3. Expect: session and CSRF cookies only travel over HTTPS; DEBUG is off
    """
    production = load_production_settings()

    # Not covered by Django's deploy check: without it Render's http -> https loops.
    assert production.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert production.SECURE_SSL_REDIRECT is True
    assert production.SECURE_HSTS_SECONDS >= 3600  # may grow, never shrink
    assert production.SESSION_COOKIE_SECURE is True
    assert production.CSRF_COOKIE_SECURE is True
    assert production.DEBUG is False


# Warnings we accept on purpose; docs/SECURITY.md explains them.
ACCEPTED_DEPLOY_WARNINGS = {
    "security.W005",  # HSTS for subdomains: bauhelfer.onrender.com has none
    "security.W021",  # HSTS preload list: needs our own domain, not onrender.com
}


@pytest.mark.story(88)
def test_production_passes_the_django_deploy_check(monkeypatch):
    """Django's own deployment checklist finds nothing new in the production settings.

    1. Load the production settings as on Render (host name, random secret key)
    2. Run Django's security checks (manage.py check --deploy)
    3. Expect: no warnings except the two we accept on purpose
    """
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "bauhelfer.onrender.com")
    # Render generates the key (render.yaml); the keys in .env and CI are not checked.
    monkeypatch.setenv("SECRET_KEY", get_random_secret_key())
    production = load_production_settings()
    changed = {
        name: getattr(production, name)
        for name in dir(production)
        if name.isupper() and getattr(production, name) != getattr(settings, name, None)
    }

    with override_settings(**changed):
        found = run_checks(include_deployment_checks=True, tags=[Tags.security])

    assert {message.id for message in found} - ACCEPTED_DEPLOY_WARNINGS == set()
