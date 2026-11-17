"""Unit tests: the translation cache row (#31), what the coverage review of #40 found missing.

The cache itself is tested in test_services.py; here only how a row is shown.
"""

import pytest

from translations.models import Translation

pytestmark = pytest.mark.story(40)


def test_str_shows_start_of_the_hash_and_the_language():
    """A cached translation is shown as the first 12 characters of its hash and its language.

    1. Make a translation row of a 64-character hash into German (not saved)
    2. Expect: the first 12 characters, an arrow, "de"; never the translated text, which
       may hold names and phone numbers (ai-translation.md D3)
    """
    row = Translation(
        source_hash="0123456789ab" + "f" * 52, target_language="de", text="Hallo"
    )

    assert str(row) == "0123456789ab → de"
