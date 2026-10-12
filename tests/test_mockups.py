"""Unit tests: the UI mockups saved in docs/mockups/ (#122).

The mockups are PNG pictures of phone screens, listed with their tickets in
docs/mockups/README.md. The specs and the ticket workflow point to them, so a missing or
unlisted picture would go unnoticed without these checks.
"""

import re
import struct
from pathlib import Path

import pytest

pytestmark = [pytest.mark.story(122)]

MOCKUPS = Path(__file__).resolve().parent.parent / "docs" / "mockups"
README = MOCKUPS / "README.md"


def linked_images():
    """The image file names the README shows: ![…](post-a-job.png) or <img src="…png">.

    The README uses <img width="…">, because GitHub shows Markdown images at full size.
    """
    return re.findall(r'(?:!\[[^\]]*\]\(|<img src=")([^)"]+\.png)', README.read_text())


def png_size(path):
    """Width and height of a PNG, read from its header (bytes 16-24 of the IHDR chunk)."""
    return struct.unpack(">II", path.read_bytes()[16:24])


def test_every_listed_screen_exists():
    """Every screen the mockup README shows is a picture in docs/mockups/.

    1. Read the image links in docs/mockups/README.md
    2. Expect: at least one link, and a file for each of them
    """
    images = linked_images()

    assert images, "the README shows no screens"
    assert [name for name in images if not (MOCKUPS / name).is_file()] == []


def test_every_screen_is_listed():
    """Every picture in docs/mockups/ is shown in the README, so none is forgotten.

    1. List the PNG files in docs/mockups/
    2. Expect: each one is linked from the README
    """
    pictures = sorted(path.name for path in MOCKUPS.glob("*.png"))

    assert pictures
    assert [name for name in pictures if name not in linked_images()] == []


def test_screens_have_phone_proportions():
    """Every screen has the proportions of the 390 × 844 phone of the mockup.

    1. Read the width and height of each PNG
    2. Expect: width : height = 390 : 844 (sharper pictures may be 2× or 3× larger)
    """
    pictures = list(MOCKUPS.glob("*.png"))
    wrong = [
        path.name
        for path in pictures
        if png_size(path)[0] * 844 != png_size(path)[1] * 390
    ]

    assert pictures
    assert wrong == []
