"""Unit tests: minimum wage by date from settings (#16, covers #17).

Spec: docs/specs/job-form.md (R1-R3, D3), acceptance criteria AC1-AC2.
"""

import datetime
from decimal import Decimal

import pytest
from django.conf import settings

from jobs.models import MINIMUM_WAGE, minimum_wage_on

pytestmark = [pytest.mark.story(16)]


def test_minimum_wages_are_in_settings():
    """The minimum wages with their start dates are a dict in settings.

    1. Read settings.MINIMUM_WAGES
    2. Expect: 13.90 € from 1 January 2026 and 14.60 € from 1 January 2027
    """
    assert settings.MINIMUM_WAGES == {
        datetime.date(2026, 1, 1): Decimal("13.90"),
        datetime.date(2027, 1, 1): Decimal("14.60"),
    }


@pytest.mark.parametrize(
    ("day", "rate"),
    [
        (datetime.date(2026, 1, 1), Decimal("13.90")),  # first day of the 2026 rate
        (datetime.date(2026, 12, 31), Decimal("13.90")),  # last day before the rise
        (datetime.date(2027, 1, 1), Decimal("14.60")),  # first day of the 2027 rate
        (datetime.date(2030, 6, 1), Decimal("14.60")),  # no newer rate known yet
    ],
)
def test_minimum_wage_on_a_day(day, rate):
    """The minimum wage of a day is the rate with the latest start on or before it.

    1. Ask for the minimum wage on a day around the 2027 rise
    2. Expect: 13.90 € up to 31 December 2026, 14.60 € from 1 January 2027
    """
    assert minimum_wage_on(day) == rate


def test_minimum_wage_before_the_first_rate():
    """A day before the first start date gets the first rate.

    1. Ask for the minimum wage on a day in 2025
    2. Expect: 13.90 €, the first rate in the dict
    """
    assert minimum_wage_on(datetime.date(2025, 6, 1)) == Decimal("13.90")


def test_minimum_wage_follows_changed_settings(settings):
    """minimum_wage_on reads settings each time, so a new rate needs only settings.

    1. Add a rate of 20.00 € from 1 January 2030 to settings
    2. Expect: 20.00 € on 1 March 2030, still 14.60 € on 1 March 2029
    """
    settings.MINIMUM_WAGES = {
        **settings.MINIMUM_WAGES,
        datetime.date(2030, 1, 1): Decimal("20.00"),
    }

    assert minimum_wage_on(datetime.date(2030, 3, 1)) == Decimal("20.00")
    assert minimum_wage_on(datetime.date(2029, 3, 1)) == Decimal("14.60")


def test_model_floor_is_the_lowest_rate():
    """MINIMUM_WAGE in the model is the lowest rate from settings, not a number of its own.

    1. Read MINIMUM_WAGE from jobs.models
    2. Expect: the lowest value of settings.MINIMUM_WAGES (13.90 €)
    """
    # The model validator and the #15 migration use it; it must not drift from settings.
    assert MINIMUM_WAGE == min(settings.MINIMUM_WAGES.values())
