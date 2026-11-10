"""Unit tests: detect_language() finds the language of a text, never raises (#32).

Spec: docs/specs/job-translation.md, iteration 1 (R2, R4, D2, D3, D11), acceptance
criterion AC1. The translators are the small classes below, chosen through
TRANSLATION_BACKEND as in test_errors_and_limits.py; they record their calls, so a test
sees whether anything would have been sent to Claude. Nothing here reaches the network.
"""

from typing import ClassVar

import pytest

from translations.backends import TranslationError
from translations.backends.fake_claude import FakeClaudeBackend
from translations.services import detect_language

pytestmark = [pytest.mark.story(32)]

JOB_TEXT = "Нужны 2 человека на демонтаж, звонить Ивану +49 151 2345678"


class AnsweringBackend:
    """A translator whose detect_language() answers `answer` and records each call."""

    answer: ClassVar = "ru"
    calls: ClassVar[list] = []

    def detect_language(self, text):
        """Record the call and answer with the prepared code."""
        self.calls.append(text)
        return self.answer


class UnavailableBackend:
    """A translator that cannot answer, as Claude when the API is down."""

    def detect_language(self, text):
        """Raise TranslationError, as ClaudeBackend does for an API error."""
        raise TranslationError("APIConnectionError")


@pytest.fixture(autouse=True)
def answering(settings):
    """Use AnsweringBackend for every test here: answer "ru", no calls yet."""
    settings.TRANSLATION_BACKEND = f"{__name__}.AnsweringBackend"
    AnsweringBackend.answer = "ru"
    AnsweringBackend.calls = []
    return AnsweringBackend


@pytest.mark.parametrize("code", ["ru", "de", "tr", ""])
def test_the_translators_answer_comes_back(answering, code):
    """The code the translator found comes back; "" means a language not among our 7.

    1. The translator answers "ru", "de", "tr" or "" (another language, D3)
    2. Detect the language of the job text
    3. Expect: that answer, after one call with the text
    """
    answering.answer = code

    assert detect_language(JOB_TEXT) == code
    assert answering.calls == [JOB_TEXT]


@pytest.mark.parametrize("text", ["", "   \n"], ids=["empty", "whitespace"])
def test_empty_text_is_not_sent(answering, text):
    """An empty text has no language: None, and the translator is not asked.

    1. Detect the language of "" or of whitespace
    2. Expect: None, no call
    """
    assert detect_language(text) is None
    assert answering.calls == []


def test_text_over_the_limit_is_not_sent(answering, settings):
    """A text longer than TRANSLATION_MAX_LENGTH is not sent, as for translate() (#34 D16).

    1. Detect the language of a text of 1001 characters
    2. Expect: None, no call
    3. Detect the language of a text of 1000 characters
    4. Expect: the translator's answer
    """
    assert settings.TRANSLATION_MAX_LENGTH == 1000

    assert detect_language("я" * 1001) is None
    assert answering.calls == []
    assert detect_language("я" * 1000) == "ru"


def test_failing_translator_gives_none_and_a_log_line(settings, caplog):
    """A translator that fails gives None, logged with the error class, not the text.

    1. The translator raises TranslationError
    2. Detect the language of the job text
    3. Expect: None, no exception
    4. Expect: a WARNING "Language detection failed: hash=<12> error=TranslationError",
       without the text or its phone number
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"

    assert detect_language(JOB_TEXT) is None

    [record] = [r for r in caplog.records if r.name.startswith("translations")]
    assert record.levelname == "WARNING"
    message = record.getMessage()
    assert message.startswith("Language detection failed: hash=")
    assert message.endswith(" error=TranslationError")
    assert "+49 151" not in caplog.text
    assert "демонтаж" not in caplog.text


def test_fake_backend_cannot_tell():
    """The fake translator answers None: locally a job keeps its employer's language (R4).

    1. Ask FakeClaudeBackend for the language of the job text
    2. Expect: None
    """
    assert FakeClaudeBackend().detect_language(JOB_TEXT) is None
