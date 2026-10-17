"""Unit tests: the theme tests read app.css the same way whether it is minified or not (#113).

CI and Render build app.css with --minify, the dev command (--watch) without it.
"""

import pytest

from tests.test_theme import normalise_css

pytestmark = pytest.mark.story(113)

MINIFIED = (
    ":where(:root),[data-theme=bauhelfer-light]{color-scheme:light;--color-base-100:#FFFBF5}"
    "@media (prefers-color-scheme:dark){:root:not([data-theme]){color-scheme:dark}}"
)

UNMINIFIED = """\
  :where(:root),[data-theme="bauhelfer-light"] {
    color-scheme: light;
    --color-base-100: #FFFBF5;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme]) {
      color-scheme: dark;
    }
  }
"""


def test_minified_and_unminified_css_read_the_same():
    """Minified and unminified CSS give the same text to search in.

    1. Take one theme rule written as --minify writes it and as --watch writes it
    2. Normalise both
    3. Expect: the two results are equal
    """
    assert normalise_css(MINIFIED) == normalise_css(UNMINIFIED)


def test_normalised_css_has_no_quotes_or_whitespace():
    """Quotes and whitespace are gone after normalising.

    1. Normalise the unminified rule
    2. Expect: the selector is written without quotes, nothing contains spaces or newlines
    """
    css = normalise_css(UNMINIFIED)

    assert "[data-theme=bauhelfer-light]" in css
    assert '"' not in css
    assert not any(char.isspace() for char in css)
