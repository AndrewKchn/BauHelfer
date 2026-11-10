"""Unit tests: the fake translator the site uses without a key (#31).

Spec: docs/specs/ai-translation.md, iteration 1 (R4, R5, D5), acceptance criterion AC8.
Locally and in tests TRANSLATION_BACKEND points to it, as EMAIL_BACKEND points to the
console: the site works without an Anthropic key, and nothing leaves the computer.
"""

import pytest
from django.conf import settings

from translations.backends.fake_claude import FakeClaudeBackend

pytestmark = [pytest.mark.story(31)]


def test_fake_backend_marks_the_text_with_the_language():
    """The fake translator answers "[<lang>] <text>", so a page shows it was "translated".

    1. Ask FakeClaudeBackend to translate "Abriss ab Montag" into Polish
    2. Expect: "[pl] Abriss ab Montag"
    """
    assert (
        FakeClaudeBackend().translate("Abriss ab Montag", "pl")
        == "[pl] Abriss ab Montag"
    )


def test_fake_backend_is_the_default():
    """Without settings of production, the translator is the fake one (AC8, D5).

    1. Read TRANSLATION_BACKEND in the settings the tests and runserver use
    2. Expect: the dotted path of FakeClaudeBackend
    """
    assert (
        settings.TRANSLATION_BACKEND
        == "translations.backends.fake_claude.FakeClaudeBackend"
    )
