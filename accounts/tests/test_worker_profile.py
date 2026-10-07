"""Unit tests: worker profile model and forms (#11).

Spec: docs/specs/worker-profile.md (requirements R1-R9, decisions D1-D8).
"""

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from accounts.forms import NameAndPhoneForm, WorkerProfileForm
from accounts.models import Skill, SpokenLanguage, WorkerProfile

pytestmark = [pytest.mark.django_db, pytest.mark.story(11)]

User = get_user_model()


@pytest.fixture
def worker():
    """A user who chose the worker role and has no profile yet."""
    return User.objects.create_user(
        email="worker@example.com", password="x", role="worker"
    )


def make_profile(user, **fields):
    """Save a valid profile for `user`; `fields` replace the defaults."""
    values = {
        "team_size": 1,
        "skills": ["demolition"],
        "languages": ["de"],
        "legal_status": "minijob",
        **fields,
    }
    return WorkerProfile.objects.create(user=user, **values)


def valid_form_data(**fields):
    """Form data as a browser sends it for a correctly filled profile form."""
    return {
        "team_size": "3",
        "skills": ["demolition", "carrying"],
        "languages": ["ru", "de"],
        "legal_status": "gewerbe",
        **fields,
    }


# Choice lists (R2, D1, D2)


def test_skill_list():
    """The skills are the eight helper jobs agreed in the spec.

    1. Read the values of Skill
    2. Expect: exactly the eight skills from the spec, in that order
    """
    assert Skill.values == [
        "demolition",
        "debris_clearing",
        "carrying",
        "earthworks",
        "site_cleaning",
        "scaffolding",
        "drywall",
        "painting",
    ]


def test_spoken_language_list():
    """The spoken languages are the 7 UI languages plus 8 others.

    1. Read the values of SpokenLanguage
    2. Expect: the 7 UI languages first, then the 8 others from the spec
    """
    ui_languages = ["de", "en", "ru", "uk", "pl", "ro", "tr"]
    others = ["bg", "hr", "sr", "bs", "hu", "sq", "ar", "it"]

    assert SpokenLanguage.values == ui_languages + others


def test_legal_status_list():
    """A worker is self-employed (Gewerbe), on a Minijob or employed.

    1. Read the values of WorkerProfile.LegalStatus
    2. Expect: gewerbe, minijob, employed
    """
    assert WorkerProfile.LegalStatus.values == ["gewerbe", "minijob", "employed"]


# Model (R1, R2, D6)


def test_profile_is_linked_to_its_user(worker):
    """A saved profile is reachable from its user.

    1. Save a profile for a worker
    2. Expect: user.worker_profile is that profile
    """
    profile = make_profile(worker)

    worker.refresh_from_db()
    assert worker.worker_profile == profile


def test_user_cannot_have_two_profiles(worker):
    """The database allows only one profile per user.

    1. Save a profile for a worker
    2. Save a second profile for the same worker
    3. Expect: the database rejects it
    """
    make_profile(worker)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_profile(worker)


def test_deleting_the_user_deletes_the_profile(worker):
    """No profile stays behind without its user.

    1. Save a profile for a worker
    2. Delete the worker
    3. Expect: no profiles left
    """
    make_profile(worker)

    worker.delete()

    assert WorkerProfile.objects.count() == 0


