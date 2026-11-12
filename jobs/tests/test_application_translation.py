"""Unit tests: the application messages as the employer sees them, and forgetting them.

Ticket #33. Spec: docs/specs/application-translation.md, iteration 2 (R10, R13, D5-D7),
acceptance criterion AC8 and the rule behind AC6; iteration 3 (R16), AC11. messages_for()
is called with saved applications and a language, without a request. The translator is
the small class below, chosen through TRANSLATION_BACKEND; it records its calls, so
nothing reaches the network.
"""

from typing import ClassVar

import pytest

from jobs.models import Application
from jobs.shown_text import ShownText, messages_for
from translations.models import Translation
from translations.services import source_hash, translate

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(33)]

UKRAINIAN = "Ми вдвох, 5 років демонтажу."
GERMAN = "Wir sind zu zweit."


class RecordingBackend:
    """A translator that answers "<lang>: <text>" and records each call in `calls`."""

    calls: ClassVar[list] = []

    def translate(self, text, target_lang):
        """Record the call and answer with a made-up translation."""
        self.calls.append((text, target_lang))
        return f"{target_lang}: {text}"


@pytest.fixture(autouse=True)
def recording(settings):
    """Use RecordingBackend for every test here, with an empty list of calls."""
    settings.TRANSLATION_BACKEND = f"{__name__}.RecordingBackend"
    RecordingBackend.calls = []
    return RecordingBackend


@pytest.fixture
def job():
    """An open job of a German employer."""
    return make_job(make_employer("klaus@example.com", preferred_language="de"))


def apply(job, email, message, language):
    """A saved application from a new worker, with its message in `language`."""
    return Application.objects.create(
        job=job,
        worker=make_worker(email),
        message=message,
        original_language=language,
    )


# What the employer sees (R10, D5, D6)


def test_each_message_gets_what_its_reader_should_see(job, recording):
    """A message in another language is translated, one in the reader's is not.

    1. Save a Ukrainian and a German application
    2. Ask for their messages as a German reader
    3. Expect: the Ukrainian one translated, from "uk"; the German one as it is, "same"
    4. Expect: one translator call, for the Ukrainian text
    """
    andrii = apply(job, "andrii@example.com", UKRAINIAN, "uk")
    jonas = apply(job, "jonas@example.com", GERMAN, "de")

    applications = messages_for([andrii, jonas], "de")

    assert [a.shown_message for a in applications] == [
        ShownText(f"de: {UKRAINIAN}", "translated", "uk"),
        ShownText(GERMAN, "same", "de"),
    ]
    assert recording.calls == [(UKRAINIAN, "de")]


def test_a_message_translated_when_sent_costs_no_call(job, recording):
    """A message translated when it was sent (D1) comes from the cache.

    1. Save a Ukrainian application; translate its message into German, as sending does
    2. Ask for its message as a German reader
    3. Expect: the translation, no new translator call
    """
    andrii = apply(job, "andrii@example.com", UKRAINIAN, "uk")
    translate(UKRAINIAN, "de")
    recording.calls.clear()

    (application,) = messages_for([andrii], "de")

    assert application.shown_message.state == "translated"
    assert recording.calls == []


def test_an_empty_message_costs_no_call(job, recording):
    """An application without a message asks the translator nothing.

    1. Save a Ukrainian worker's application without a message
    2. Ask for its message as a German reader
    3. Expect: an empty text, no translator call
    """
    silent = apply(job, "andrii@example.com", "", "uk")

    (application,) = messages_for([silent], "de")

    assert application.shown_message.text == ""
    assert recording.calls == []


# Forgetting (R13, D7; AC8)


def rows_of(text):
    """How many cached translations `text` has."""
    return Translation.objects.filter(source_hash=source_hash(text)).count()


@pytest.mark.parametrize("deleted", ["application", "job", "worker"])
def test_deleting_forgets_the_translations_of_the_message(job, deleted):
    """A deleted application leaves no translation of its message; others keep theirs.

    1. Save a Ukrainian application; translate its message and another text
    2. Delete the application, its job, or the worker's account (CASCADE)
    3. Expect: no rows of the message, the other text's row stays
    """
    andrii = apply(job, "andrii@example.com", UKRAINIAN, "uk")
    translate(UKRAINIAN, "de")
    translate(UKRAINIAN, "pl")
    translate("Ein anderer Text.", "pl")

    {"application": andrii, "job": job, "worker": andrii.worker}[deleted].delete()

    assert rows_of(UKRAINIAN) == 0
    assert rows_of("Ein anderer Text.") == 1


# "Show original" (R16, D8; AC11)


def test_show_original_switches_only_that_message(job, recording):
    """The message asked for is shown in the original, the others stay translated.

    1. Save two Ukrainian applications
    2. Ask for their messages as a German reader, with the first one's id as original_id
    3. Expect: the first in the original, state "original"; the second translated
    4. Expect: one translator call, for the second message only
    """
    andrii = apply(job, "andrii@example.com", UKRAINIAN, "uk")
    olena = apply(job, "olena@example.com", "Я одна.", "uk")

    first, second = messages_for([andrii, olena], "de", original_id=andrii.pk)

    assert first.shown_message == ShownText(UKRAINIAN, "original", "uk")
    assert second.shown_message.state == "translated"
    assert recording.calls == [("Я одна.", "de")]
