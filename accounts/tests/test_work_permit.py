"""Unit tests: work-permit confirmation on the user, its form and the migration (#13).

Spec: docs/specs/work-permit.md (requirements R1-R8, decisions D1-D7).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from accounts.forms import WorkerUserForm
from accounts.models import WorkerProfile

pytestmark = [pytest.mark.django_db, pytest.mark.story(13)]

User = get_user_model()

FIRST_CONFIRMATION = datetime(2026, 1, 5, 9, 30, tzinfo=ZoneInfo("Europe/Berlin"))


@pytest.fixture
def worker():
    """A worker who has not confirmed the work permit yet."""
    return User.objects.create_user(
        email="worker@example.com", password="x", role="worker", name="Ivan"
    )


def make_profile(user):
    """Save a valid worker profile for `user`."""
    return WorkerProfile.objects.create(
        user=user,
        team_size=1,
        skills=["demolition"],
        languages=["de"],
        legal_status="minijob",
    )


# Model (R1, AC1)


def test_new_user_has_no_confirmation():
    """A new account has no work-permit confirmation.

    1. Create a user with only email and password
    2. Expect: work_permit_confirmed_at is empty
    """
    user = User.objects.create_user(email="anna@example.com", password="x")

    assert user.work_permit_confirmed_at is None


def test_old_boolean_field_is_gone():
    """The old yes/no field is replaced by the date (D2).

    1. Look for the field work_permit_confirmed on the User model
    2. Expect: it does not exist; work_permit_confirmed_at does
    """
    field_names = [field.name for field in User._meta.get_fields()]

    assert "work_permit_confirmed" not in field_names
    assert "work_permit_confirmed_at" in field_names


# WorkerUserForm (R2, R3, D4, D5)


def test_worker_user_form_fields():
    """The worker's user form adds a required checkbox to name and phone.

    1. Open an empty WorkerUserForm
    2. Expect: fields name, phone, work_permit
    3. Expect: work_permit is a required checkbox
    """
    form = WorkerUserForm()

    assert list(form.fields) == ["name", "phone", "work_permit"]
    field = form.fields["work_permit"]
    assert isinstance(field, forms.BooleanField)
    assert field.required is True
    assert isinstance(field.widget, forms.CheckboxInput)


def test_form_without_the_box_is_invalid(worker):
    """Without the ticked box the form is not valid.

    1. Submit the form with a name and no work_permit
    2. Expect: the form is invalid with an error on work_permit only
    """
    form = WorkerUserForm({"name": "Ivan", "phone": ""}, instance=worker)

    assert not form.is_valid()
    assert list(form.errors) == ["work_permit"]


def test_ticking_the_box_saves_the_date(worker):
    """The first confirmation stores the current date and time.

    1. Submit the form with the box ticked and save it
    2. Expect: work_permit_confirmed_at is between the start and the end of the test
    """
    before = timezone.now()
    form = WorkerUserForm({"name": "Ivan", "work_permit": "on"}, instance=worker)

    assert form.is_valid(), form.errors
    form.save()

    worker.refresh_from_db()
    assert before <= worker.work_permit_confirmed_at <= timezone.now()


@pytest.mark.story(14)  # found by the coverage review: this branch had no test
def test_save_without_commit_does_not_write_to_the_database(worker):
    """save(commit=False) fills in the date but leaves the database to the caller.

    1. Submit the form with the box ticked, call save(commit=False)
    2. Expect: the returned user has the date
    3. Expect: the database still has no date
    """
    form = WorkerUserForm({"name": "Ivan", "work_permit": "on"}, instance=worker)

    assert form.is_valid(), form.errors
    user = form.save(commit=False)

    assert user.work_permit_confirmed_at is not None
    worker.refresh_from_db()
    assert worker.work_permit_confirmed_at is None


def test_saving_again_keeps_the_first_date(worker):
    """A worker who confirmed earlier keeps the first date (D5).

    1. A worker confirmed on 5 January 2026
    2. Submit the form again with the box ticked and a new phone, and save it
    3. Expect: the date is still 5 January 2026; the phone is new
    """
    worker.work_permit_confirmed_at = FIRST_CONFIRMATION
    worker.save()
    form = WorkerUserForm(
        {"name": "Ivan", "phone": "+49 170 1234567", "work_permit": "on"},
        instance=worker,
    )

    assert form.is_valid(), form.errors
    form.save()

    worker.refresh_from_db()
    assert worker.work_permit_confirmed_at == FIRST_CONFIRMATION
    assert worker.phone == "+49 170 1234567"


def test_box_is_ticked_only_for_a_confirmed_worker(worker):
    """The checkbox starts ticked once the worker has confirmed.

    1. Open the form for a worker without confirmation
    2. Expect: the box is not ticked
    3. Give the worker a confirmation date and open the form again
    4. Expect: the box is ticked
    """
    assert WorkerUserForm(instance=worker)["work_permit"].value() is False

    worker.work_permit_confirmed_at = FIRST_CONFIRMATION
    worker.save()

    assert WorkerUserForm(instance=worker)["work_permit"].value() is True


# can_apply() (R5, D3, AC6)


@pytest.mark.parametrize(
    ("role", "has_profile", "confirmed", "expected"),
    [
        ("worker", True, True, True),
        ("worker", True, False, False),
        ("worker", False, True, False),
        ("employer", False, True, False),
        ("", False, True, False),
    ],
    ids=[
        "worker-with-profile-and-confirmation",
        "worker-without-confirmation",
        "worker-without-profile",
        "employer",
        "no-role",
    ],
)
def test_can_apply(role, has_profile, confirmed, expected):
    """Only a worker with a profile and a confirmation can apply (#22 uses this).

    1. Create a user with the given role, with or without profile and confirmation
    2. Expect: can_apply() is True only for a worker with both
    """
    user = User.objects.create_user(email="u@example.com", password="x", role=role)
    if confirmed:
        user.work_permit_confirmed_at = FIRST_CONFIRMATION
        user.save()
    if has_profile:
        make_profile(user)

    assert user.can_apply() is expected


# Migration (R1, D7, AC10)

BEFORE = ("accounts", "0003_employer_profile")
AFTER = ("accounts", "0004_work_permit_confirmed_at")


@pytest.mark.django_db(transaction=True)  # the test changes the tables themselves
def test_migration_keeps_existing_confirmations():
    """Users who had the old box ticked get a date; the others stay empty (D7).

    1. Move the database back to before this ticket's migration
    2. Create one user with work_permit_confirmed = True and one without
    3. Run the migration
    4. Expect: the first user has a date from the migration run, the second has none
    """
    executor = MigrationExecutor(connection)
    try:
        executor.migrate([BEFORE])
        old_apps = executor.loader.project_state([BEFORE]).apps
        OldUser = old_apps.get_model("accounts", "User")
        OldUser.objects.create(email="yes@example.com", work_permit_confirmed=True)
        OldUser.objects.create(email="no@example.com")

        before = timezone.now()
        executor = MigrationExecutor(connection)  # re-read which migrations are applied
        executor.migrate([AFTER])
        new_apps = executor.loader.project_state([AFTER]).apps
        NewUser = new_apps.get_model("accounts", "User")

        confirmed_at = NewUser.objects.get(
            email="yes@example.com"
        ).work_permit_confirmed_at
        assert before <= confirmed_at <= timezone.now()
        assert (
            NewUser.objects.get(email="no@example.com").work_permit_confirmed_at is None
        )
    finally:
        # Leave the database fully migrated for the next tests.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
