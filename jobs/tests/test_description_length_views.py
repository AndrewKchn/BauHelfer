"""Integration tests: posting and editing a job with a description above 1000 characters (#34).

Spec: docs/specs/ai-translation.md, "#34: API errors and cost limits", iteration 2 (R18,
R19), acceptance criteria AC20, AC21. Django test client on `job_create` and `job_edit`:
middleware, URL, view, form, template and database. The form itself is unit-tested in
test_description_length.py.
"""

import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains

from jobs.models import Job

from .test_views import form_data, make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(34)]

# 1001 characters. No space at the end: the form strips it, and 1000 would be left.
TOO_LONG = "Abriss " * 142 + "Abbruch"


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


@pytest.fixture
def employer_client(client, employer):
    """The test client, logged in as the employer."""
    client.force_login(employer)
    return client


def test_post_page_shows_the_limit(employer_client):
    """The "Post a job" page shows the limit under the description and in the textarea.

    1. Log in as an employer
    2. Open "Post a job"
    3. Expect: the help text with "up to 1000 characters" and maxlength="1000"
    """
    response = employer_client.get(reverse("job_create"))

    assertContains(response, "Write in your language, up to 1000 characters.")
    assertContains(response, 'maxlength="1000"')


def test_too_long_job_is_not_posted(employer_client):
    """A job with 1001 characters of description is not saved, and the form says why.

    1. Log in as an employer
    2. Send the job form with a description of 1001 characters
    3. Expect: no job saved; the form is shown again with the length error
    """
    assert len(TOO_LONG) == 1001

    response = employer_client.post(
        reverse("job_create"), form_data(description=TOO_LONG)
    )

    assert response.status_code == 200
    assert not Job.objects.exists()
    assertContains(response, "at most 1000 characters (it has 1001)")


def test_edit_cannot_make_a_description_too_long(employer_client, employer):
    """Editing a job to 1001 characters of description is refused, the old text stays.

    1. Log in as the employer of an open job
    2. Send the edit form with a description of 1001 characters
    3. Expect: the form is shown again with the length error; the saved description is
       unchanged
    """
    job = make_job(employer)
    before = job.description

    response = employer_client.post(
        reverse("job_edit", args=[job.pk]), form_data(description=TOO_LONG)
    )

    assertContains(response, "at most 1000 characters (it has 1001)")
    job.refresh_from_db()
    assert job.description == before
