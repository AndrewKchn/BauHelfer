"""Unit tests: translate_many() reads the cached translations of many texts in one query.

Ticket #33. Spec: docs/specs/application-translation.md, iteration 2 (R9, D2), acceptance
criterion AC3. A job page lists many applications; one query for all their cached messages
keeps the page's queries from growing with them ("N+1", applications-list.md D7). The
translator is the small class below, chosen through TRANSLATION_BACKEND; it records its
calls, so nothing reaches the network.
"""

from typing import ClassVar

import pytest

from translations.backends import TranslationError
from translations.models import Translation
from translations.services import Translated, source_hash, translate_many

pytestmark = [pytest.mark.django_db, pytest.mark.story(33)]


class RecordingBackend:
    """A translator that answers "<lang>: <text>" and records each call in `calls`."""

    calls: ClassVar[list] = []

    def translate(self, text, target_lang):
        """Record the call and answer with a made-up translation."""
        self.calls.append((text, target_lang))
        return f"{target_lang}: {text}"


class UnavailableBackend:
    """A translator that cannot answer, as Claude when the API is down."""

    def translate(self, text, target_lang):
        """Raise TranslationError: the text then comes back as the original."""
        raise TranslationError("APIConnectionError")


@pytest.fixture(autouse=True)
def recording(settings):
    """Use RecordingBackend for every test here, with an empty list of calls."""
    settings.TRANSLATION_BACKEND = f"{__name__}.RecordingBackend"
    RecordingBackend.calls = []
    return RecordingBackend


def cache(text, lang, translated):
    """Save a translation as translate() would."""
    Translation.objects.create(
        source_hash=source_hash(text), target_language=lang, text=translated
    )


def test_cached_texts_cost_one_query(recording, django_assert_num_queries):
    """Three cached texts come back in one query, without the translator.

    1. Cache German translations of three texts
    2. Ask for all three in German, counting the queries
    3. Expect: their translations, 1 query, no translator call
    """
    texts = ["Ми вдвох.", "Suntem trei.", "Mam samochód."]
    for text in texts:
        cache(text, "de", f"cached: {text}")

    with django_assert_num_queries(1):
        result = translate_many(texts, "de")

    assert result == {text: Translated(f"cached: {text}", ok=True) for text in texts}
    assert recording.calls == []


def test_a_translation_into_another_language_is_not_used():
    """The cache row of another language is not this reader's translation.

    1. Cache a Polish translation of a text
    2. Ask for the text in German
    3. Expect: a new German translation, not the Polish one
    """
    cache("Suntem trei.", "pl", "Jest nas trzech.")

    result = translate_many(["Suntem trei."], "de")

    assert result == {"Suntem trei.": Translated("de: Suntem trei.", ok=True)}


def test_a_text_not_cached_is_translated_and_saved(recording):
    """A text missing from the cache goes to the translator, as with translate().

    1. Cache one text; leave another out
    2. Ask for both in German
    3. Expect: the cached one as it was, the other translated and now in the cache
    """
    cache("Ми вдвох.", "de", "Wir sind zu zweit.")

    result = translate_many(["Ми вдвох.", "Suntem trei."], "de")

    assert result["Ми вдвох."] == Translated("Wir sind zu zweit.", ok=True)
    assert result["Suntem trei."] == Translated("de: Suntem trei.", ok=True)
    assert recording.calls == [("Suntem trei.", "de")]
    assert Translation.objects.filter(source_hash=source_hash("Suntem trei.")).exists()


def test_a_failing_translator_gives_the_original(settings):
    """A translation that cannot be made gives the original with ok false (#34 D15).

    1. The translator raises TranslationError
    2. Ask for a text that is not cached
    3. Expect: the original text, ok false
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"

    result = translate_many(["Suntem trei."], "de")

    assert result == {"Suntem trei.": Translated("Suntem trei.", ok=False)}


def test_empty_and_repeated_texts(recording):
    """An empty text comes back as it is; a repeated one is translated once.

    1. Ask for "", and the same text twice, in German
    2. Expect: "" unchanged and ok, the text translated, one translator call
    """
    result = translate_many(["", "Suntem trei.", "Suntem trei."], "de")

    assert result == {
        "": Translated("", ok=True),
        "Suntem trei.": Translated("de: Suntem trei.", ok=True),
    }
    assert recording.calls == [("Suntem trei.", "de")]


def test_no_texts_no_query(django_assert_num_queries):
    """A job without applications costs no query.

    1. Ask for an empty list of texts
    2. Expect: an empty dict, 0 queries
    """
    with django_assert_num_queries(0):
        assert translate_many([], "de") == {}


def test_unknown_language_is_refused():
    """A target language not among the site's is a programming error, as in translate().

    1. Ask for a text in "xx"
    2. Expect: ValueError
    """
    with pytest.raises(ValueError, match="xx"):
        translate_many(["Suntem trei."], "xx")
