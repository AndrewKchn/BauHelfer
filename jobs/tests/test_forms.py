"""Unit tests: the job form, JobForm (#16).

Spec: docs/specs/job-form.md (R6-R9), acceptance criteria AC4-AC7.
Dates are counted from today, so the tests do not expire; where the minimum wage matters,
the test sets its own rates in settings around today.
"""

import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from jobs.forms import JobForm

# django_db: the form runs the model's CheckConstraints, and Django checks them with a query.
pytestmark = [pytest.mark.django_db, pytest.mark.story(16)]


def days_from_today(days):
    """The date `days` days after today in Munich (negative: before today)."""
    return timezone.localdate() + datetime.timedelta(days=days)


def form_data(**fields):
    """What the browser sends for a correctly filled job form; `fields` replace the defaults."""
    return {
        "job_type": "demolition",
        "description": "Tear down a garden shed.",
        "original_language": "de",
        "address": "Lindwurmstraße 1",
        "district": "sendling",
        "date": days_from_today(7).isoformat(),
        "start_time": "08:00",
        "hours": "6",
        "workers_needed": "2",
        "hourly_rate": "20.00",
        **fields,
    }


@pytest.fixture
def wage_rises_in_30_days(settings):
    """Minimum wage 13.90 € until 29 days from today, 15.00 € from 30 days from today."""
    settings.MINIMUM_WAGES = {
        datetime.date(2000, 1, 1): Decimal("13.90"),
        days_from_today(30): Decimal("15.00"),
    }


def test_valid_form():
    """A correctly filled job form is valid.

    1. Fill in every field with a good value
    2. Expect: the form is valid
    """
    form = JobForm(data=form_data())

    assert form.is_valid(), form.errors


# Fields (R6, AC6)


def test_form_fields():
    """The form asks for the job details only, not for owner, status or coordinates.

    1. Open an empty job form
    2. Expect: the ten job fields in order; no employer, status, latitude, longitude
    """
    # The view sets the employer, the model the status; geocoding (#41) the coordinates.
    assert list(JobForm().fields) == [
        "job_type",
        "description",
        "original_language",
        "address",
        "district",
        "date",
        "start_time",
        "hours",
        "workers_needed",
        "hourly_rate",
    ]


# Minimum wage of the job's date (R7, AC4)


@pytest.mark.usefixtures("wage_rises_in_30_days")
def test_rate_equal_to_minimum_wage_of_the_date_is_accepted():
    """An hourly rate equal to the minimum wage of the job's date is accepted.

    1. Minimum wage rises from 13.90 € to 15.00 € in 30 days
    2. Post a job in 40 days at 15.00 €
    3. Expect: the form is valid
    """
    form = JobForm(data=form_data(date=days_from_today(40), hourly_rate="15.00"))

    assert form.is_valid(), form.errors


@pytest.mark.usefixtures("wage_rises_in_30_days")
def test_rate_one_cent_below_minimum_wage_of_the_date_is_rejected():
    """One cent below the minimum wage of the job's date is rejected with a clear error.

    1. Minimum wage rises from 13.90 € to 15.00 € in 30 days
    2. Post a job in 40 days at 14.99 €
    3. Expect: an error on the hourly rate that names 15.00
    """
    form = JobForm(data=form_data(date=days_from_today(40), hourly_rate="14.99"))

    assert not form.is_valid()
    assert list(form.errors) == ["hourly_rate"]
    assert "15.00" in form.errors["hourly_rate"][0]


@pytest.mark.usefixtures("wage_rises_in_30_days")
def test_same_rate_is_accepted_before_the_rise():
    """A rate below the new minimum wage is still fine for a day before the rise.

    1. Minimum wage rises from 13.90 € to 15.00 € in 30 days
    2. Post a job in 10 days at 14.99 €
    3. Expect: the form is valid
    """
    form = JobForm(data=form_data(date=days_from_today(10), hourly_rate="14.99"))

    assert form.is_valid(), form.errors


def test_rate_below_lowest_minimum_wage_is_rejected():
    """A rate below every minimum wage is rejected.

    1. Post a job at 13.89 €
    2. Expect: an error on the hourly rate only
    """
    form = JobForm(data=form_data(hourly_rate="13.89"))

    assert not form.is_valid()
    assert list(form.errors) == ["hourly_rate"]


# Date (R7, AC5)


def test_date_in_the_past_is_rejected():
    """A job cannot be posted for yesterday.

    1. Post a job with yesterday's date
    2. Expect: an error on the date only
    """
    form = JobForm(data=form_data(date=days_from_today(-1)))

    assert not form.is_valid()
    assert list(form.errors) == ["date"]


def test_date_today_is_accepted():
    """A job can be posted for today.

    1. Post a job with today's date
    2. Expect: the form is valid
    """
    form = JobForm(data=form_data(date=days_from_today(0)))

    assert form.is_valid(), form.errors


# Browser hints (R8, AC7)


def test_date_and_time_inputs_open_the_pickers():
    """Date and start time use the browser's date and time inputs.

    1. Render the date and start time fields
    2. Expect: type="date" with today as the earliest date, type="time"
    """
    form = JobForm()

    assert 'type="date"' in str(form["date"])
    assert f'min="{days_from_today(0).isoformat()}"' in str(form["date"])
    assert 'type="time"' in str(form["start_time"])


@pytest.mark.parametrize("field", ["hours", "workers_needed"])
def test_hours_and_workers_carry_the_model_limits(field):
    """Hours and workers tell the browser the same 1-10 limits as the model.

    1. Render the hours / workers needed field
    2. Expect: min="1" and max="10", not the min="0" Django gives by default
    """
    html = str(JobForm()[field])

    assert 'min="1"' in html
    assert 'max="10"' in html


def test_rate_input_has_cents_and_the_lowest_minimum_wage():
    """The hourly rate input allows cents and starts at the lowest minimum wage.

    1. Render the hourly rate field
    2. Expect: step="0.01" and min="13.90"
    """
    html = str(JobForm()["hourly_rate"])

    assert 'step="0.01"' in html
    assert 'min="13.90"' in html
