"""Integration tests: translate() gives the original instead of an error or above a limit (#34).

Spec: docs/specs/ai-translation.md, "#34: API errors and cost limits", iteration 1 (R12-R15,
D15-D17, D20), acceptance criteria AC14, AC15, AC17, AC18. The translators are the small
classes below, chosen through TRANSLATION_BACKEND as in test_services.py; they record their
calls, so a test sees whether anything would have been sent to Claude. Nothing here reaches
the network.
"""

from datetime import timedelta
from typing import ClassVar

import pytest
from django.utils import timezone

from translations.backends import TranslationError
from translations.models import Translation
from translations.services import Translated, translate

pytestmark = [pytest.mark.django_db, pytest.mark.story(34)]

JOB_TEXT = "Нужны 2 человека на демонтаж, звонить Ивану +49 151 2345678"


class RecordingBackend:
    """A translator that answers "<lang>: <text>" and records each call in `calls`."""

    calls: ClassVar[list] = []

    def translate(self, text, target_lang):
        """Record the call and answer with a made-up translation."""
        self.calls.append((text, target_lang))
        return f"{target_lang}: {text}"


class UnavailableBackend:
    """A translator that cannot answer, as Claude when the API is down (D20)."""

    calls: ClassVar[list] = []

    def translate(self, text, target_lang):
        """Record the call and raise TranslationError."""
        self.calls.append((text, target_lang))
        raise TranslationError("APIConnectionError")


@pytest.fixture(autouse=True)
def recording_backend(settings):
    """Use RecordingBackend for every test here, with empty lists of calls."""
    settings.TRANSLATION_BACKEND = f"{__name__}.RecordingBackend"
    RecordingBackend.calls = []
    UnavailableBackend.calls = []
    return RecordingBackend


@pytest.fixture
def unavailable(settings):
    """Use UnavailableBackend instead."""
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"
    return UnavailableBackend


def fill_the_day(count, hours_ago=0):
    """Save `count` translations of other texts, made `hours_ago` hours ago."""
    Translation.objects.bulk_create(
        Translation(source_hash=f"{n:064x}", target_language="de", text="schon da")
        for n in range(count)
    )
    if hours_ago:  # created_at is set on save (auto_now_add), so it is moved afterwards
        Translation.objects.update(
            created_at=timezone.now() - timedelta(hours=hours_ago)
        )


def skip_lines(caplog):
    """The messages of the translation log lines at WARNING."""
    return [
        r.getMessage()
        for r in caplog.records
        if r.name.startswith("translations") and r.levelname == "WARNING"
    ]


# The result says whether it is a translation (R12, D15; AC14)


def test_new_translation_is_ok():
    """A translation from the translator comes back with ok true (AC14).

    1. Translate the job text into Polish
    2. Expect: Translated(text="pl: <text>", ok=True)
    """
    assert translate(JOB_TEXT, "pl") == Translated(f"pl: {JOB_TEXT}", ok=True)


def test_cached_translation_is_ok():
    """A translation from the cache comes back with ok true (AC14).

    1. Translate the job text into Polish twice
    2. Expect: the second result is the translation with ok true
    """
    translate(JOB_TEXT, "pl")

    assert translate(JOB_TEXT, "pl") == Translated(f"pl: {JOB_TEXT}", ok=True)


def test_empty_text_is_ok(recording_backend):
    """Empty text has nothing to translate: it comes back with ok true (AC14, D7).

    1. Translate "  " into Polish
    2. Expect: Translated(text="  ", ok=True), no translator call
    """
    assert translate("  ", "pl") == Translated("  ", ok=True)
    assert recording_backend.calls == []


# The translator fails (R13, D15, D20; AC15)


def test_failed_translation_gives_the_original(unavailable):
    """When the translator raises TranslationError, the original comes back (AC15).

    1. Use a translator that raises TranslationError
    2. Translate the job text into Polish
    3. Expect: Translated(text=<the original>, ok=False), no exception
    """
    assert translate(JOB_TEXT, "pl") == Translated(JOB_TEXT, ok=False)


def test_failed_translation_is_not_cached(unavailable):
    """A failure saves no row: the next reader asks the translator again (AC15).

    1. Use a translator that raises TranslationError
    2. Translate the job text into Polish twice
    3. Expect: no row; the translator was asked both times
    """
    translate(JOB_TEXT, "pl")
    translate(JOB_TEXT, "pl")

    assert not Translation.objects.exists()
    assert len(unavailable.calls) == 2


