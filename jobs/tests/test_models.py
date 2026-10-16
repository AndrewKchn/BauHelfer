"""Unit tests: the Job model (#15).

Spec: docs/specs/job.md (requirements R1-R6, decisions D1-D8).
"""

import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.forms import modelform_factory
from django.utils import timezone

from accounts.models import Skill
from jobs.models import MINIMUM_WAGE, District, Job

pytestmark = [pytest.mark.django_db, pytest.mark.story(15)]

User = get_user_model()


@pytest.fixture
def employer():
    """A user with the employer role."""
    return User.objects.create_user(
        email="employer@example.com", password="x", role="employer"
    )


def make_job(employer, **fields):
    """An unsaved job with every required field filled; `fields` replace the defaults."""
    values = {
        "job_type": "demolition",
        "description": "Tear down a garden shed.",
        "original_language": "de",
        "address": "Lindwurmstraße 1",
        "district": "sendling",
        "date": datetime.date(2026, 11, 3),
        "start_time": datetime.time(8, 0),
        "hours": 6,
        "workers_needed": 2,
        "hourly_rate": Decimal("18.00"),
        **fields,
    }
    return Job(employer=employer, **values)


# Choice lists and constants (R2, R3, D1)


def test_district_list():
    """The districts are the 25 Munich Stadtbezirke plus one entry outside the city.

    1. Read the values of District
    2. Expect: the 25 Stadtbezirke in official order, then "outside_munich"
    """
    assert District.values == [
        "altstadt_lehel",
        "ludwigsvorstadt_isarvorstadt",
        "maxvorstadt",
        "schwabing_west",
        "au_haidhausen",
        "sendling",
        "sendling_westpark",
        "schwanthalerhoehe",
        "neuhausen_nymphenburg",
        "moosach",
        "milbertshofen_am_hart",
        "schwabing_freimann",
        "bogenhausen",
        "berg_am_laim",
        "trudering_riem",
        "ramersdorf_perlach",
        "obergiesing_fasangarten",
        "untergiesing_harlaching",
        "thalkirchen_obersendling_forstenried_fuerstenried_solln",
        "hadern",
        "pasing_obermenzing",
        "aubing_lochhausen_langwied",
        "allach_untermenzing",
        "feldmoching_hasenbergl",
        "laim",
        "outside_munich",
    ]


def test_status_list():
    """A job is open, filled, done or cancelled.

    1. Read the values of Job.Status
    2. Expect: open, filled, done, cancelled
    """
    assert Job.Status.values == ["open", "filled", "done", "cancelled"]


def test_job_types_are_the_worker_skills():
    """The job type list is the same list as the worker skills.

    1. Read the choices of the job_type field
    2. Expect: exactly the Skill choices
    """
    assert Job._meta.get_field("job_type").choices == Skill.choices


def test_minimum_wage():
    """The minimum wage is the German one from 1 January 2026.

    1. Read MINIMUM_WAGE
    2. Expect: 13.90 as a Decimal
    """
    assert MINIMUM_WAGE == Decimal("13.90")


# Saving a job (R2, AC1, AC2)


def test_new_job_is_open(employer):
    """A job saved without a status is open.

    1. Save a job without setting the status
    2. Expect: status "open"
    """
    job = make_job(employer)
    job.save()

    job.refresh_from_db()
    assert job.status == Job.Status.OPEN


def test_job_with_required_fields_only(employer):
    """A job without coordinates can be saved; created_at is set automatically.

    1. Save a job with only the required fields
    2. Expect: no validation error, latitude and longitude empty, created_at filled
    """
    job = make_job(employer)
    job.full_clean()
    job.save()

    job.refresh_from_db()
    assert job.latitude is None
    assert job.longitude is None
    assert job.created_at is not None


