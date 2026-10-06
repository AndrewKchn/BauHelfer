"""Integration tests: the built app.css carries our light and dark themes (#83).

app.css is not in git: build it first (see CLAUDE.md), CI does it before the tests.
"""

import re

import pytest

from tests.test_base_layout import get_static_file

pytestmark = [pytest.mark.django_db, pytest.mark.story(83)]


def built_css(client):
    """app.css as the browser gets it, as text."""
    response, content = get_static_file(client, "css/app.css")
    assert response.status_code == 200
    return content.decode()


def rule_body(css, selector_pattern):
    """The declarations of the first CSS rule whose selector matches the pattern."""
    match = re.search(selector_pattern + r"[^{]*\{([^{}]*)\}", css)
    return match.group(1) if match else None


def test_light_theme_is_the_default(client):
    """Without a device preference the page uses our light theme.

    1. Download app.css like a browser does
    2. Expect: the bauhelfer-light rule also applies to :root (the whole page)
    """
    css = built_css(client)

    assert re.search(r":where\(:root\)[^{]*\[data-theme=bauhelfer-light\]", css)


def test_dark_theme_is_used_when_device_is_in_dark_mode(client):
    """A phone in dark mode gets our dark theme.

    1. Download app.css like a browser does
    2. Find the rule inside @media (prefers-color-scheme: dark)
    3. Expect: it sets exactly the same values as the bauhelfer-dark theme
    """
    css = built_css(client)

    dark_mode = rule_body(css, r"@media \(prefers-color-scheme:\s*dark\)\s*\{\s*:root")
    dark_theme = rule_body(css, r"\[data-theme=bauhelfer-dark\]")

    assert dark_theme is not None
    assert "color-scheme:dark" in dark_theme.replace(" ", "")
    assert dark_mode == dark_theme


def test_built_css_has_no_builtin_daisyui_themes(client):
    """Only our themes are built in, not daisyUI's light/dark.

    1. Download app.css like a browser does
    2. Expect: no [data-theme=light] or [data-theme=dark] rule
    """
    css = built_css(client)

    assert "[data-theme=light]" not in css
    assert "[data-theme=dark]" not in css