def test_failure_is_logged_without_the_text(unavailable, caplog):
    """The failure is logged with the language, a hash prefix and the error class only.

    1. Use a translator that raises TranslationError("APIConnectionError")
    2. Translate the job text, which has a name and a phone number, into Polish
    3. Expect: one WARNING "Translation failed: lang=pl hash=<12 characters>
       error=TranslationError"
    4. Expect: neither the text, the name nor the phone in the log
    """
    translate(JOB_TEXT, "pl")

    [line] = skip_lines(caplog)
    assert line.startswith("Translation failed: lang=pl hash=")
    assert line.endswith(" error=TranslationError")
    assert len(line.split("hash=")[1].split()[0]) == 12
    for secret in [JOB_TEXT, "Ивану", "2345678"]:
        assert secret not in caplog.text


# Too long (R14, D16; AC17)


def test_text_of_1001_characters_is_not_sent(recording_backend, caplog):
    """A text above 1000 characters is not sent: the original, ok false (AC17).

    1. Translate a text of 1001 characters into Polish
    2. Expect: Translated(text=<the original>, ok=False)
    3. Expect: no translator call, no row
    4. Expect: one WARNING "Translation skipped: reason=too_long lang=pl hash=…"
    """
    text = "x" * 1001

    assert translate(text, "pl") == Translated(text, ok=False)
    assert recording_backend.calls == []
    assert not Translation.objects.exists()
    [line] = skip_lines(caplog)
    assert line.startswith("Translation skipped: reason=too_long lang=pl hash=")


def test_text_of_1000_characters_is_sent(recording_backend):
    """A text of exactly 1000 characters is translated (AC17).

    1. Translate a text of 1000 characters into Polish
    2. Expect: the translation with ok true, one translator call
    """
    text = "x" * 1000

    assert translate(text, "pl") == Translated(f"pl: {text}", ok=True)
    assert len(recording_backend.calls) == 1


def test_long_text_in_the_cache_is_still_returned(settings):
    """A long text translated before the limit comes from the cache (R14).

    1. Translate a text of 1001 characters while the limit is 2000
    2. Set the limit back to 1000
    3. Expect: the cached translation with ok true
    """
    text = "x" * 1001
    settings.TRANSLATION_MAX_LENGTH = 2000
    translate(text, "pl")
    settings.TRANSLATION_MAX_LENGTH = 1000

    assert translate(text, "pl") == Translated(f"pl: {text}", ok=True)


# The daily limit (R15, D17; AC18)


def test_new_text_is_not_sent_after_300_today(recording_backend, caplog):
    """With 300 translations in the last 24 hours, a new text is not sent (AC18).

    1. Save 300 translations of other texts now
    2. Translate the job text into Polish
    3. Expect: the original with ok false, no translator call, no new row
    4. Expect: one WARNING "Translation skipped: reason=daily_limit lang=pl hash=…"
    """
    fill_the_day(300)

    assert translate(JOB_TEXT, "pl") == Translated(JOB_TEXT, ok=False)
    assert recording_backend.calls == []
    assert Translation.objects.count() == 300
    [line] = skip_lines(caplog)
    assert line.startswith("Translation skipped: reason=daily_limit lang=pl hash=")


def test_299_today_still_translates(recording_backend):
    """With 299 translations in the last 24 hours, the 300th is made (AC18).

    1. Save 299 translations of other texts now
    2. Translate the job text into Polish
    3. Expect: the translation with ok true, one translator call
    """
    fill_the_day(299)

    assert translate(JOB_TEXT, "pl").ok
    assert len(recording_backend.calls) == 1


def test_translations_older_than_24_hours_do_not_count(recording_backend):
    """Only the last 24 hours count: 300 rows of yesterday do not stop a new text (AC18).

    1. Save 300 translations made 25 hours ago
    2. Translate the job text into Polish
    3. Expect: the translation with ok true, one translator call
    """
    fill_the_day(300, hours_ago=25)

    assert translate(JOB_TEXT, "pl").ok
    assert len(recording_backend.calls) == 1


def test_cached_text_is_returned_above_the_limit(recording_backend):
    """Above the limit, a text already in the cache still comes back translated (AC18).

    1. Translate the job text into Polish
    2. Save 300 more translations now
    3. Translate the job text into Polish again
    4. Expect: the translation with ok true, still one translator call
    """
    translate(JOB_TEXT, "pl")
    fill_the_day(300)

    assert translate(JOB_TEXT, "pl") == Translated(f"pl: {JOB_TEXT}", ok=True)
    assert len(recording_backend.calls) == 1


def test_limits_are_1000_characters_and_300_a_day(settings):
    """The settings hold the agreed numbers (D16, D17).

    1. Read the settings
    2. Expect: TRANSLATION_MAX_LENGTH 1000, TRANSLATION_DAILY_LIMIT 300
    """
    assert settings.TRANSLATION_MAX_LENGTH == 1000
    assert settings.TRANSLATION_DAILY_LIMIT == 300