def test_coordinates_are_stored_exactly(employer):
    """Coordinates keep six decimal places.

    1. Save a job at Marienplatz, 48.137154 / 11.576124
    2. Expect: the same numbers come back from the database
    """
    job = make_job(
        employer, latitude=Decimal("48.137154"), longitude=Decimal("11.576124")
    )
    job.save()

    job.refresh_from_db()
    assert job.latitude == Decimal("48.137154")
    assert job.longitude == Decimal("11.576124")


# Validation (AC3, AC4, AC5)


def test_rate_below_minimum_wage_is_rejected(employer):
    """An hourly rate one cent below the minimum wage is rejected.

    1. Validate a job with an hourly rate of 13.89
    2. Expect: a validation error on hourly_rate
    """
    job = make_job(employer, hourly_rate=Decimal("13.89"))

    with pytest.raises(ValidationError) as error:
        job.full_clean()
    assert "hourly_rate" in error.value.message_dict


def test_rate_equal_to_minimum_wage_is_accepted(employer):
    """An hourly rate equal to the minimum wage is accepted.

    1. Validate a job with an hourly rate of 13.90
    2. Expect: no validation error
    """
    make_job(employer, hourly_rate=Decimal("13.90")).full_clean()


@pytest.mark.parametrize(
    "field", ["job_type", "district", "status", "original_language"]
)
def test_unknown_choice_is_rejected(employer, field):
    """A value that is not in the field's list is rejected.

    1. Validate a job with "nonsense" in a choice field
    2. Expect: a validation error on that field
    """
    job = make_job(employer, **{field: "nonsense"})

    with pytest.raises(ValidationError) as error:
        job.full_clean()
    assert field in error.value.message_dict


@pytest.mark.parametrize("field", ["workers_needed", "hours"])
@pytest.mark.parametrize("value", [1, 10])
def test_range_limits_are_accepted(employer, field, value):
    """1 and 10 workers or hours are allowed.

    1. Validate a job with 1 or 10 in workers_needed or hours
    2. Expect: no validation error
    """
    make_job(employer, **{field: value}).full_clean()


@pytest.mark.parametrize("field", ["workers_needed", "hours"])
@pytest.mark.parametrize("value", [0, 11])
def test_out_of_range_is_rejected_by_validation(employer, field, value):
    """0 or 11 workers or hours are rejected by the form validation.

    1. Validate a job with 0 or 11 in workers_needed or hours
    2. Expect: a validation error on that field
    """
    job = make_job(employer, **{field: value})

    with pytest.raises(ValidationError) as error:
        job.full_clean()
    assert field in error.value.message_dict


@pytest.mark.parametrize("field", ["workers_needed", "hours"])
@pytest.mark.parametrize("value", [0, 11])
def test_out_of_range_is_rejected_by_database(employer, field, value):
    """0 or 11 workers or hours are rejected by the database even without validation.

    1. Save a job with 0 or 11 in workers_needed or hours, skipping full_clean()
    2. Expect: the database rejects it
    """
    job = make_job(employer, **{field: value})

    with pytest.raises(IntegrityError), transaction.atomic():
        job.save()


# Employer (R2, D4, AC6)


def test_employer_sees_their_jobs(employer):
    """An employer's jobs are reachable from the user.

    1. Save a job for an employer
    2. Expect: employer.jobs contains that job
    """
    job = make_job(employer)
    job.save()

    assert list(employer.jobs.all()) == [job]


def test_deleting_employer_deletes_their_jobs(employer):
    """When an employer is deleted, their jobs are deleted too.

    1. Save a job for an employer
    2. Delete the employer
    3. Expect: no jobs left
    """
    make_job(employer).save()

    employer.delete()

    assert not Job.objects.exists()


def test_only_employers_can_be_chosen_as_employer(employer):
    """The employer field in a form offers only users with the employer role.

    1. Create a worker and an admin without a role besides the employer
    2. Build a form for Job with the employer field
    3. Expect: only the employer is offered
    """
    User.objects.create_user(email="worker@example.com", password="x", role="worker")
    User.objects.create_superuser(email="admin@example.com", password="x")

    form = modelform_factory(Job, fields=["employer"])()

    assert list(form.fields["employer"].queryset) == [employer]


