"""Integration tests: the shared page layout base.html, its CSS and HTMX (#3)."""

import re

import pytest
from django.conf import settings
from django.contrib.messages import constants
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

pytestmark = pytest.mark.django_db

HTMX_VERSION = "2.0.10"


def get_static_file(client, path):
    """Fetch a static file the way the browser does; WhiteNoise serves it."""
    response = client.get(static(path))
    if response.status_code != 200:
        return response, b""
    return response, b"".join(response.streaming_content)


def test_home_page_uses_base_layout(client):
    response = client.get(reverse("home"))

    assert response.status_code == 200
    assertTemplateUsed(response, "base.html")


def test_layout_is_set_up_for_phone_screens(client):
    response = client.get(reverse("home"))

    # Without this tag phones render the page at desktop width and zoom out.
    viewport = 'name="viewport" content="width=device-width, initial-scale=1"'
    assert viewport in response.text


def test_layout_loads_css_and_htmx(client):
    response = client.get(reverse("home"))

    assert static("css/app.css") in response.text
    assert static("js/htmx.min.js") in response.text


def test_htmx_file_is_served_in_the_chosen_version(client):
    response, content = get_static_file(client, "js/htmx.min.js")

    assert response.status_code == 200
    assert f'"{HTMX_VERSION}"'.encode() in content


def test_built_css_is_served_and_contains_daisyui(client):
    # app.css is not in git: it is built by the Tailwind CLI (locally, in CI, on Render).
    response, content = get_static_file(client, "css/app.css")

    assert response.status_code == 200
    assert b".btn" in content  # a daisyUI class: the plugin was part of the build


def test_layout_shows_messages():
    message = Message(constants.SUCCESS, "Your profile was saved.")

    html = render_to_string("base.html", {"messages": [message]})

    assert "Your profile was saved." in html
    assert 'role="alert"' in html


def test_every_page_template_extends_base():
    # Partials (_name.html) are pieces of a page, so they do not extend base.html.
    templates_dir = settings.BASE_DIR / "templates"
    pages = [
        path
        for path in templates_dir.rglob("*.html")
        if path.name != "base.html" and not path.name.startswith("_")
    ]
    extends_base = re.compile(r"""^\s*{%\s*extends\s+["']base\.html["']\s*%}""")

    not_extending = [
        str(path.relative_to(templates_dir))
        for path in pages
        if not extends_base.match(path.read_text())
    ]

    assert pages, "no page templates found"
    assert not_extending == []
