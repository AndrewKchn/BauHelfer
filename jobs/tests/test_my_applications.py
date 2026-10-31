"""Unit tests: when a job is over, and which tab of "My applications" an application is in.

Spec: docs/specs/my-applications.md, iteration 1 (R1, R2, D3, D8-D10), acceptance criteria
AC1-AC3. The page itself is in test_my_applications_views.py.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from jobs.models import Application, Job

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(26)]

# A fixed "now": 3 November 2026, 10:00 in Munich, as in test_contacts.py.
MUNICH_NOW = datetime.datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
TODAY = MUNICH_NOW.date()
DAY = datetime.timedelta(days=1)


@pytest.fixture
def frozen_now(monkeypatch):
    """Fix the clock at MUNICH_NOW, so the test does not depend on when it runs."""
    monkeypatch.setattr(timezone, "now", lambda: MUNICH_NOW)
    return MUNICH_NOW


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


def apply(job, status):
    """Save an application of a new worker to `job` in `status`."""
    taken = 1 if status == "accepted" else 0
    return Application.objects.create(
        job=job, worker=make_worker(), status=status, workers_accepted=taken
    )


# When a job is over (#26, docs/specs/my-applications.md R1, D8; AC1, AC2)


@pytest.mark.parametrize(
    ("date", "start_hour", "hours", "expected"),
    [
        (TODAY + DAY, 8, 6, False),  # tomorrow
        (TODAY, 8, 6, False),  # started at 08:00, still the day of the job
        (TODAY - DAY, 8, 6, True),  # ended yesterday at 14:00
        (TODAY - DAY, 22, 8, False),  # a night shift that ended today at 06:00
        (TODAY - 2 * DAY, 22, 8, True),  # the night shift ended yesterday morning
    ],
    ids=[
        "tomorrow",
        "today",
        "yesterday",
        "night shift ending today",
        "night shift ending yesterday",
    ],
)
def test_a_job_is_over_from_the_day_after_it_ends(
    employer, frozen_now, date, start_hour, hours, expected
):
    """A job is over once the day it ends is over, Munich time (R1).

    1. Fix the clock at 3 November 2026, 10:00 in Munich
    2. Save a job on that date, start and hours
    3. Expect: is_over is False until the day the job ends is over, then True
    """
    job = make_job(
        employer, date=date, start_time=datetime.time(start_hour, 0), hours=hours
    )

    assert job.is_over is expected


@pytest.mark.parametrize(("date", "expected"), [(TODAY, True), (TODAY - DAY, False)])
def test_contacts_follow_the_same_rule(employer, frozen_now, date, expected):
    """An accepted application shows contacts exactly while its job is not over (D8).

    1. Fix the clock; save an accepted application to a job today / yesterday
    2. Expect: shows_contacts is the opposite of the job's is_over
    """
    application = apply(make_job(employer, date=date), "accepted")

    assert application.shows_contacts is expected
    assert application.job.is_over is not expected


# The tab of an application (R2, D3, D9, D10; AC3)


@pytest.mark.parametrize(
    "status", ["pending", "accepted", "closed", "rejected", "cancelled"]
)
def test_application_of_a_coming_job_is_in_the_tab_of_its_status(
    employer, frozen_now, status
):
    """Before the job, each application is in the tab of its own status.

    1. Fix the clock; save an application with this status to an open job next week
    2. Expect: its tab is its status
    """
    application = apply(make_job(employer, date=TODAY + 7 * DAY), status)

    assert application.tab == status


@pytest.mark.parametrize("status", ["pending", "closed"])
def test_waiting_application_of_a_job_that_is_over_is_past(
    employer, frozen_now, status
):
    """What is over and did not happen goes to "Past" (D3).

    1. Fix the clock; save a pending / "Job filled" application to a job that ended
       yesterday
    2. Expect: its tab is "past"
    """
    application = apply(make_job(employer, date=TODAY - DAY), status)

    assert application.tab == "past"


@pytest.mark.parametrize("status", ["accepted", "rejected", "cancelled"])
def test_decided_application_of_a_job_that_is_over_keeps_its_tab(
    employer, frozen_now, status
):
    """An accepted worker probably worked; rejected and cancelled stay what they are (D3).

    1. Fix the clock; save an accepted / rejected / cancelled application to a job that
       ended yesterday
    2. Expect: its tab is still its status, not "past"
    """
    application = apply(make_job(employer, date=TODAY - DAY), status)

    assert application.tab == status


@pytest.mark.parametrize("date", [TODAY + 7 * DAY, TODAY - DAY], ids=["coming", "over"])
def test_pending_application_of_a_cancelled_job_is_cancelled(
    employer, frozen_now, date
):
    """Nobody will answer it: it is in "Cancelled", also after the job's day (D9).

    1. Fix the clock; save a pending application to a cancelled job next week / that ended
       yesterday
    2. Expect: its tab is "cancelled"
    """
    job = make_job(employer, date=date, status=Job.Status.CANCELLED)

    assert apply(job, "pending").tab == "cancelled"