# Display (R4, AC7)


def test_str_shows_job_type_and_date(employer):
    """A job is shown as its job type name and its date.

    1. Make a demolition job on 3 November 2026
    2. Expect: "Demolition – 2026-11-03"
    """
    job = make_job(employer, job_type="demolition", date=datetime.date(2026, 11, 3))

    assert str(job) == "Demolition – 2026-11-03"


# Open jobs only (#16 spec R4, AC3)


@pytest.mark.story(16)
def test_open_returns_only_open_jobs(employer):
    """Job.objects.open() leaves out filled, done and cancelled jobs.

    1. Save one job in each status
    2. Ask for Job.objects.open()
    3. Expect: only the open job; the job list (#18) builds on this
    """
    jobs = {}
    for status in Job.Status.values:
        job = make_job(employer, status=status)
        job.save()
        jobs[status] = job

    assert list(Job.objects.open()) == [jobs["open"]]


# Upcoming jobs and end time (#18, docs/specs/job-list.md R3, R8; AC1, AC2)

# A fixed "now" for the upcoming tests: 3 November 2026, 10:00 in Munich (09:00 UTC).
MUNICH_NOW = datetime.datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))


@pytest.fixture
def frozen_now(monkeypatch):
    """Fix the clock at MUNICH_NOW, so the test does not depend on when it runs.

    timezone.localtime() and localdate() call timezone.now(), so they see this time too.
    """
    monkeypatch.setattr(timezone, "now", lambda: MUNICH_NOW)
    return MUNICH_NOW


@pytest.mark.story(18)
def test_upcoming_keeps_only_jobs_that_have_not_started(employer, frozen_now):
    """Job.objects.upcoming() keeps jobs that start later, Munich time.

    1. Fix the clock at 3 November 2026, 10:00 in Munich
    2. Save jobs yesterday, today at 09:00, 09:30, 10:00 and 11:00, and tomorrow at 06:00
    3. Ask for Job.objects.upcoming()
    4. Expect: only today 11:00 and tomorrow 06:00; 09:30 is gone although it is still
       ahead in UTC (09:00 there), and 10:00 is gone because it starts right now
    """
    today = datetime.date(2026, 11, 3)
    starts = {
        "yesterday": (today - datetime.timedelta(days=1), datetime.time(12, 0)),
        "today 09:00": (today, datetime.time(9, 0)),
        "today 09:30": (today, datetime.time(9, 30)),
        "today 10:00": (today, datetime.time(10, 0)),
        "today 11:00": (today, datetime.time(11, 0)),
        "tomorrow 06:00": (today + datetime.timedelta(days=1), datetime.time(6, 0)),
    }
    jobs = {}
    for name, (date, start_time) in starts.items():
        job = make_job(employer, date=date, start_time=start_time)
        job.save()
        jobs[name] = job

    assert set(Job.objects.upcoming()) == {jobs["today 11:00"], jobs["tomorrow 06:00"]}


@pytest.mark.story(18)
@pytest.mark.parametrize(
    ("start", "hours", "end"),
    [
        (datetime.time(8, 0), 6, datetime.time(14, 0)),
        (datetime.time(20, 0), 10, datetime.time(6, 0)),
    ],
    ids=["same day", "after midnight"],
)
def test_end_time_is_start_plus_hours(employer, start, hours, end):
    """Job.end_time is the start time plus the hours, also past midnight.

    1. Make a job starting at 08:00 for 6 hours, or at 20:00 for 10 hours
    2. Read job.end_time
    3. Expect: 14:00, or 06:00 (the next morning)
    """
    job = make_job(employer, start_time=start, hours=hours)

    assert job.end_time == end
