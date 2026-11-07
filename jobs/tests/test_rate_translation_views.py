"""Integration tests: the hourly rate "€/h" is translated on every page that shows it (#30).

Each test goes through the whole stack: middleware, URL, view, template and database.
Spec: docs/specs/translations.md, iteration 1 (R1, D9), acceptance criterion AC1.
German is the example; the number is localized too (20,00).
"""

import pytest
from django.conf import settings
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(30)]

GERMAN_RATE = "20,00 €/Std."  # make_job's rate, in German


@pytest.fixture
def job():
    """An open job at 20.00 €/h, posted by an employer who reads the site in German."""
    employer = make_employer("anna@example.com", preferred_language="de")
    return make_job(employer)


@pytest.fixture
def german_guest(client):
    """A guest browser that chose German in the switcher (the language cookie)."""
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "de"
    return client


def test_job_card_shows_the_rate_in_german(german_guest, job):
    """The job list shows the rate with the German unit.

    1. As a guest with the German cookie, open the job list
    2. Expect: "20,00 €/Std." on the card, no "€/h"
    """
    response = german_guest.get(reverse("home"))

    assertContains(response, GERMAN_RATE)
    assertNotContains(response, "€/h")


def test_job_detail_shows_the_rate_in_german(german_guest, job):
    """The job page shows the rate with the German unit.

    1. As a guest with the German cookie, open the job page
    2. Expect: "20,00 €/Std." on it, no "€/h"
    """
    response = german_guest.get(reverse("job_detail", args=[job.pk]))

    assertContains(response, GERMAN_RATE)
    assertNotContains(response, "€/h")


def test_job_summary_shows_the_rate_in_german(client, job):
    """The job summary on "My jobs" shows the rate with the German unit.

    1. Log in as the employer whose profile language is German, open "My jobs"
    2. Expect: "20,00 €/Std." in the job's summary, no "€/h"
    """
    client.force_login(job.employer)

    response = client.get(reverse("my_jobs"))

    assertContains(response, GERMAN_RATE)
    assertNotContains(response, "€/h")
