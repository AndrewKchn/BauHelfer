"""Unit tests: chat messages as their reader sees them, and forgetting them.

Ticket #36. Spec: docs/specs/chat-translation.md, iteration 1 (R4, R7, D4-D6, D9),
acceptance criteria AC3 and AC5. chat_messages_for() is called with saved messages, a
reader and a language, without a request. The translator is the small class below, chosen
through TRANSLATION_BACKEND; it records its calls, so nothing reaches the network.
"""

from typing import ClassVar

import pytest

from chat.models import Message
from chat.shown_text import chat_messages_for
from jobs.shown_text import ShownText
from translations.backends import TranslationError
from translations.models import Translation
from translations.services import source_hash, translate

pytestmark = [pytest.mark.django_db, pytest.mark.story(36)]

UKRAINIAN = "Чи є біля будинку парковка?"
GERMAN = "Ja, im Hof."


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
        """Raise TranslationError: the text then stays the original."""
        raise TranslationError("APIConnectionError")


@pytest.fixture(autouse=True)
def recording(settings):
    """Use RecordingBackend for every test here, with an empty list of calls."""
    settings.TRANSLATION_BACKEND = f"{__name__}.RecordingBackend"
    RecordingBackend.calls = []
    return RecordingBackend


def say(application, sender, text, language):
    """A saved chat message of `sender`, written in `language`."""
    return Message.objects.create(
        application=application, sender=sender, text=text, original_language=language
    )


# What each reader sees (R4, D4, D5)


def test_each_message_gets_what_its_reader_should_see(
    application, employer, worker, recording
):
    """The other person's message in another language is translated, the rest is not.

    1. Save Ivan's Ukrainian question, Anna's German answer and Anna's own Ukrainian line
    2. Ask for the messages as Anna, reading German
    3. Expect: Ivan's question translated from "uk"; Anna's German answer and her
       Ukrainian line as written, "own" (her own texts, whatever their language)
    4. Expect: one translator call, for Ivan's question
    """
    question = say(application, worker, UKRAINIAN, "uk")
    answer = say(application, employer, GERMAN, "de")
    own_ukrainian = say(application, employer, "Дякую!", "uk")

    messages = chat_messages_for([question, answer, own_ukrainian], employer, "de")

    assert [m.shown for m in messages] == [
        ShownText(f"de: {UKRAINIAN}", "translated", "uk"),
        ShownText(GERMAN, "own", "de"),
        ShownText("Дякую!", "own", "uk"),
    ]
    assert recording.calls == [(UKRAINIAN, "de")]


def test_message_in_the_readers_language_is_not_translated(
    application, employer, worker, recording
):
    """The other person wrote in the reader's language: shown as it is, no call (D4).

    1. Save Ivan's message in German
    2. Ask for it as Anna, reading German
    3. Expect: the text as written, state "same"; no translator call
    """
    message = say(application, worker, GERMAN, "de")

    (shown,) = chat_messages_for([message], employer, "de")

    assert shown.shown == ShownText(GERMAN, "same", "de")
    assert recording.calls == []


def test_the_author_is_decided_per_message(application, employer, worker):
    """The same chat read by the other side: now Anna's text is the translated one (D5).

    1. Save Ivan's Ukrainian question and Anna's German answer
    2. Ask for the messages as Ivan, reading Ukrainian
    3. Expect: his question "own"; Anna's answer translated from "de"
    """
    question = say(application, worker, UKRAINIAN, "uk")
    answer = say(application, employer, GERMAN, "de")

    messages = chat_messages_for([question, answer], worker, "uk")

    assert [m.shown.state for m in messages] == ["own", "translated"]
    assert messages[1].shown.text == f"uk: {GERMAN}"


def test_a_message_translated_when_sent_costs_no_call(
    application, employer, worker, recording
):
    """A message translated when it was sent (D1) comes from the cache.

    1. Save Ivan's Ukrainian message; translate it into German, as sending does
    2. Ask for it as Anna, reading German
    3. Expect: the translation, no new translator call
    """
    message = say(application, worker, UKRAINIAN, "uk")
    translate(UKRAINIAN, "de")
    recording.calls.clear()

    (shown,) = chat_messages_for([message], employer, "de")

    assert shown.shown.state == "translated"
    assert recording.calls == []


def test_failed_translation_gives_the_original(application, employer, worker, settings):
    """Claude down: the reader gets the original, marked unavailable (D10).

    1. The translator raises
    2. Ask for Ivan's Ukrainian message as Anna, reading German
    3. Expect: the original text, state "unavailable"
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"
    message = say(application, worker, UKRAINIAN, "uk")

    (shown,) = chat_messages_for([message], employer, "de")

    assert shown.shown == ShownText(UKRAINIAN, "unavailable", "uk")


# Forgetting (R7, D9; AC5)


def rows_of(text):
    """How many cached translations `text` has."""
    return Translation.objects.filter(source_hash=source_hash(text)).count()


@pytest.mark.parametrize("deleted", ["message", "application", "job", "worker"])
def test_deleting_forgets_the_translations_of_the_message(application, worker, deleted):
    """A deleted message leaves no translation of its text; other texts keep theirs.

    1. Save Ivan's Ukrainian message; translate it and another text
    2. Delete the message, its application, its job, or Ivan's account (CASCADE)
    3. Expect: no rows of the message's text, the other text's row stays
    """
    message = say(application, worker, UKRAINIAN, "uk")
    translate(UKRAINIAN, "de")
    translate(UKRAINIAN, "en")
    translate("Ein anderer Text.", "en")

    {
        "message": message,
        "application": application,
        "job": application.job,
        "worker": worker,
    }[deleted].delete()

    assert rows_of(UKRAINIAN) == 0
    assert rows_of("Ein anderer Text.") == 1
