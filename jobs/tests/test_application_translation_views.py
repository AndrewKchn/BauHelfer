"""Integration tests: a message's language is found when sent, the employer reads it translated.

Ticket #33. Spec: docs/specs/application-translation.md, iteration 2 (R6-R8, R11, R12,
D1, D3-D5, D10), acceptance criteria AC4-AC7 and AC9. Each test goes through the whole
stack: middleware, URL, view, form, template and database. The translator is the small
class below, chosen through TRANSLATION_BACKEND; it records its calls, so nothing reaches
the network.
"""

from typing import ClassVar

import pytest
from django.contrib.messages import get_messages
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from jobs.models import Application
from jobs.shown_text import ShownText
from translations.backends import TranslationError
from translations.models import Translation
from translations.services import source_hash, translate

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(33)]

UKRAINIAN = "Ми вдвох, 5 років демонтажу."
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
        """Raise TranslationError: the language is then the worker's site language."""
        raise TranslationError("APIConnectionError")


@pytest.fixture(autouse=True)
def recording(settings):
    """Use RecordingBackend for every test here: no language found, no calls yet."""
    settings.TRANSLATION_BACKEND = f"{__name__}.RecordingBackend"
    RecordingBackend.language = None
    RecordingBackend.calls = []
    return RecordingBackend


@pytest.fixture
def employer():
    """An employer whose site is in English, the language of the test's labels."""
    return make_employer("klaus@example.com", preferred_language="en")


@pytest.fixture
def job(employer):
    """An open job in English: its owner sees it without any call."""
    return make_job(employer, original_language="en")


@pytest.fixture
def worker():
    """A worker who can apply, with the site in Ukrainian."""
    worker = make_worker("andrii@example.com")
    worker.preferred_language = "uk"
    worker.save()
    return worker


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the job's employer."""
    client.force_login(employer)
    return client


def send(client, worker, job, message):
    """Log in as `worker` and send an application with `message`.

    The redirect is not followed: the job page after it is the worker's, in Ukrainian, and
    would translate the job's description, a call that has nothing to do with sending.
    """
    client.force_login(worker)
    return client.post(
        reverse("job_apply", args=[job.pk]), {"workers_offered": 1, "message": message}
    )


def apply(job, email, message, language):
    """A saved application from a new worker, with its message in `language`."""
    return Application.objects.create(
        job=job, worker=make_worker(email), message=message, original_language=language
    )


def detail_url(job):
    """The job's page."""
    return reverse("job_detail", args=[job.pk])


# Sending: the language is found (R7, D3; AC4)


@pytest.mark.parametrize(
    ("found", "saved"),
    [("uk", "uk"), (None, "uk"), ("", "")],
    ids=["found", "cannot-tell", "other-language"],
)
def test_sent_message_gets_the_language_found(
    client, worker, job, recording, found, saved
):
    """An application is saved with its message's language; if none is found, the worker's.

    1. The translator finds "uk", cannot tell (None), or another language ("")
    2. Send an application with a message
    3. Expect: its original language is "uk", "uk" (the worker's site) or "" (unknown)
    """
    recording.language = found

    send(client, worker, job, UKRAINIAN)

    assert Application.objects.get().original_language == saved
    assert ("detect", UKRAINIAN) in recording.calls


def test_empty_message_asks_nothing(client, worker, job, recording):
    """Without a message there is nothing to detect or translate.

    1. Send an application without a message
    2. Expect: the worker's site language, no translator call
    """
    send(client, worker, job, "")

    assert Application.objects.get().original_language == "uk"
    assert recording.calls == []


# Sending: the message is translated for the employer (R8, D1; AC5)


def test_message_is_translated_for_the_employer_when_sent(
    client, worker, job, recording
):
    """The employer's translation is made while the worker sends, not when Klaus reads.

    1. The translator finds "uk"
    2. Send an application with a Ukrainian message to an English employer
    3. Expect: one translation into English, saved in the cache
    """
    recording.language = "uk"

    send(client, worker, job, UKRAINIAN)

    assert ("translate", UKRAINIAN, "en") in recording.calls
    assert Translation.objects.filter(
        source_hash=source_hash(UKRAINIAN), target_language="en"
    ).exists()


def test_message_in_the_employers_language_is_not_translated(
    client, worker, job, recording
):
    """A message already in the employer's language costs no translation.

    1. The translator finds "en", the employer's language
    2. Send an application
    3. Expect: no translation call
    """
    recording.language = "en"

    send(client, worker, job, "We are two.")

    assert [call for call in recording.calls if call[0] == "translate"] == []


