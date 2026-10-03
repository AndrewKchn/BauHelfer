"""Checks the settings the live server on Render depends on (#5)."""

import importlib

from django.conf import settings


def load_production_settings():
    """Import production.py fresh, so it sees the environment set by the test."""
    from config.settings import production

    return importlib.reload(production)


def test_whitenoise_middleware_comes_right_after_security_middleware():
    # WhiteNoise docs: directly after SecurityMiddleware, before everything else.
    security = "django.middleware.security.SecurityMiddleware"
    whitenoise = "whitenoise.middleware.WhiteNoiseMiddleware"

    position = settings.MIDDLEWARE.index(security)
    assert settings.MIDDLEWARE[position + 1] == whitenoise


def test_collectstatic_writes_to_staticfiles_folder():
    assert settings.STATIC_ROOT == settings.BASE_DIR / "staticfiles"


def test_production_serves_compressed_static_files_with_hashed_names():
    production = load_production_settings()

    backend = production.STORAGES["staticfiles"]["BACKEND"]
    assert backend == "whitenoise.storage.CompressedManifestStaticFilesStorage"


def test_production_allows_the_host_name_render_gives_the_service(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "bauhelfer.onrender.com")

    production = load_production_settings()

    assert "bauhelfer.onrender.com" in production.ALLOWED_HOSTS


def test_production_without_render_adds_no_empty_host(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)

    production = load_production_settings()

    assert "" not in production.ALLOWED_HOSTS
