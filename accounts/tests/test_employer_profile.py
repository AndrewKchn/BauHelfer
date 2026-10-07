"""Unit tests: employer profile model and form (#12).

Spec: docs/specs/employer-profile.md (requirements R1-R11, decisions D1-D3).
"""

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from accounts.forms import EmployerProfileForm
from accounts.models import EmployerProfile, Trade

pytestmark = [pytest.mark.django_db, pytest.mark.story(12)]

User = get_user_model()


@pytest.fixture
def employer():
    """A user who chose the employer role and has no profile yet."""
    return User.objects.create_user(
        email="employer@example.com", password="x", role="employer", name="Anna Huber"
    )


def make_profile(user, **fields):
    """Save a valid profile for `user`; `fields` replace the defaults."""
    values = {
        "company_name": "Huber Fenster GmbH",
        "trades": ["window_fitting"],
        **fields,
    }
    return EmployerProfile.objects.create(user=user, **values)


def valid_form_data(**fields):
    """Form data as a browser sends it for a correctly filled profile form."""
    return {
        "company_name": "Huber Fenster GmbH",
        "trades": ["window_fitting", "drywall"],
        **fields,
    }


# Choice list (R2, D1)


def test_trade_list():
    """The trades are the fifteen agreed in the spec.

    1. Read the values of Trade
    2. Expect: exactly the fifteen trades from the spec, in that order
    """
    assert Trade.values == [
        "window_fitting",
        "drywall",
        "plastering",
        "painting",
        "tiling",
        "roofing",
        "bricklaying",
        "carpentry",
        "electrical",
        "plumbing_heating",
        "landscaping",
        "demolition",
        "general_contractor",
        "private_person",
        "other",
    ]


# Model (R1, R2, R7, D2)


def test_profile_is_linked_to_its_user(employer):
    """A saved profile is reachable from its user.

    1. Save a profile for an employer
    2. Expect: user.employer_profile is that profile
    """
    profile = make_profile(employer)

    employer.refresh_from_db()
    assert employer.employer_profile == profile


def test_user_cannot_have_two_profiles(employer):
    """The database allows only one profile per user.

    1. Save a profile for an employer
    2. Save a second profile for the same employer
    3. Expect: the database rejects it
    """
    make_profile(employer)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_profile(employer)


def test_deleting_the_user_deletes_the_profile(employer):
    """No profile stays behind without its user.

    1. Save a profile for an employer
    2. Delete the employer
    3. Expect: no profiles left
    """
    make_profile(employer)

    employer.delete()

    assert EmployerProfile.objects.count() == 0


def test_company_name_may_be_empty(employer):
    """A private person saves a profile without a company.

    1. Save a profile with an empty company name and the trade "private person"
    2. Expect: it is saved with an empty company name
    """
    profile = make_profile(employer, company_name="", trades=["private_person"])

    profile.refresh_from_db()
    assert profile.company_name == ""


@pytest.mark.parametrize(
    ("company_name", "shown"),
    [("Huber Fenster GmbH", "Huber Fenster GmbH"), ("", "Anna Huber")],
)
def test_display_name(employer, company_name, shown):
    """The profile is shown under the company name, or the person's name without one.

    1. Take a profile of Anna Huber with company "Huber Fenster GmbH" / no company
    2. Expect: "Huber Fenster GmbH" / "Anna Huber"
    """
    profile = EmployerProfile(user=employer, company_name=company_name)

    assert profile.display_name() == shown


def test_trade_names_are_readable():
    """Stored codes are shown as names, in the order they were chosen.

    1. Take a profile with trades window_fitting, plumbing_heating, private_person
    2. Expect: "Window fitting", "Plumbing & heating", "Private person"
    """
    profile = EmployerProfile(
        trades=["window_fitting", "plumbing_heating", "private_person"]
    )

    assert profile.trade_names() == [
        "Window fitting",
        "Plumbing & heating",
        "Private person",
    ]


# Profile form (R2, R7, D1, D2)


def test_profile_form_fields():
    """The form edits the company name and the trades, never the owner.

    1. Open an empty employer profile form
    2. Expect: company_name, trades, and no user field
    """
    # The owner always comes from the logged-in user (AC8).
    assert list(EmployerProfileForm().fields) == ["company_name", "trades"]


def test_trades_are_checkboxes():
    """Several trades can be ticked.

    1. Open an empty employer profile form
    2. Expect: checkboxes for the trades
    """
    form = EmployerProfileForm()

    assert isinstance(form.fields["trades"].widget, forms.CheckboxSelectMultiple)


def test_profile_form_saves_a_valid_profile(employer):
    """A correctly filled form saves the company and all chosen trades.

    1. Submit the form: "Huber Fenster GmbH", window fitting + drywall
    2. Save it for the employer
    3. Expect: the profile in the database has exactly these values
    """
    form = EmployerProfileForm(valid_form_data())

    assert form.is_valid(), form.errors
    profile = form.save(commit=False)
    profile.user = employer
    profile.save()

    profile.refresh_from_db()
    assert profile.company_name == "Huber Fenster GmbH"
    assert profile.trades == ["window_fitting", "drywall"]


def test_profile_form_accepts_an_empty_company_name():
    """The company name is optional in the form too.

    1. Submit the form with an empty company name
    2. Expect: the form is valid
    """
    form = EmployerProfileForm(valid_form_data(company_name=""))

    assert form.is_valid(), form.errors


def test_profile_form_rejects_a_too_long_company_name():
    """A company name longer than 150 characters is an error.

    1. Submit the form with a company name of 151 characters
    2. Expect: the form is invalid with an error on company_name
    """
    form = EmployerProfileForm(valid_form_data(company_name="x" * 151))

    assert not form.is_valid()
    assert "company_name" in form.errors


@pytest.mark.parametrize("trades", [[], ["astronaut"], ["drywall", "astronaut"]])
def test_profile_form_rejects_empty_or_unknown_trades(trades):
    """At least one trade is needed, and only trades from the list.

    1. Submit the form with no trade / an unknown trade / a known and an unknown trade
    2. Expect: the form is invalid with an error on trades
    """
    form = EmployerProfileForm(valid_form_data(trades=trades))

    assert not form.is_valid()
    assert "trades" in form.errors
