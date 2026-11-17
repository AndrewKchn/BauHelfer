"""Integration tests: a chat message's language is found and translated when sent, the other
person reads it translated.

Ticket #36. Spec: docs/specs/chat-translation.md, iteration 1 (R1-R3, R5, R6, R8, D1-D7,
D10), acceptance criteria AC1, AC2, AC4 and AC6; iteration 2, "Show original" per message
(R11-R13, D8), AC7-AC9. The test client runs no JavaScript: the click itself is for the
E2E ticket #40 (R13); iteration 3, the last message on "Chats" in the reader's language
(R14-R16, D11, D12), AC10 and AC11. Each test goes through the whole stack:
middleware, URL, view, form, template and database. The translator is the small class
below, chosen through TRANSLATION_BACKEND; it records its calls, so nothing reaches the
network. Ivan's site is in Ukrainian, Anna's in English, the language of the labels.
"""

from typing import ClassVar

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from chat.models import Message
from jobs.shown_text import ShownText
from jobs.tests.test_application import make_worker
from translations.backends import TranslationError
from translations.models import Translation
from translations.services import source_hash, translate

from .helpers import apply, chat_url

pytestmark = [pytest.mark.django_db, pytest.mark.story(36)]

UKRAINIAN = "Чи є біля будинку парковка?"
LABEL = "Translated from Ukrainian by AI"


class RecordingBackend:
    """Answers "<lang>: <text>" and the prepared `language`; records every call."""

    language: ClassVar = None
    calls: ClassVar[list] = []

    def translate(self, text, target_lang):
        """Record the call and answer with a made-up translation."""
        self.calls.append(("translate", text, target_lang))
        return f"{target_lang}: {text}"

    def detect_language(self, text):
        """Record the call and answer with the prepared language code."""
        self.calls.append(("detect", text))
        return self.language


class UnavailableBackend:
    """A translator that cannot answer, as Claude when the API is down."""

    def translate(self, text, target_lang):
        """Raise TranslationError: the text then stays the original."""
        raise TranslationError("APIConnectionError")

    def detect_language(self, text):
        """Raise TranslationError: the language is then the sender's site language."""
        raise TranslationError("APIConnectionError")


@pytest.fixture(autouse=True)
def recording(settings, worker):
    """Use RecordingBackend for every test here; Ivan's site is in Ukrainian."""
    settings.TRANSLATION_BACKEND = f"{__name__}.RecordingBackend"
    RecordingBackend.language = None
    RecordingBackend.calls = []
    worker.preferred_language = "uk"
    worker.save()
    return RecordingBackend


def send(client, sender, application, text):
    """Log in as `sender` and send `text` in the chat; the redirect is not followed."""
    client.force_login(sender)
    return client.post(chat_url(application), {"text": text})


def say(application, sender, text, language):
    """A saved chat message of `sender`, written in `language`."""
    return Message.objects.create(
        application=application, sender=sender, text=text, original_language=language
    )


def translations_made(recording):
    """The translate calls the backend got, without the detections."""
    return [call for call in recording.calls if call[0] == "translate"]


# Sending: the language is found (R2, D3; AC1)


@pytest.mark.parametrize(
    ("found", "saved"),
    [("uk", "uk"), (None, "uk"), ("", "")],
    ids=["found", "cannot-tell", "other-language"],
)
def test_sent_message_gets_the_language_found(
    client, application, worker, recording, found, saved
):
    """A message is saved with its language; if none is found, the sender's site language.

    1. The translator finds "uk", cannot tell (None), or another language ("")
    2. Send a message as Ivan
    3. Expect: its original language is "uk", "uk" (Ivan's site) or "" (unknown)
    """
    recording.language = found

    send(client, worker, application, UKRAINIAN)

    assert Message.objects.get().original_language == saved
    assert ("detect", UKRAINIAN) in recording.calls


# Sending: the message is translated for the other person (R3, D1, D4, D10; AC2)


def test_message_is_translated_for_the_other_person_when_sent(
    client, application, worker, recording
):
    """Anna's translation is made while Ivan sends, not when Anna reads.

    1. The translator finds "uk"
    2. Send a Ukrainian message as Ivan to Anna, whose site is in English
    3. Expect: one translation into English, saved in the cache
    """
    recording.language = "uk"

    send(client, worker, application, UKRAINIAN)

    assert translations_made(recording) == [("translate", UKRAINIAN, "en")]
    assert Translation.objects.filter(
        source_hash=source_hash(UKRAINIAN), target_language="en"
    ).exists()


