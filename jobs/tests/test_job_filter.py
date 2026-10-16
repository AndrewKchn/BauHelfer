"""Unit tests: the job list filters, JobFilterForm (#18, iteration 2).

Spec: docs/specs/job-list.md (R12, R14-R16, R19), acceptance criteria AC12-AC15.
The form is the one place where the filters live (spec D10): the view only calls
`form.filter(jobs)`, and the map (#42) will do the same.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from accounts.models import Skill
from jobs.forms import JobFilterForm
from jobs.models import District, Job

from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(18)]

# A fixed "now" for the date filter: 3 November 2026, 10:00 in Munich.
MUNICH_NOW = datetime.datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
TODAY = MUNICH_NOW.date()


@pytest.fixture
def frozen_now(monkeypatch):
    """Fix the clock at MUNICH_NOW, so "next 7 days" does not depend on when the test runs."""
    monkeypatch.setattr(timezone, "now", lambda: MUNICH_NOW)
    return MUNICH_NOW


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


def filtered(data):
    """The upcoming jobs that JobFilterForm(data) keeps, as a set."""
    return set(JobFilterForm(data).filter(Job.objects.upcoming()))


# The form itself (#18, docs/specs/job-list.md R12, R16; AC12)


def test_empty_form_is_valid_and_filters_nothing():
    """Without any choice the form is valid and has no filters.

    1. Make the form from an empty query string
    2. Expect: valid, has_filters is False
    """
    form = JobFilterForm({})

    assert form.is_valid()
    assert form.has_filters is False


def test_choices_start_with_all():
    """Each drop-down starts with "all" (an empty value), then the real values.

    1. Read the choices of the three fields
    2. Expect: date "", "7", "30"; job type "" + every job type; district "" + every district
    """
    form = JobFilterForm()

    assert [value for value, _ in form.fields["date"].choices] == ["", "7", "30"]
    assert [value for value, _ in form.fields["job_type"].choices] == [
        "",
        *Skill.values,
    ]
    assert [value for value, _ in form.fields["district"].choices] == [
        "",
        *District.values,
    ]


def test_a_value_that_is_not_listed_makes_only_that_field_invalid():
    """?district=moon is rejected, the other filters still count.

    1. Make the form with district "moon" and job type "demolition"
    2. Expect: the form is invalid only because of district; has_filters is True
       (the job type is chosen)
    """
    form = JobFilterForm({"district": "moon", "job_type": "demolition"})

    assert not form.is_valid()
    assert list(form.errors) == ["district"]
    assert form.has_filters is True


@pytest.mark.parametrize("field", ["date", "job_type", "district"])
def test_any_one_filter_counts_as_filtered(field):
    """Choosing one filter is enough for has_filters ("Reset filters" is shown, R19).

    1. Make the form with one valid value in date / job type / district
    2. Expect: has_filters is True
    """
    value = {"date": "7", "job_type": "demolition", "district": "sendling"}[field]

    assert JobFilterForm({field: value}).has_filters is True


# Filtering (#18, docs/specs/job-list.md R14-R16; AC13, AC14, AC15)


def test_job_type_and_district_keep_only_matching_jobs(employer):
    """Job type and district each narrow the list; together they must both match.

    1. Save a demolition job in Sendling, a demolition job in Laim, a carrying job in Sendling
    2. Filter by job type, by district, and by both
    3. Expect: demolition -> the two demolition jobs; Sendling -> the two Sendling jobs;
       both -> only the demolition job in Sendling
    """
    demolition_sendling = make_job(employer, job_type="demolition", district="sendling")
    demolition_laim = make_job(employer, job_type="demolition", district="laim")
    carrying_sendling = make_job(employer, job_type="carrying", district="sendling")

    assert filtered({"job_type": "demolition"}) == {
        demolition_sendling,
        demolition_laim,
    }
    assert filtered({"district": "sendling"}) == {
        demolition_sendling,
        carrying_sendling,
    }
    assert filtered({"job_type": "demolition", "district": "sendling"}) == {
        demolition_sendling
    }


def test_next_7_and_30_days_count_from_today(employer, frozen_now):
    """ "Next 7 days" is today + 6 days, "Next 30 days" today + 29; "Any day" keeps all.

    1. Fix the clock at 3 November 2026, 10:00 in Munich
    2. Save jobs today at 11:00 and in 6, 7, 29 and 30 days
    3. Filter by date "7", "30" and "" (any day)
    4. Expect: "7" -> today and +6; "30" -> today up to +29; "" -> all five
    """
    jobs = {
        days: make_job(
            employer,
            date=TODAY + datetime.timedelta(days=days),
            start_time=datetime.time(11, 0),
        )
        for days in (0, 6, 7, 29, 30)
    }

    assert filtered({"date": "7"}) == {jobs[0], jobs[6]}
    assert filtered({"date": "30"}) == {jobs[0], jobs[6], jobs[7], jobs[29]}
    assert filtered({"date": ""}) == set(jobs.values())


def test_a_value_that_is_not_listed_is_ignored(employer):
    """?district=moon filters nothing; a valid filter next to it still works.

    1. Save a demolition job and a carrying job
    2. Filter by district "moon", then by district "moon" and job type "demolition"
    3. Expect: both jobs; then only the demolition job
    """
    demolition = make_job(employer, job_type="demolition")
    carrying = make_job(employer, job_type="carrying")

    assert filtered({"district": "moon"}) == {demolition, carrying}
    assert filtered({"district": "moon", "job_type": "demolition"}) == {demolition}


def test_filter_keeps_the_order_and_only_narrows(employer):
    """filter() only adds conditions: the jobs it gets stay in their order.

    1. Save two Sendling jobs, the later one first, and a Laim job
    2. Filter Job.objects.order_by("date") by district Sendling
    3. Expect: the two Sendling jobs, sooner first
    """
    later = make_job(
        employer, district="sendling", date=TODAY + datetime.timedelta(days=9)
    )
    sooner = make_job(
        employer, district="sendling", date=TODAY + datetime.timedelta(days=8)
    )
    make_job(employer, district="laim")

    jobs = JobFilterForm({"district": "sendling"}).filter(Job.objects.order_by("date"))

    assert list(jobs) == [sooner, later]
