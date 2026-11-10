"""Unit tests: what the job page shows of a description, and forgetting its translations.

Ticket #32. Spec: docs/specs/job-translation.md, iteration 1 (R6, R7, D7, D8, D10, D12),
acceptance criteria AC5 (deleting) and AC6. description_for() is called with a job and a
language, without a request; its translations go through translate() and its cache
(the database). The translators are the small classes below, chosen through
TRANSLATION_BACKEND; nothing reaches the network.
"""

from typing import ClassVar

import pytest

from jobs.descriptions import Description, description_for
from translations.backends import TranslationError
from translations.models import Translation
from translations.services import source_hash, translate

from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(32)]

GERMAN_TEXT = "Trennwand im 3. Stock abreißen, Schutt in den Container tragen."


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
        """Raise TranslationError: translate() then gives the original, `ok` false."""
        raise TranslationError("APIConnectionError")


@pytest.fixture(autouse=True)
def recording(settings):
    """Use RecordingBackend for every test here, with an empty list of calls."""
    settings.TRANSLATION_BACKEND = f"{__name__}.RecordingBackend"
    RecordingBackend.calls = []
    return RecordingBackend


@pytest.fixture
def job():
    """An open job written in German."""
    employer = make_employer("anna@example.com", preferred_language="de")
    return make_job(employer, description=GERMAN_TEXT, original_language="de")


# What the page shows (R7, D7, D8, D10; AC6)


def test_another_language_gets_the_translation(job, recording):
    """A reader in another language gets the translation, labelled with its source.

    1. Ask for the German job's description in Polish
    2. Expect: the translation, state "translated", from "de", one translator call
    """
    result = description_for(job, "pl", is_owner=False)

    assert result == Description(f"pl: {GERMAN_TEXT}", "translated", "de")
    assert recording.calls == [(GERMAN_TEXT, "pl")]


def test_unknown_source_language_is_translated_for_everyone(job, recording):
    """A description in a language not among our 7 is translated also for German (D3).

    1. Mark the job's language as unknown ("")
    2. Ask for its description in German
    3. Expect: the translation, state "translated", from ""
    """
    job.original_language = ""

    result = description_for(job, "de", is_owner=False)

    assert result == Description(f"de: {GERMAN_TEXT}", "translated", "")


def test_same_language_is_not_translated(job, recording):
    """A reader in the description's own language gets it as it is, no call (D8).

    1. Ask for the German job's description in German
    2. Expect: the original, state "same", no translator call
    """
    result = description_for(job, "de", is_owner=False)

    assert result == Description(GERMAN_TEXT, "same", "de")
    assert recording.calls == []


def test_owner_sees_their_own_text(job, recording):
    """The job's employer gets their own text in any language, no call (D7).

    1. Ask for the German job's description in Polish, as its owner
    2. Expect: the original, state "own", no translator call
    """
    result = description_for(job, "pl", is_owner=True)

    assert result == Description(GERMAN_TEXT, "own", "de")
    assert recording.calls == []


def test_failed_translation_shows_the_original(job, settings):
    """A translation that cannot be made gives the original, not labelled translated (D10).

    1. The translator raises TranslationError
    2. Ask for the German job's description in Polish
    3. Expect: the original, state "unavailable"
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"

    result = description_for(job, "pl", is_owner=False)

    assert result == Description(GERMAN_TEXT, "unavailable", "de")


# Forgetting translations when the job goes (R6, D12; AC5)


def rows_of(text):
    """How many cached translations `text` has."""
    return Translation.objects.filter(source_hash=source_hash(text)).count()


def test_deleting_a_job_forgets_its_translations(job):
    """A deleted job leaves no translation of its description; other texts keep theirs.

    1. Translate the German job's description into Polish and Russian, and another text
    2. Delete the job
    3. Expect: no rows of the description, the other text's row stays
    """
    translate(GERMAN_TEXT, "pl")
    translate(GERMAN_TEXT, "ru")
    translate("Ein anderer Text.", "pl")

    job.delete()

    assert rows_of(GERMAN_TEXT) == 0
    assert rows_of("Ein anderer Text.") == 1


def test_deleting_the_employer_forgets_the_translations(job):
    """Deleting an account deletes its jobs (CASCADE), and their translations with them.

    1. Translate the German job's description into Polish
    2. Delete the job's employer
    3. Expect: no rows of the description
    """
    translate(GERMAN_TEXT, "pl")

    job.employer.delete()

    assert rows_of(GERMAN_TEXT) == 0
