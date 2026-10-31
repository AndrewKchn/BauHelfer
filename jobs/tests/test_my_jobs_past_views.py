"""Integration tests: the employer's "Past" tab on "My jobs" (#26).

Spec: docs/specs/my-applications.md, iteration 3 (R22, R23, D3, D6, D8, D20), acceptance
criteria AC19 and AC20. Django test client on `my_jobs`; when a job is over is
Job.is_over, unit-tested in test_my_applications.py. The tabs of "My jobs" are in
test_my_jobs_views.py (#20).
"""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Job

from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(26)]

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the employer."""
    client.force_login(employer)
    return client


def groups(response):
    """The tabs on the page: (status, jobs) in order."""
    return [(group["status"], group["items"]) for group in response.context["groups"]]


# Which jobs are past (#26, docs/specs/my-applications.md R22, D3; AC19)


def test_open_job_that_is_over_is_past(employer_client, employer):
    """An open job whose day is over did not happen: it goes to "Past" (R22, D3).

    1. Save an open job that ended yesterday and one today
    2. Open "My jobs"
    3. Expect: today's job in "open", yesterday's in "past", the tabs in this order
    """
    over = make_job(employer, date=TODAY - DAY)
    today = make_job(employer, date=TODAY)

    response = employer_client.get(reverse("my_jobs"))

    assert groups(response) == [("open", [today]), ("past", [over])]


@pytest.mark.parametrize(
    "status", [Job.Status.FILLED, Job.Status.DONE, Job.Status.CANCELLED]
)
def test_other_jobs_that_are_over_keep_their_tab(employer_client, employer, status):
    """A filled job probably happened; done and cancelled stay what they are (D3).

    1. Save a filled / done / cancelled job that ended yesterday
    2. Open "My jobs"
    3. Expect: it is in the tab of its status, no "past" tab
    """
    job = make_job(employer, date=TODAY - DAY, status=status)

    response = employer_client.get(reverse("my_jobs"))

    assert groups(response) == [(status, [job])]


def test_past_tab_comes_last_in_grey(employer_client, employer):
    """After "Cancelled", labelled "Past", in the quiet grey (R22, D20).

    1. Save a cancelled job next week and an open job that ended yesterday
    2. Open "My jobs"
    3. Expect: the tabs cancelled, past; the badge "Past 1" with data-colour bg-base-300
    """
    make_job(employer, status=Job.Status.CANCELLED)
    make_job(employer, date=TODAY - DAY)

    response = employer_client.get(reverse("my_jobs"))

    assert [status for status, _ in groups(response)] == ["cancelled", "past"]
    assertContains(response, ">Past 1</a>")
    assertContains(response, 'data-colour="bg-base-300"')


# No changes to a past job (R23, D6; AC20)


def test_past_job_has_no_edit_or_cancel_link(employer_client, employer):
    """There is nothing to edit or cancel any more; the applications stay (R23).

    1. Save an open job that ended yesterday
    2. Open "My jobs"
    3. Expect: no edit and no cancel link for it
    """
    job = make_job(employer, date=TODAY - DAY)

    response = employer_client.get(reverse("my_jobs"))

    assertNotContains(response, reverse("job_edit", args=[job.pk]))
    assertNotContains(response, reverse("job_cancel", args=[job.pk]))


def test_open_job_today_keeps_its_links(employer_client, employer):
    """On the day of the job it is still open, with its links (R22).

    1. Save an open job today
    2. Open "My jobs"
    3. Expect: its edit and cancel links
    """
    job = make_job(employer, date=TODAY)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, reverse("job_edit", args=[job.pk]))
    assertContains(response, reverse("job_cancel", args=[job.pk]))
