"""Unit tests: which settings load Django Debug Toolbar (#135).

The toolbar is for runserver only. pytest uses the same local.py, so local.py adds it only
when pytest is not running (the PYTEST_VERSION variable, set by pytest at start, as the
toolbar's docs recommend). Production never adds it: on Render the package is not even
installed (`uv sync --no-dev`).
"""

import importlib

import pytest
from django.conf import settings

from tests.test_deploy import MEDIA_ENV

pytestmark = pytest.mark.story(135)

APP = "debug_toolbar"
MIDDLEWARE = "debug_toolbar.middleware.DebugToolbarMiddleware"


@pytest.fixture
def outside_pytest(monkeypatch):
    """The environment of runserver: no PYTEST_VERSION, Render's storage variables set."""
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    for name, value in MEDIA_ENV.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def reload_settings_after():
    """Load the settings files fresh again after the test, with pytest's environment."""
    yield
    from config.settings import local, production

    importlib.reload(local)
    importlib.reload(production)


def load(name):
    """Import config/settings/<name>.py fresh, so it sees the environment set by the test."""
    module = importlib.import_module(f"config.settings.{name}")
    return importlib.reload(module)


@pytest.mark.usefixtures("outside_pytest", "reload_settings_after")
def test_local_settings_add_the_toolbar_for_runserver():
    """local.py adds the toolbar's app and middleware when pytest is not running.

    1. Remove PYTEST_VERSION, as under runserver
    2. Load local.py
    3. Expect: the app and the middleware are in, shown only for 127.0.0.1
    """
    local = load("local")

    assert APP in local.INSTALLED_APPS
    assert MIDDLEWARE in local.MIDDLEWARE
    assert local.INTERNAL_IPS == ["127.0.0.1"]


def test_the_test_run_does_not_add_the_toolbar():
    """pytest runs without the toolbar's app and middleware.

    1. Look at the settings pytest runs with
    2. Expect: no toolbar app, no toolbar middleware
    """
    assert APP not in settings.INSTALLED_APPS
    assert MIDDLEWARE not in settings.MIDDLEWARE


@pytest.mark.usefixtures("outside_pytest", "reload_settings_after")
def test_production_does_not_add_the_toolbar():
    """production.py never adds the toolbar, even outside pytest.

    1. Remove PYTEST_VERSION, as on Render
    2. Load production.py
    3. Expect: no toolbar app, no toolbar middleware
    """
    production = load("production")

    assert APP not in production.INSTALLED_APPS
    assert MIDDLEWARE not in production.MIDDLEWARE