def test_employer_message_is_translated_for_the_worker(
    client, application, employer, recording
):
    """The other way round: Anna writes, Ivan's Ukrainian is the target.

    1. The translator finds "en"
    2. Send an English message as Anna
    3. Expect: one translation into Ukrainian
    """
    recording.language = "en"

    send(client, employer, application, "Yes, in the yard.")

    assert translations_made(recording) == [("translate", "Yes, in the yard.", "uk")]


def test_message_in_the_other_persons_language_is_not_translated(
    client, application, worker, recording
):
    """A message already in Anna's language costs no translation (D4).

    1. The translator finds "en", Anna's language
    2. Send a message as Ivan
    3. Expect: no translation call
    """
    recording.language = "en"

    send(client, worker, application, "Is there parking?")

    assert translations_made(recording) == []


def test_failing_translator_does_not_stop_the_message(
    client, application, worker, settings
):
    """Claude down: the message is sent as always (#34 D15, D10).

    1. The translator raises on detection and on translation
    2. Send a message as Ivan
    3. Expect: back to the chat; the message saved with Ivan's site language
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"

    response = send(client, worker, application, UKRAINIAN)

    assertRedirects(response, chat_url(application), fetch_redirect_response=False)
    assert Message.objects.get().original_language == "uk"


# The chat page (R5, R6, D5, D7; AC4)


@pytest.fixture
def anna_client(client, employer):
    """A browser logged in as Anna, whose site is in English."""
    client.force_login(employer)
    return client


def test_reader_sees_the_other_persons_message_translated(
    anna_client, application, worker
):
    """Ivan's Ukrainian message is shown to Anna in English, with its label.

    1. Save Ivan's Ukrainian message
    2. Open the chat as Anna
    3. Expect: the translation and "Translated from Ukrainian by AI"
    """
    say(application, worker, UKRAINIAN, "uk")

    response = anna_client.get(chat_url(application))

    assertContains(response, f"en: {UKRAINIAN}")
    assertContains(response, LABEL)


def test_own_message_is_shown_as_written(client, application, worker, recording):
    """Ivan reads his own message in the original, although it is not in his site's language.

    1. Save Ivan's English message (his site is in Ukrainian)
    2. Open the chat as Ivan
    3. Expect: the original, no translation into Ukrainian, no translator call (D5)
    """
    say(application, worker, "Is there parking?", "en")
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, "Is there parking?")
    assertNotContains(response, "uk: Is there parking?")
    assert translations_made(recording) == []


def test_message_in_the_readers_language_has_no_label(anna_client, application, worker):
    """Ivan wrote in English: Anna reads it as it is (D4).

    1. Save Ivan's English message
    2. Open the chat as Anna
    3. Expect: the message, no "by AI" label
    """
    say(application, worker, "Is there parking?", "en")

    response = anna_client.get(chat_url(application))

    assertContains(response, "Is there parking?")
    assertNotContains(response, "by AI")


def test_message_of_unknown_language_says_translated_by_ai(
    anna_client, application, worker
):
    """A message in a language not among our 7 (or saved before #36, D2) has the short label.

    1. Save Ivan's message with the language ""
    2. Open the chat as Anna
    3. Expect: the translation and "Translated by AI"
    """
    say(application, worker, UKRAINIAN, "")

    response = anna_client.get(chat_url(application))

    assertContains(response, f"en: {UKRAINIAN}")
    assertContains(response, "Translated by AI")


def test_failed_translation_shows_the_original_and_says_so(
    anna_client, application, worker, settings
):
    """Claude down: Anna reads the original and knows why (D10).

    1. The translator raises
    2. Open the chat as Anna with Ivan's Ukrainian message
    3. Expect: the original, "Translation is not available right now.", no label
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"
    say(application, worker, UKRAINIAN, "uk")

    response = anna_client.get(chat_url(application))

    assertContains(response, UKRAINIAN)
    assertContains(response, "Translation is not available right now.")
    assertNotContains(response, LABEL)


def test_template_draws_what_the_rule_decided(
    anna_client, application, worker, monkeypatch
):
    """The template checks no language: it draws the state chat_messages_for() gave (D6).

    1. Save Ivan's Ukrainian message
    2. Make chat_messages_for() say "same" for it, although Anna reads English
    3. Open the chat as Anna
    4. Expect: the original, no label
    """
    say(application, worker, UKRAINIAN, "uk")

    def says_same(messages, reader, reader_lang, **kwargs):
        messages = list(messages)
        for message in messages:
            message.shown = ShownText(message.text, "same", "uk")
        return messages

    monkeypatch.setattr("chat.views.chat_messages_for", says_same)

    response = anna_client.get(chat_url(application))

    assertContains(response, UKRAINIAN)
    assertNotContains(response, "by AI")


def test_poll_with_a_new_message_brings_it_translated(anna_client, application, worker):
    """The open chat's poll draws the new message translated too (R5).

    1. Save Ivan's first message in English and his second in Ukrainian
    2. Poll as Anna with ?after=<id of the first>
    3. Expect: 200 with the translation of the second and its label
    """
    first = say(application, worker, "Hello!", "en")
    say(application, worker, UKRAINIAN, "uk")

    response = anna_client.get(chat_url(application), {"after": first.pk})

    assertContains(response, f"en: {UKRAINIAN}")
    assertContains(response, LABEL)


# Database queries (R8; AC6)


def count_page_queries(client, application):
    """How many SQL queries the chat page makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(chat_url(application))
    assert response.status_code == 200
    return len(queries)


def test_queries_do_not_grow_with_translated_messages(anna_client, application, worker):
    """All cached translations come in one query, however many messages (D6).

    1. Save 1 Ukrainian message, its translation cached; count the page's queries
    2. Save 4 more in Ukrainian, cached too; count again
    3. Expect: the same number of queries (no "N+1")
    """
    say(application, worker, UKRAINIAN, "uk")
    translate(UKRAINIAN, "en")
    with_one = count_page_queries(anna_client, application)

    for n in range(4):
        text = f"Повідомлення {n}"
        say(application, worker, text, "uk")
        translate(text, "en")
    with_five = count_page_queries(anna_client, application)

    assert with_five == with_one


# "Show original" per message (R11-R13, D8; AC7-AC9)


def htmx_link(text, href, url, target):
    """The toggle's <a>: `href` for a plain click, `url` fetched by HTMX into `target`."""
    return (
        f'<a class="link" href="{href}" hx-get="{url}" hx-select="#{target}" '
        f'hx-target="#{target}" hx-swap="outerHTML">{text}</a>'
    )


def test_translated_message_offers_the_original(anna_client, application, worker):
    """ "Show original" links to the chat with this message's id, swapping its block.

    1. Save Ivan's Ukrainian message
    2. Open the chat as Anna
    3. Expect: a link to ?original=<id>#message-<id>, fetched by HTMX into #message-<id>
    """
    message = say(application, worker, UKRAINIAN, "uk")
    page = chat_url(application)

    response = anna_client.get(page)

    assertContains(
        response,
        htmx_link(
            "Show original",
            f"{page}?original={message.pk}#message-{message.pk}",
            f"{page}?original={message.pk}",
            f"message-{message.pk}",
        ),
        html=True,
    )
    assertContains(response, f'id="message-{message.pk}"')


def test_untranslated_messages_offer_no_original(
    anna_client, application, employer, worker
):
    """A message in the reader's language and the reader's own have nothing to switch.

    1. Save Ivan's English message and Anna's own Ukrainian one
    2. Open the chat as Anna
    3. Expect: no "Show original"
    """
    say(application, worker, "Is there parking?", "en")
    say(application, employer, "Так, у дворі.", "uk")

    response = anna_client.get(chat_url(application))

    assertNotContains(response, "Show original")


def test_original_shows_that_message_and_offers_the_translation(
    anna_client, application, worker, recording
):
    """?original=<id> shows that message as written; the other stays translated.

    1. Save two Ukrainian messages of Ivan
    2. Open the chat as Anna with ?original=<first id>
    3. Expect: the first in the original with "Original" and "Show translation" linking to
       the chat without the parameter; the second translated
    4. Expect: no translation of the first message
    """
    first = say(application, worker, UKRAINIAN, "uk")
    say(application, worker, "Дякую!", "uk")
    page = chat_url(application)

    response = anna_client.get(page, {"original": first.pk})

    assertNotContains(response, f"en: {UKRAINIAN}")
    assertContains(response, UKRAINIAN)
    assertContains(response, "Original")
    assertContains(
        response,
        htmx_link(
            "Show translation",
            f"{page}#message-{first.pk}",
            page,
            f"message-{first.pk}",
        ),
        html=True,
    )
    assertContains(response, "en: Дякую!")
    assert ("translate", UKRAINIAN, "en") not in recording.calls


@pytest.mark.parametrize("value", ["abc", "other-chat"])
def test_wrong_original_changes_nothing(
    anna_client, application, employer, worker, value
):
    """A letter or a message id of another chat: the page as without the parameter.

    1. Save Ivan's Ukrainian message, and one in another chat of Anna
    2. Open the chat with ?original=abc or ?original=<the other chat's message id>
    3. Expect: 200, the message translated with "Show original"
    """
    say(application, worker, UKRAINIAN, "uk")
    other_chat = apply(employer, make_worker("olena@example.com"))
    other = say(other_chat, other_chat.worker, "Я одна.", "uk")
    original = other.pk if value == "other-chat" else value

    response = anna_client.get(chat_url(application), {"original": original})

    assertContains(response, f"en: {UKRAINIAN}")
    assertContains(response, "Show original")


def test_poll_asks_without_the_original(anna_client, application, worker):
    """The open chat's poll asks for the chat without ?original= (R13, D8).

    1. Save Ivan's Ukrainian message
    2. Open the chat as Anna with ?original=<its id>
    3. Expect: the message list polls the chat's own path, without the parameter
    """
    message = say(application, worker, UKRAINIAN, "uk")
    page = chat_url(application)

    response = anna_client.get(page, {"original": message.pk})

    assertContains(response, f'hx-get="{page}?after={message.pk}"')


def test_poll_sends_after_in_its_address(anna_client, application, worker):
    """The poll's ?after= must not reach "Show original" (found in my manual check).

    HTMX adds the hx-vals of every parent to a request, also to the links inside the list
    (hx-disinherit does not stop it). With hx-vals {"after": <last id>} on the list, the
    click asked ?original=<id>&after=<id>: nothing newer, so a 204 and no change. The poll
    now has ?after= in its own address, which no link inherits.

    1. Save Ivan's Ukrainian message
    2. Open the chat as Anna
    3. Expect: no hx-vals on the page; the poll asks ?after=<its id> by its address
    """
    message = say(application, worker, UKRAINIAN, "uk")

    response = anna_client.get(chat_url(application))

    assertNotContains(response, "hx-vals")
    assertContains(response, f'hx-get="{chat_url(application)}?after={message.pk}"')


# The last message on "Chats" (R14-R16, D11, D12; AC10, AC11)

CHATS_URL = "/chat/"


def test_chats_row_shows_the_last_message_translated(anna_client, application, worker):
    """Anna reads Ivan's last Ukrainian message in English on "Chats", without a label.

    1. Save Ivan's Ukrainian message
    2. Open "Chats" as Anna
    3. Expect: the translation in the row; no "by AI" label, no "Show original" (D12)
    """
    say(application, worker, UKRAINIAN, "uk")

    response = anna_client.get(CHATS_URL)

    assertContains(response, f"en: {UKRAINIAN}")
    assertNotContains(response, "by AI")
    assertNotContains(response, "Show original")


def test_chats_row_shows_the_own_last_message_as_written(
    client, application, worker, recording
):
    """Ivan's own last message stays as he wrote it on his "Chats" (D5).

    1. Save Ivan's English message (his site is in Ukrainian)
    2. Open "Chats" as Ivan
    3. Expect: the message as written, no translation into Ukrainian, no translator call
    """
    say(application, worker, "Is there parking?", "en")
    client.force_login(worker)

    response = client.get(CHATS_URL)

    assertContains(response, "Is there parking?")
    assertNotContains(response, "uk: Is there parking?")
    assert translations_made(recording) == []


def test_chats_row_cuts_the_translation(anna_client, application, worker):
    """The translation, not the original, is cut to 60 characters (R16).

    1. Save Ivan's long Ukrainian message
    2. Open "Chats" as Anna
    3. Expect: the first 59 characters of "en: <message>" and "…"
    """
    long_text = "Привіт! Чи є біля будинку парковка для бусика? Ми приїдемо о сьомій."
    say(application, worker, long_text, "uk")

    response = anna_client.get(CHATS_URL)

    assertContains(response, f"en: {long_text}"[:59] + "…")


def count_chats_queries(client):
    """How many SQL queries the "Chats" page makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(CHATS_URL)
    assert response.status_code == 200
    return len(queries)


def test_chats_queries_do_not_grow_with_translated_previews(
    anna_client, application, employer, worker
):
    """All cached previews come in one query, however many chats (R16).

    1. One chat with Ivan's Ukrainian message, translated; count the queries of "Chats"
    2. Add two chats of Anna with other workers' Ukrainian messages, translated; count again
    3. Expect: the same number
    """
    say(application, worker, UKRAINIAN, "uk")
    translate(UKRAINIAN, "en")
    with_one = count_chats_queries(anna_client)

    for email in ("olena@example.com", "taras@example.com"):
        other = apply(employer, make_worker(email))
        text = f"Привіт від {email}"
        say(other, other.worker, text, "uk")
        translate(text, "en")
    with_three = count_chats_queries(anna_client)

    assert with_three == with_one
