"""Integration tests: translate() and forget() with the real database and a fake translator (#31).

Spec: docs/specs/ai-translation.md, iteration 1 (R1-R5, D3, D5-D8), acceptance criteria
AC1-AC7. The translator is `RecordingBackend` below, chosen through the setting
TRANSLATION_BACKEND as production chooses Claude (D5): it answers like a translator and
remembers every call, so a test sees whether the cache or the translator answered.
Nothing here reaches the network.
"""

import hashlib
from typing import ClassVar

import pytest

from translations.models import Translation
from translations.services import forget, translate

pytestmark = [pytest.mark.django_db, pytest.mark.story(31)]

JOB_TEXT = "Нужны 2 человека на демонтаж, звонить Ивану +49 151 2345678"


class RecordingBackend:
    """A translator that answers "<lang>: <text>" and records each call in `calls`."""

    # One list for all instances: the service creates a new translator for each call.
    calls: ClassVar[list] = []

    def translate(self, text, target_lang):
        """Record the call and answer with a made-up translation."""
        self.calls.append((text, target_lang))
        return f"{target_lang}: {text}"


@pytest.fixture(autouse=True)
def recording_backend(settings):
    """Use RecordingBackend for every test here, with an empty list of calls."""
    settings.TRANSLATION_BACKEND = f"{__name__}.RecordingBackend"
    RecordingBackend.calls = []
    return RecordingBackend


# Translating and the cache (R2; AC1-AC3)


def test_translate_returns_the_translators_answer(recording_backend):
    """translate() returns what the translator answered (AC1).

    1. Translate the Russian job text into Polish
    2. Expect: the translator's answer "pl: <text>"
    3. Expect: the translator was called once, with the text and "pl"
    """
    assert translate(JOB_TEXT, "pl").text == f"pl: {JOB_TEXT}"
    assert recording_backend.calls == [(JOB_TEXT, "pl")]


def test_second_translation_comes_from_the_cache(recording_backend):
    """The same text and language twice: the translator is asked only once (AC2).

    1. Translate the job text into Polish twice
    2. Expect: both answers are the same
    3. Expect: one translator call and one row in the database
    """
    first = translate(JOB_TEXT, "pl").text
    second = translate(JOB_TEXT, "pl").text

    assert first == second == f"pl: {JOB_TEXT}"
    assert len(recording_backend.calls) == 1
    assert Translation.objects.count() == 1


def test_cache_answers_without_the_translator(recording_backend):
    """A saved translation is returned as saved, whatever the translator would say (AC2).

    1. Translate the job text into German once
    2. Change the saved row's text by hand
    3. Translate again
    4. Expect: the changed text, and still only one translator call
    """
    translate(JOB_TEXT, "de")
    Translation.objects.update(text="Aus dem Cache")

    assert translate(JOB_TEXT, "de").text == "Aus dem Cache"
    assert len(recording_backend.calls) == 1


def test_another_language_is_a_new_translation(recording_backend):
    """The same text in another language asks the translator again (AC3).

    1. Translate the job text into Polish, then into German
    2. Expect: two calls, one per language, and two rows
    """
    translate(JOB_TEXT, "pl")
    translate(JOB_TEXT, "de")

    assert recording_backend.calls == [(JOB_TEXT, "pl"), (JOB_TEXT, "de")]
    assert Translation.objects.count() == 2


class RacingBackend:
    """A translator during whose call another request saves the same translation first."""

    def translate(self, text, target_lang):
        """Save "first" as the other request would, then answer "second"."""
        Translation.objects.create(
            source_hash=hashlib.sha256(text.encode()).hexdigest(),
            target_language=target_lang,
            text="first",
        )
        return "second"