@pytest.mark.parametrize("team_size", [0, 11])
def test_database_rejects_team_size_outside_1_to_10(worker, team_size):
    """Team size 0 or 11 cannot be saved, even without the form.

    1. Save a profile with team size 0 / 11 directly in the database
    2. Expect: the database rejects it
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        make_profile(worker, team_size=team_size)


@pytest.mark.parametrize(
    ("team_size", "label"), [(1, "Individual"), (3, "Crew of 3"), (10, "Crew of 10")]
)
def test_team_label(team_size, label):
    """Team size is shown in words: one person or a crew.

    1. Take a profile with team size 1 / 3 / 10
    2. Expect: "Individual" / "Crew of 3" / "Crew of 10"
    """
    assert WorkerProfile(team_size=team_size).team_label() == label


def test_skill_and_language_names_are_readable():
    """Stored codes are shown as names, in the order they were chosen.

    1. Take a profile with skills demolition, carrying and languages ru, de
    2. Expect: skill names "Demolition", "Carrying materials"
    3. Expect: language names "Russian", "German"
    """
    profile = WorkerProfile(skills=["demolition", "carrying"], languages=["ru", "de"])

    assert profile.skill_names() == ["Demolition", "Carrying materials"]
    assert profile.language_names() == ["Russian", "German"]


# Profile form (R2, R7, D6)


def test_profile_form_fields():
    """The form edits the four profile fields and never the owner.

    1. Open an empty worker profile form
    2. Expect: team_size, skills, languages, legal_status, and no user field
    """
    # The owner always comes from the logged-in user (AC10).
    assert list(WorkerProfileForm().fields) == [
        "team_size",
        "skills",
        "languages",
        "legal_status",
    ]


def test_profile_form_widgets():
    """Skills and languages are checkboxes, legal status is radio buttons.

    1. Open an empty worker profile form
    2. Expect: checkboxes for skills and languages, radio buttons for legal status
    """
    form = WorkerProfileForm()

    assert isinstance(form.fields["skills"].widget, forms.CheckboxSelectMultiple)
    assert isinstance(form.fields["languages"].widget, forms.CheckboxSelectMultiple)
    assert isinstance(form.fields["legal_status"].widget, forms.RadioSelect)


def test_profile_form_saves_a_valid_profile(worker):
    """A correctly filled form saves all four fields.

    1. Submit the form: crew of 3, demolition + carrying, ru + de, Gewerbe
    2. Save it for the worker
    3. Expect: the profile in the database has exactly these values
    """
    form = WorkerProfileForm(valid_form_data())

    assert form.is_valid(), form.errors
    profile = form.save(commit=False)
    profile.user = worker
    profile.save()

    profile.refresh_from_db()
    assert profile.team_size == 3
    assert profile.skills == ["demolition", "carrying"]
    assert profile.languages == ["ru", "de"]
    assert profile.legal_status == "gewerbe"


@pytest.mark.parametrize("team_size", ["1", "10"])
def test_profile_form_accepts_team_size_1_and_10(team_size):
    """The smallest and the largest team size are allowed.

    1. Submit the form with team size 1 / 10
    2. Expect: the form is valid
    """
    form = WorkerProfileForm(valid_form_data(team_size=team_size))

    assert form.is_valid(), form.errors


@pytest.mark.parametrize("team_size", ["0", "11", "", "two"])
def test_profile_form_rejects_a_wrong_team_size(team_size):
    """Team size outside 1-10, empty or not a number is an error.

    1. Submit the form with team size 0 / 11 / empty / "two"
    2. Expect: the form is invalid with an error on team_size
    """
    form = WorkerProfileForm(valid_form_data(team_size=team_size))

    assert not form.is_valid()
    assert "team_size" in form.errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("skills", []),
        ("skills", ["juggling"]),
        ("languages", []),
        ("languages", ["xx"]),
        ("legal_status", ""),
        ("legal_status", "freelancer"),
    ],
)
def test_profile_form_rejects_empty_or_unknown_choices(field, value):
    """Each choice field needs at least one value from its list.

    1. Submit the form with no value / an unknown value for skills, languages or legal status
    2. Expect: the form is invalid with an error on that field
    """
    form = WorkerProfileForm(valid_form_data(**{field: value}))

    assert not form.is_valid()
    assert field in form.errors


# Name and phone form (R3, D5)


def test_name_and_phone_form_fields():
    """The second form on the page edits only the user's name and phone.

    1. Open an empty name and phone form
    2. Expect: only name and phone
    """
    assert list(NameAndPhoneForm().fields) == ["name", "phone"]


def test_name_is_required_phone_is_optional(worker):
    """A worker must give a name; the phone may stay empty.

    1. Submit the form with an empty name and an empty phone
    2. Expect: an error on name only
    3. Submit it with name "Ivan" and an empty phone
    4. Expect: valid, and the name is saved on the user
    """
    empty = NameAndPhoneForm({"name": "", "phone": ""}, instance=worker)
    assert not empty.is_valid()
    assert list(empty.errors) == ["name"]

    filled = NameAndPhoneForm({"name": "Ivan", "phone": ""}, instance=worker)
    assert filled.is_valid(), filled.errors
    filled.save()

    worker.refresh_from_db()
    assert worker.name == "Ivan"
    assert worker.phone == ""