def test_failing_translator_does_not_stop_the_application(
    client, worker, job, settings
):
    """Claude down: the application is sent as always (#34 D15).

    1. The translator raises on detection and on translation
    2. Send an application with a message
    3. Expect: back to the job with a success message ("Application sent." in the
       worker's Ukrainian), the application saved with the worker's language
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"

    response = send(client, worker, job, UKRAINIAN)

    assertRedirects(response, detail_url(job), fetch_redirect_response=False)
    assert [m.level_tag for m in get_messages(response.wsgi_request)] == ["success"]
    assert Application.objects.get().original_language == "uk"


# The employer's page (R11, R12, D4, D5; AC6, AC7)


def test_employer_reads_the_message_translated(employer_client, job):
    """A Ukrainian message is shown in English with its label.

    1. Save a Ukrainian application
    2. Open the job's page as its English employer
    3. Expect: the translation and "Translated from Ukrainian by AI"
    """
    apply(job, "andrii@example.com", UKRAINIAN, "uk")

    response = employer_client.get(detail_url(job))

    assertContains(response, f"en: {UKRAINIAN}")
    assertContains(response, LABEL)


def test_message_in_the_employers_language_has_no_label(employer_client, job):
    """A message in the reader's language is shown as it is, without a label.

    1. Save an English application
    2. Open the page as the English employer
    3. Expect: the message, no "Translated" label
    """
    apply(job, "andrii@example.com", "We are two.", "en")

    response = employer_client.get(detail_url(job))

    assertContains(response, "We are two.")
    assertNotContains(response, "by AI")


def test_message_of_unknown_language_says_translated_by_ai(employer_client, job):
    """A message in a language not among our 7 ("", D10) has the short label.

    1. Save an application whose language is unknown
    2. Open the page as the employer
    3. Expect: the translation and "Translated by AI"
    """
    apply(job, "andrii@example.com", UKRAINIAN, "")

    response = employer_client.get(detail_url(job))

    assertContains(response, f"en: {UKRAINIAN}")
    assertContains(response, "Translated by AI")


def test_failed_translation_shows_the_original_and_says_so(
    employer_client, job, settings
):
    """Claude down: the employer reads the original and knows why.

    1. The translator raises
    2. Open the page with a Ukrainian application
    3. Expect: the original, "Translation is not available right now.", no label
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"
    apply(job, "andrii@example.com", UKRAINIAN, "uk")

    response = employer_client.get(detail_url(job))

    assertContains(response, UKRAINIAN)
    assertContains(response, "Translation is not available right now.")
    assertNotContains(response, LABEL)


def test_template_draws_what_the_rule_decided(employer_client, job, monkeypatch):
    """The template checks no language: it draws the state messages_for() gave (D5).

    1. Save a Ukrainian application
    2. Make messages_for() say "same" for it, although the employer reads English
    3. Open the page as the employer
    4. Expect: the original, no label
    """
    apply(job, "andrii@example.com", UKRAINIAN, "uk")

    def says_same(applications, reader_lang, **kwargs):
        for application in applications:
            application.shown_message = ShownText(application.message, "same", "uk")
        return applications

    monkeypatch.setattr("jobs.views.messages_for", says_same)

    response = employer_client.get(detail_url(job))

    assertContains(response, UKRAINIAN)
    assertNotContains(response, "by AI")


def test_worker_sees_their_own_message_as_written(client, worker, job):
    """The worker reads their message in the original on the job page (D6).

    1. Save the worker's Ukrainian application
    2. Open the job's page as the worker, whose site is in Ukrainian
    3. Expect: the original message, no translation of it
    """
    Application.objects.create(
        job=job, worker=worker, message=UKRAINIAN, original_language="uk"
    )
    client.force_login(worker)

    response = client.get(detail_url(job))

    assertNotContains(response, f"uk: {UKRAINIAN}")


# Database queries (AC9)


def count_page_queries(client, job):
    """How many SQL queries the job's page makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(detail_url(job))
    assert response.status_code == 200
    return len(queries)


def test_queries_do_not_grow_with_translated_messages(employer_client, job):
    """All cached messages come in one query, however many applications (D2).

    1. Save 1 Ukrainian application, its translation cached; count the page's queries
    2. Save 2 more in Romanian and Polish, cached too; count again
    3. Expect: the same number of queries (no "N+1")
    """
    apply(job, "andrii@example.com", UKRAINIAN, "uk")
    translate(UKRAINIAN, "en")
    with_one = count_page_queries(employer_client, job)

    apply(job, "ion@example.com", "Suntem doi.", "ro")
    apply(job, "piotr@example.com", "Jest nas dwóch.", "pl")
    translate("Suntem doi.", "en")
    translate("Jest nas dwóch.", "en")
    with_three = count_page_queries(employer_client, job)

    assert with_three == with_one