def test_two_requests_at_once_keep_one_translation(settings):
    """Two requests translate the same text at the same instant: both see one row (R1).

    1. Use a translator during whose call another request saves "first"
    2. Translate the job text into Polish
    3. Expect: "first", the saved row, not this call's "second"; one row, no error
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.RacingBackend"

    assert translate(JOB_TEXT, "pl").text == "first"
    assert Translation.objects.count() == 1


class BrokenBackend:
    """A translator with a bug: it raises something that is not a TranslationError."""

    def translate(self, text, target_lang):
        """Raise instead of answering."""
        raise RuntimeError("a bug in the translator")


def test_bug_in_the_translator_is_raised_not_cached(settings):
    """A bug in the translator reaches the caller and nothing is saved (D20).

    Changed by #34: a TranslationError gives the original (test_errors_and_limits.py);
    any other error is a bug and stays visible.

    1. Use a translator that raises RuntimeError
    2. Translate the job text into Polish
    3. Expect: the error is raised; no row, so the next call asks the translator again
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.BrokenBackend"

    with pytest.raises(RuntimeError):
        translate(JOB_TEXT, "pl")

    assert not Translation.objects.exists()


# What is not translated (D7, D8; AC4, AC5)


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_empty_text_is_returned_unchanged(recording_backend, text):
    """Empty or whitespace-only text comes back as it is: no call, no row (AC4, D7).

    1. Translate empty or whitespace-only text into Polish
    2. Expect: the same text back
    3. Expect: no translator call, no row
    """
    assert translate(text, "pl").text == text
    assert recording_backend.calls == []
    assert not Translation.objects.exists()


@pytest.mark.parametrize("lang", ["fr", "PL", "pl-pl", ""])
def test_unknown_language_is_refused(recording_backend, lang):
    """A language that is not one of our 7 codes raises ValueError (AC5, D8).

    1. Translate the job text into French, "PL", "pl-pl" or ""
    2. Expect: ValueError
    3. Expect: no translator call, no row
    """
    with pytest.raises(ValueError):
        translate(JOB_TEXT, lang)

    assert recording_backend.calls == []
    assert not Translation.objects.exists()


@pytest.mark.parametrize("lang", ["de", "en", "ru", "uk", "pl", "ro", "tr"])
def test_each_of_our_languages_is_accepted(recording_backend, lang):
    """Every language of the site can be a target, English too (D8).

    1. Translate the job text into one of the 7 languages
    2. Expect: the translator's answer for that language
    """
    assert translate(JOB_TEXT, lang).text == f"{lang}: {JOB_TEXT}"


# What is stored (R1, D6; AC7)


def test_row_stores_the_hash_not_the_source_text():
    """The database keeps the SHA-256 of the text and the translation, not the text (AC7).

    1. Translate the job text, which has a name and a phone number, into Polish
    2. Expect: the row's source_hash is the SHA-256 hex of the text, its language "pl"
    3. Expect: no field of the row is the source text
    """
    translate(JOB_TEXT, "pl")

    row = Translation.objects.get()
    assert row.source_hash == hashlib.sha256(JOB_TEXT.encode()).hexdigest()
    assert row.target_language == "pl"
    values = [getattr(row, field.attname) for field in Translation._meta.fields]
    assert JOB_TEXT not in values


# Forgetting a text (R3, D3; AC6)


def test_forget_removes_the_text_in_every_language(recording_backend):
    """forget(text) deletes its translations in every language, and only them (AC6).

    1. Translate the job text into Polish and German, and another text into Polish
    2. Call forget() with the job text
    3. Expect: only the other text's row is left
    4. Translate the job text into Polish again
    5. Expect: the translator is called again for it
    """
    translate(JOB_TEXT, "pl")
    translate(JOB_TEXT, "de")
    translate("Gerüstbau ab Montag", "pl")

    forget(JOB_TEXT)

    other_hash = hashlib.sha256("Gerüstbau ab Montag".encode()).hexdigest()
    assert list(Translation.objects.values_list("source_hash", flat=True)) == [
        other_hash
    ]
    translate(JOB_TEXT, "pl")
    assert recording_backend.calls[-1] == (JOB_TEXT, "pl")
    assert len(recording_backend.calls) == 4


def test_forget_of_an_unknown_text_does_nothing():
    """forget() of a text that was never translated changes nothing and does not fail (AC6).

    1. Translate the job text into Polish
    2. Call forget() with another text
    3. Expect: the job text's row is still there
    """
    translate(JOB_TEXT, "pl")

    forget("Never translated")

    assert Translation.objects.count() == 1
