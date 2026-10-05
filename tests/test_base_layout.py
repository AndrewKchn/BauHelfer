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

pytestmark = [pytest.mark.django_db, pytest.mark.story(3)]

HTMX_VERSION = "2.0.10"


def get_static_file(client, path):
    """Fetch a static file the way the browser does; WhiteNoise serves it."""
    response = client.get(static(path))
    if response.status_code != 200:
        return response, b""
    return response, b"".join(response.streaming_content)


def test_home_page_uses_base_layout(client):
    """The home page is built on the shared layout base.html.

    1. Open the home page
    2. Expect: status 200, base.html is used
    """
    response = client.get(reverse("home"))

    assert response.status_code == 200
    assertTemplateUsed(response, "base.html")


def test_layout_is_set_up_for_phone_screens(client):
    """The layout has the viewport tag, so phones show it at phone width.

    1. Open the home page
    2. Expect: the viewport meta tag
    """
    response = client.get(reverse("home"))

    # Without this tag phones render the page at desktop width and zoom out.
    viewport = 'name="viewport" content="width=device-width, initial-scale=1"'
    assert viewport in response.text


def test_layout_loads_css_and_htmx(client):
    """Every page loads our CSS and HTMX.

    1. Open the home page
    2. Expect: links to app.css and htmx.min.js
    """
    response = client.get(reverse("home"))

    assert static("css/app.css") in response.text
    assert static("js/htmx.min.js") in response.text


def test_htmx_file_is_served_in_the_chosen_version(client):
    """The server delivers HTMX in the chosen version 2.0.10.

    1. Download htmx.min.js like a browser does
    2. Expect: status 200 and the version "2.0.10" inside
    """
    response, content = get_static_file(client, "js/htmx.min.js")

    assert response.status_code == 200
    assert f'"{HTMX_VERSION}"'.encode() in content


def test_built_css_is_served_and_contains_daisyui(client):
    """The built CSS is delivered and contains daisyUI.

    1. Download app.css like a browser does
    2. Expect: status 200 and the daisyUI class .btn inside
    """
    # app.css is not in git: it is built by the Tailwind CLI (locally, in CI, on Render).
    response, content = get_static_file(client, "css/app.css")

    assert response.status_code == 200
    assert b".btn" in content  # a daisyUI class: the plugin was part of the build


def test_layout_shows_messages():
    """Messages like "Your profile was saved." appear on the page.

    1. Render base.html with one success message
    2. Expect: the text in a box with role="alert"
    """
    message = Message(constants.SUCCESS, "Your profile was saved.")

    html = render_to_string("base.html", {"messages": [message]})

    assert "Your profile was saved." in html
    assert 'role="alert"' in html


def test_every_page_template_extends_base():
    """Every page template is built on base.html.

    1. Look at every template in templates/ (partials _name.html are not pages)
    2. Expect: each page starts with extends "base.html"
    """
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
