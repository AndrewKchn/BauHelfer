"""Unit tests: the one-row SiteSettings with the demo switch (#81).

Spec: docs/specs/email-verification.md, iteration 3 (R13, D12), acceptance criterion AC17.
"""

import pytest

from accounts.models import SiteSettings

pytestmark = [pytest.mark.django_db, pytest.mark.story(81)]


def test_load_creates_one_row_with_the_switch_on():
    """The first load() creates the row, verification switched on (R13).

    1. Start with no SiteSettings
    2. Call SiteSettings.load() twice
    3. Expect: one row, the same both times, email_verification_required on
    """
    first = SiteSettings.load()
    second = SiteSettings.load()

    assert SiteSettings.objects.count() == 1
    assert first.pk == second.pk
    assert second.email_verification_required is True


def test_saving_a_new_object_still_leaves_one_row():
    """Saving a new SiteSettings() overwrites the row instead of adding one (AC17).

    1. Load the settings
    2. Save a new SiteSettings() with the switch off
    3. Expect: still one row, and load() gives the switch off
    """
    SiteSettings.load()

    SiteSettings(email_verification_required=False).save()

    assert SiteSettings.objects.count() == 1
    assert SiteSettings.load().email_verification_required is False
