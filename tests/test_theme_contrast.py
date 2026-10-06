"""Unit tests: our light and dark daisyUI themes in tailwind/input.css (#83).

The themes are read straight from the source file, so no CSS build is needed.
Contrast is computed with the WCAG 2.x formula: https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
"""

import re

import pytest
from django.conf import settings

pytestmark = [pytest.mark.story(83)]

INPUT_CSS = settings.BASE_DIR / "tailwind" / "input.css"
THEMES = ("bauhelfer-light", "bauhelfer-dark")

# WCAG AA for normal-size text. Buttons and alerts use normal-size text, so all pairs need it.
AA_NORMAL_TEXT = 4.5

# Every variable a daisyUI 5 theme has. The theme plugin does not fill in missing ones:
# a missing --radius-box would simply not exist in the built CSS.
THEME_VARIABLES = {
    "--color-base-100", "--color-base-200", "--color-base-300", "--color-base-content",
    "--color-primary", "--color-primary-content",
    "--color-secondary", "--color-secondary-content",
    "--color-accent", "--color-accent-content",
    "--color-neutral", "--color-neutral-content",
    "--color-info", "--color-info-content",
    "--color-success", "--color-success-content",
    "--color-warning", "--color-warning-content",
    "--color-error", "--color-error-content",
    "--radius-selector", "--radius-field", "--radius-box",
    "--size-selector", "--size-field", "--border", "--depth", "--noise",
}  # fmt: skip

# (background, text) pairs that appear on our pages.
TEXT_PAIRS = [
    ("base-100", "base-content"),  # page text
    ("base-200", "base-content"),  # page background around cards
    ("base-300", "base-content"),
    ("primary", "primary-content"),  # btn-primary
    ("secondary", "secondary-content"),
    ("accent", "accent-content"),
    ("neutral", "neutral-content"),
    ("info", "info-content"),  # alert-info
    ("success", "success-content"),  # alert-success
    ("warning", "warning-content"),  # alert-warning
    ("error", "error-content"),  # alert-error
    ("base-100", "error"),  # text-error: form error text on a card
]


def read_themes():
    """The theme blocks in input.css as {name: {variable: value}}."""
    css = INPUT_CSS.read_text()
    blocks = re.findall(
        r'@plugin\s+"\./daisyui-theme\.mjs"\s*\{(.*?)\}', css, re.DOTALL
    )
    themes = {}
    for block in blocks:
        name = re.search(r'name:\s*"([^"]+)"', block).group(1)
        themes[name] = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))
    return themes


def relative_luminance(hex_color):
    """How bright a colour looks, 0 (black) to 1 (white), from a #RRGGBB value."""
    assert re.fullmatch(r"#[0-9A-Fa-f]{6}", hex_color), f"use #RRGGBB, not {hex_color}"
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    red, green, blue = linear
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(color_a, color_b):
    """WCAG contrast ratio of two colours: 1 (same) to 21 (black on white)."""
    lighter, darker = sorted(
        [relative_luminance(color_a), relative_luminance(color_b)], reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_contrast_formula_matches_known_values():
    """The contrast helper gives the known WCAG results.

    1. Compute black on white, a colour with itself, and #767676 on white
    2. Expect: 21, 1 and 4.54 (the classic "lightest grey that passes AA")
    """
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21)
    assert contrast_ratio("#1E3A5F", "#1E3A5F") == pytest.approx(1)
    assert contrast_ratio("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.01)


def test_input_css_defines_light_and_dark_theme():
    """input.css has our two themes, bauhelfer-light and bauhelfer-dark.

    1. Read the daisyui-theme blocks from tailwind/input.css
    2. Expect: exactly the themes bauhelfer-light and bauhelfer-dark
    """
    assert set(read_themes()) == set(THEMES)


@pytest.mark.parametrize("theme", THEMES)
def test_theme_sets_every_daisyui_variable(theme):
    """The theme sets every daisyUI variable, so nothing falls back to nothing.

    1. Read the theme's variables from tailwind/input.css
    2. Expect: all 28 daisyUI 5 theme variables, none missing
    """
    variables = set(read_themes().get(theme, {}))

    assert THEME_VARIABLES - variables == set()


@pytest.mark.parametrize("background, text", TEXT_PAIRS)
@pytest.mark.parametrize("theme", THEMES)
def test_text_passes_wcag_aa_contrast(theme, background, text):
    """Text on its background passes WCAG AA contrast (4.5:1).

    1. Read the two colours of the pair from the theme in tailwind/input.css
    2. Compute their WCAG contrast ratio
    3. Expect: at least 4.5
    """
    colors = read_themes().get(theme, {})
    bg = colors.get(f"--color-{background}", "")
    fg = colors.get(f"--color-{text}", "")

    assert contrast_ratio(bg, fg) >= AA_NORMAL_TEXT
