"""Unit tests: the settings the live server on Render depends on (#5)."""

import importlib

import pytest
from django.conf import settings

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
