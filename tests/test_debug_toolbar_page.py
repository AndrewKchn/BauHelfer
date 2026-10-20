"""Integration tests: Django Debug Toolbar on a page, as runserver shows it (#135).

pytest runs without the toolbar (tests/test_debug_toolbar_settings.py), so each test here
switches it on with override_settings, the way local.py does under runserver, and loads
config/urls.py fresh so it sees the toolbar app.
"""

import importlib
import sys

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import NoReverseMatch, clear_url_caches, reverse

pytestmark = pytest.mark.story(135)

TOOLBAR = 'id="djDebug"'  # the toolbar's own <div> at the end of <body>


def reload_urls():
    """Import config/urls.py fresh and forget the URLs Django has cached."""
    from config import urls

    importlib.reload(urls)
    clear_url_caches()


@pytest.fixture
def toolbar_installed():
    """The toolbar's app, middleware and internal IP added as in local.py; undone after."""
    with override_settings(
        INSTALLED_APPS=[*settings.INSTALLED_APPS, "debug_toolbar"],
        MIDDLEWARE=[
            "debug_toolbar.middleware.DebugToolbarMiddleware",
            *settings.MIDDLEWARE,
        ],
        INTERNAL_IPS=["127.0.0.1"],
    ):
        yield
    reload_urls()


@pytest.mark.django_db
@pytest.mark.usefixtures("toolbar_installed")
def test_toolbar_shows_on_a_page_with_debug_on(client):
    """With DEBUG on, the job list from 127.0.0.1 ends with the toolbar.

    1. Install the toolbar as local.py does, switch DEBUG on
    2. Open the job list (the test client comes from 127.0.0.1)
    3. Expect: the toolbar's <div> is in the page
    """
    with override_settings(DEBUG=True):
        reload_urls()
        response = client.get(reverse("home"))

    assert TOOLBAR in response.content.decode()


@pytest.mark.django_db
@pytest.mark.usefixtures("toolbar_installed")
def test_toolbar_hides_with_debug_off(client):
    """With DEBUG off, the same page has no toolbar.

    1. Install the toolbar as local.py does, keep DEBUG off
    2. Open the job list
    3. Expect: no toolbar <div> in the page
    """
    reload_urls()
    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert TOOLBAR not in response.content.decode()


@pytest.mark.usefixtures("toolbar_installed")
def test_urls_route_the_toolbar_when_it_is_installed():
    """config/urls.py adds the toolbar's /__debug__/ URLs once its app is installed.

    1. Install the toolbar, switch DEBUG on, load urls.py fresh
    2. Expect: the toolbar's panel URL resolves under /__debug__/
    """
    with override_settings(DEBUG=True):
        reload_urls()
        url = reverse("djdt:render_panel")

    assert url.startswith("/__debug__/")


def test_urls_load_without_the_toolbar_package(monkeypatch):
    """Without the toolbar's app, urls.py loads even where the package is not installed.

    1. Hide the toolbar package, as on Render (`uv sync --no-dev`)
    2. Load urls.py with pytest's settings, where the app is not installed
    3. Expect: no import error, and the toolbar's panel URL does not resolve
    """
    # None in sys.modules makes `import debug_toolbar.toolbar` raise ImportError.
    monkeypatch.setitem(sys.modules, "debug_toolbar.toolbar", None)

    reload_urls()

    with pytest.raises(NoReverseMatch):
        reverse("djdt:render_panel")
