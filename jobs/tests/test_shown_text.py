"""Unit tests: the rule "does this reader see the original or a translation?" for any text.

Ticket #33. Spec: docs/specs/application-translation.md, iteration 1 (R2, D5), acceptance
criterion AC1. shown_text() gets plain values, no job and no application: the description
(#32), the application messages (#33) and the chat (#36) all use it. `translated` is a
function, so the tests see whether the rule asked for a translation at all.
"""

import pytest

from jobs.shown_text import ShownText, shown_text
from translations.services import Translated

pytestmark = [pytest.mark.story(33)]

TEXT = "Wir sind zu zweit, 5 Jahre Abbruch."


class Translator:
    """Stands in for translate(): gives `result` and counts how often it was asked."""

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def __call__(self):
        """Count the call and give the prepared result."""
        self.calls += 1
        return self.result


@pytest.fixture
def ok():
    """A translation that worked."""
    return Translator(Translated("pl: " + TEXT, ok=True))


def test_another_language_gets_the_translation(ok):
    """A reader in another language gets the translation, labelled with its source.

    1. Ask for a German text as a Polish reader who is not its author
    2. Expect: the translation, state "translated", from "de", one translation asked for
    """
    result = shown_text(TEXT, "de", "pl", is_author=False, translated=ok)

    assert result == ShownText("pl: " + TEXT, "translated", "de")
    assert ok.calls == 1


def test_failed_translation_gives_the_original():
    """A translation that failed gives the original, state "unavailable".

    1. The translation comes back with ok false (the original)
    2. Ask for a German text as a Polish reader
    3. Expect: the original, state "unavailable"
    """
    failed = Translator(Translated(TEXT, ok=False))

    result = shown_text(TEXT, "de", "pl", is_author=False, translated=failed)

    assert result == ShownText(TEXT, "unavailable", "de")


@pytest.mark.parametrize(
    ("reader", "is_author", "show_original", "state"),
    [
        ("pl", True, False, "own"),  # the author reads their own text
        ("de", False, False, "same"),  # written in the reader's language
        ("pl", False, True, "original"),  # the reader asked for the original
        ("de", True, True, "own"),  # the author wins over the rest
    ],
)
def test_no_translation_is_asked_for(ok, reader, is_author, show_original, state):
    """Own text, the same language, or "Show original": the original, no translation.

    1. Ask for a German text as its author, as a German reader, or with show_original
    2. Expect: the original with the matching state, the translation never asked for
    """
    result = shown_text(
        TEXT,
        "de",
        reader,
        is_author=is_author,
        translated=ok,
        show_original=show_original,
    )

    assert result == ShownText(TEXT, state, "de")
    assert ok.calls == 0


def test_unknown_source_language_is_translated_for_everyone(ok):
    """A text in a language not among our 7 ("") is translated also for German.

    1. Ask for a text of unknown language as a German reader
    2. Expect: the translation, state "translated", label "Translated by AI"
    """
    result = shown_text(TEXT, "", "de", is_author=False, translated=ok)

    assert result.state == "translated"
    assert result.label == "Translated by AI"


def test_label_names_the_source_language(ok):
    """The label is the whole sentence of the source language (job-translation.md D9).

    1. Ask for a Ukrainian text as a German reader
    2. Expect: the label "Translated from Ukrainian by AI"
    """
    result = shown_text(TEXT, "uk", "de", is_author=False, translated=ok)

    assert result.label == "Translated from Ukrainian by AI"
