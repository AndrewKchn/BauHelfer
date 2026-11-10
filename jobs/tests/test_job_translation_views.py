"""Integration tests: a job's language is found on save, its page shows the translation.

Ticket #32. Spec: docs/specs/job-translation.md, iteration 1 (R5-R9, D2, D3, D7-D12),
acceptance criteria AC3, AC4, AC5 (editing), AC7, AC8. Each test goes through the whole
stack: middleware, URL, view, form, template and database. The translator is the small
class below, chosen through TRANSLATION_BACKEND; it records its calls, so nothing reaches
the network.
"""

from typing import ClassVar

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Job
from translations.backends import TranslationError
from translations.models import Translation
from translations.services import source_hash

from .test_job_detail_views import add_photos, detail_url
from .test_views import form_data, make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(32)]

GERMAN_TEXT = "Trennwand im 3. Stock abreißen, Schutt in den Container tragen."
LABEL = "Translated from German by AI"


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
        """Raise TranslationError: the page then shows the original."""
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
    """An employer whose site is in German."""
    return make_employer("anna@example.com", preferred_language="de")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the employer."""
    client.force_login(employer)
    return client


@pytest.fixture
def job(employer):
    """An open job written in German."""
    return make_job(employer, description=GERMAN_TEXT, original_language="de")


def as_guest_in(client, code):
    """The test client as a guest who chose `code` in the language switcher."""
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = code
    return client


def detections(recording):
    """The texts the translator was asked the language of."""
    return [call[1] for call in recording.calls if call[0] == "detect"]


# Posting and editing: the language is found (R5, D2, D3, D11; AC3, AC4)


@pytest.mark.parametrize(
    ("found", "saved"),
    [("ru", "ru"), (None, "de"), ("", "")],
    ids=["found", "cannot-tell", "other-language"],
)
def test_posted_job_gets_the_language_found(employer_client, recording, found, saved):
    """A new job is saved with the language found; when none is found, the employer's.

    1. Log in as an employer whose site is in German
    2. The translator finds "ru", cannot tell (None), or finds another language ("")
    3. Post a job
    4. Expect: its original language is "ru", "de" (the employer's) or "" (unknown)
    5. Expect: the translator was asked once, with the description
    """
    recording.language = found

    employer_client.post(reverse("job_create"), form_data())

    assert Job.objects.get().original_language == saved
    assert detections(recording) == [form_data()["description"]]


def test_editing_without_a_new_description_asks_nothing(
    employer_client, job, recording
):
    """A changed rate keeps the language; the translator is not asked (D11).

    1. Log in as the job's employer
    2. Send the edit form with the same description and a new rate
    3. Expect: no detection, the language is still "de"
    """
    data = form_data(description=GERMAN_TEXT, hourly_rate="22.00")

    employer_client.post(reverse("job_edit", args=[job.pk]), data)

    job.refresh_from_db()
    assert job.hourly_rate == 22
    assert detections(recording) == []
    assert job.original_language == "de"


@pytest.mark.parametrize(
    ("found", "saved"), [("ru", "ru"), (None, "de")], ids=["found", "cannot-tell"]
)
def test_new_description_gets_its_language_found(
    employer_client, job, recording, found, saved
):
    """A changed description is asked about; None keeps the language the job had.

    1. Log in as the job's employer
    2. The translator finds "ru" or cannot tell
    3. Send the edit form with a Russian description
    4. Expect: one detection with the new text; the language is "ru", or still "de"
    """
    recording.language = found
    data = form_data(description="Снести перегородку на 3 этаже.")

    employer_client.post(reverse("job_edit", args=[job.pk]), data)

    job.refresh_from_db()
    assert detections(recording) == ["Снести перегородку на 3 этаже."]
    assert job.original_language == saved


def test_new_description_forgets_the_old_translations(employer_client, job):
    """The old description's translations are deleted when the description changes (D12).

    1. A Polish guest, in a browser of their own, opens the job: its German description
       is translated and cached
    2. The employer sends the edit form with a new description
    3. Expect: no cached translation of the old description is left
    """
    as_guest_in(Client(), "pl").get(detail_url(job))
    assert Translation.objects.filter(source_hash=source_hash(GERMAN_TEXT)).exists()

    employer_client.post(
        reverse("job_edit", args=[job.pk]), form_data(description="Neuer Text.")
    )

    assert not Translation.objects.filter(source_hash=source_hash(GERMAN_TEXT)).exists()


# The job page (R7-R9, D3, D7, D8, D10; AC7)


def test_reader_in_another_language_gets_the_translation(client, job):
    """A Polish guest reads the German job in Polish, labelled as translated by AI.

    1. As a guest with the Polish cookie, open the German job's page
    2. Expect: the translation (the fake answer "pl: <text>") inside #description
    3. Expect: the label "Translated from German by AI" in Polish, with 文A
    """
    response = as_guest_in(client, "pl").get(detail_url(job))

    assertContains(response, 'id="description"')
    assertContains(response, f"pl: {GERMAN_TEXT}")
    assertContains(response, "Przetłumaczono przez AI z niemieckiego")
    assertContains(response, "文A")


def test_unknown_language_is_labelled_without_a_name(client, job):
    """A job in a language not among our 7 says only "Translated by AI" (D3).

    1. Mark the job's language as unknown ("")
    2. As a guest with the German cookie, open its page
    3. Expect: the translation into German and "Von KI übersetzt" (Translated by AI)
    """
    job.original_language = ""
    job.save()

    response = as_guest_in(client, "de").get(detail_url(job))

    assertContains(response, f"de: {GERMAN_TEXT}")
    assertContains(response, "Von KI übersetzt")


def test_reader_in_the_same_language_gets_the_original(client, job, recording):
    """A German guest reads the German job as it is, without a label or a call (D8).

    1. As a guest with the German cookie, open the German job's page
    2. Expect: the original text, no "文A" label, no translator call
    """
    response = as_guest_in(client, "de").get(detail_url(job))

    assertContains(response, GERMAN_TEXT)
    assertNotContains(response, "文A")
    assert recording.calls == []


def test_owner_reads_their_own_text(employer, job, client, recording):
    """The employer reads their own job in the original, whatever their language (D7).

    1. Change the employer's language to Polish and log in as them
    2. Open their German job's page
    3. Expect: the original text, no label, no translator call
    """
    employer.preferred_language = "pl"
    employer.save()
    client.force_login(employer)

    response = client.get(detail_url(job))

    assertContains(response, GERMAN_TEXT)
    assertNotContains(response, "文A")
    assert recording.calls == []


def test_failed_translation_shows_the_original_and_says_so(client, job, settings):
    """When the translation fails, the page shows the original and why (D10).

    1. The translator raises TranslationError
    2. As a guest with the English cookie, open the German job's page
    3. Expect: status 200, the original text, "Translation is not available right
       now.", and no "Translated from" label
    """
    settings.TRANSLATION_BACKEND = f"{__name__}.UnavailableBackend"

    response = as_guest_in(client, "en").get(detail_url(job))

    assert response.status_code == 200
    assertContains(response, GERMAN_TEXT)
    assertContains(response, "Translation is not available right now.")
    assertNotContains(response, LABEL)


# Database queries (AC8)


@pytest.mark.parametrize("photos", [0, 3])
def test_translated_page_needs_one_more_query(
    client, job, django_assert_num_queries, photos
):
    """A cached translation costs one query more than the page of #19, photos or not.

    1. Give the job 0 or 3 photos
    2. As a guest with the English cookie, open the page once: the translation is saved
    3. Open it again and count the queries
    4. Expect: 3 queries — the job, the photos and the cached translation
    """
    add_photos(job, photos)
    as_guest_in(client, "en").get(detail_url(job))

    with django_assert_num_queries(3):
        client.get(detail_url(job))
