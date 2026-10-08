"""Integration tests: work-permit confirmation through the Django test client (#13).

Each test goes through the whole stack: middleware, URL, view, forms, template and database.
Acceptance criteria AC2-AC9 from docs/specs/work-permit.md.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from accounts.models import WorkerProfile

pytestmark = [pytest.mark.django_db, pytest.mark.story(13)]

User = get_user_model()

FIRST_CONFIRMATION = datetime(2026, 1, 5, 9, 30, tzinfo=ZoneInfo("Europe/Berlin"))
# How the page shows that date, in the same format the template uses.
FIRST_CONFIRMATION_TEXT = date_format(
    timezone.localtime(FIRST_CONFIRMATION), "SHORT_DATE_FORMAT"
)


@pytest.fixture
def worker():
    """A worker without profile and without confirmation."""
    return User.objects.create_user(
        email="ivan@example.com", password="x", role="worker", name="Ivan Petrov"
    )


@pytest.fixture
def worker_client(client, worker):
    """A browser logged in as the worker."""
    client.force_login(worker)
    return client


def make_profile(user):
    """Save a filled profile for `user`."""
    return WorkerProfile.objects.create(
        user=user,
        team_size=3,
        skills=["demolition", "carrying"],
        languages=["ru", "de"],
        legal_status="gewerbe",
    )


def confirm(user):
    """Give `user` a confirmation from 5 January 2026."""
    user.work_permit_confirmed_at = FIRST_CONFIRMATION
    user.save()


def form_data(**fields):
    """What the browser sends for a correctly filled worker profile form, box ticked."""
    return {
        "name": "Ivan Petrov",
        "phone": "",
        "work_permit": "on",
        "team_size": "3",
        "skills": ["demolition", "carrying"],
        "languages": ["ru", "de"],
        "legal_status": "gewerbe",
        **fields,
    }


def work_permit_input(html):
    """The <input> tag of the work-permit checkbox in `html`."""
    match = re.search(r'<input[^>]*name="work_permit"[^>]*>', html)
    assert match, "no work_permit checkbox on the page"
    return match.group()


# R2: the checkbox on the form


def test_form_shows_the_work_permit_checkbox(worker_client):
    """The worker profile form has the work-permit checkbox.

    1. Log in as a worker without a profile
    2. Open the profile form
    3. Expect: an unticked checkbox "I am allowed to work in Germany"
    """
    response = worker_client.get(reverse("worker_profile_edit"))

    assertContains(response, "I am allowed to work in Germany")
    tag = work_permit_input(response.content.decode())
    assert 'type="checkbox"' in tag
    assert "checked" not in tag


# AC2: without the box nothing is saved


def test_profile_is_not_saved_without_the_box(worker_client, worker):
    """Without the ticked box the profile and the date are not saved.

    1. Log in as a worker without a profile
    2. Send a correctly filled form without the work-permit box
    3. Expect: the form is shown again with an error on the box
    4. Expect: no profile, no confirmation date
    """
    data = form_data()
    del data["work_permit"]  # an unticked box is not sent at all

    response = worker_client.post(reverse("worker_profile_edit"), data)

    assert response.status_code == 200
    assert "work_permit" in response.context["user_form"].errors
    assert not WorkerProfile.objects.exists()
    worker.refresh_from_db()
    assert worker.work_permit_confirmed_at is None


# AC3, AC4: saving stores the first date


def test_ticking_the_box_saves_profile_and_date(worker_client, worker):
    """With the ticked box the profile and the confirmation date are saved.

    1. Log in as a worker without a profile
    2. Send the form with the box ticked
    3. Expect: redirect to "My profile"
    4. Expect: one profile; the confirmation date is now
    """
    before = timezone.now()

    response = worker_client.post(reverse("worker_profile_edit"), form_data())

    assertRedirects(response, reverse("worker_profile"))
    assert WorkerProfile.objects.filter(user=worker).exists()
    worker.refresh_from_db()
    assert before <= worker.work_permit_confirmed_at <= timezone.now()


def test_saving_again_keeps_the_first_date(worker_client, worker):
    """Editing the profile later does not move the confirmation date.

    1. Log in as a worker with a profile, confirmed on 5 January 2026
    2. Send the form again with a new phone
    3. Expect: the phone is saved; the date is still 5 January 2026
    """
    make_profile(worker)
    confirm(worker)

    worker_client.post(
        reverse("worker_profile_edit"), form_data(phone="+49 170 1234567")
    )

    saved = User.objects.get(pk=worker.pk)  # a fresh copy, only what is in the database
    assert saved.phone == "+49 170 1234567"
    assert saved.work_permit_confirmed_at == FIRST_CONFIRMATION


# AC5: a confirmed worker sees the box ticked


def test_confirmed_worker_sees_the_box_ticked(worker_client, worker):
    """The form of a confirmed worker starts with the box ticked.

    1. Log in as a worker with a profile and a confirmation
    2. Open the profile form
    3. Expect: the work-permit checkbox is ticked
    """
    make_profile(worker)
    confirm(worker)

    response = worker_client.get(reverse("worker_profile_edit"))

    assert "checked" in work_permit_input(response.content.decode())


# AC7: not for employers


def test_employer_form_has_no_work_permit_box(client):
    """Employers are not asked about a work permit.

    1. Log in as an employer
    2. Open the employer profile form
    3. Expect: no work-permit checkbox
    """
    employer = User.objects.create_user(
        email="boss@example.com", password="x", role="employer"
    )
    client.force_login(employer)

    response = client.get(reverse("employer_profile_edit"))

    assert response.status_code == 200
    assertNotContains(response, 'name="work_permit"')
    assertNotContains(response, "I am allowed to work in Germany")


# AC9: who sees what (D6)


def test_profile_page_shows_the_confirmation_date(worker_client, worker):
    """The worker's own page shows when they confirmed.

    1. Log in as a worker with a profile, confirmed on 5 January 2026
    2. Open "My profile"
    3. Expect: the confirmation and its date
    """
    make_profile(worker)
    confirm(worker)

    response = worker_client.get(reverse("worker_profile"))

    assertContains(response, "Allowed to work in Germany")
    assertContains(response, FIRST_CONFIRMATION_TEXT)


def test_profile_card_shows_confirmation_without_date(worker):
    """The card employers will see (#23) says "confirmed", without the date.

    1. Render the profile card of a confirmed worker
    2. Expect: "Confirmed by the worker", and not the date
    """
    profile = make_profile(worker)
    confirm(worker)

    html = render_to_string("accounts/_worker_profile_card.html", {"profile": profile})

    assert "Confirmed by the worker" in html
    assert FIRST_CONFIRMATION_TEXT not in html


def test_profile_card_of_an_unconfirmed_worker(worker):
    """A profile saved before this ticket shows "Not confirmed".

    1. Render the profile card of a worker with a profile and no confirmation
    2. Expect: "Not confirmed"
    """
    profile = make_profile(worker)

    html = render_to_string("accounts/_worker_profile_card.html", {"profile": profile})

    assert "Not confirmed" in html
    assert "Confirmed by the worker" not in html


# AC8: admin (R6)


def test_admin_shows_and_clears_the_confirmation(client, worker):
    """An admin sees the confirmation date and can clear it.

    1. A confirmed worker exists; an admin is logged in
    2. Open the worker in /admin/
    3. Expect: the date field with 5 January 2026
    4. Save the page with an empty date
    5. Expect: the worker has no confirmation and cannot apply
    """
    make_profile(worker)
    confirm(worker)
    client.force_login(
        User.objects.create_superuser(email="admin@example.com", password="x")
    )
    url = reverse("admin:accounts_user_change", args=[worker.pk])

    response = client.get(url)

    assertContains(response, 'name="work_permit_confirmed_at_0"')
    assertContains(response, 'value="2026-01-05"')

    response = client.post(
        url,
        {
            "email": worker.email,
            "name": worker.name,
            "role": "worker",
            "preferred_language": "en",
            "work_permit_confirmed_at_0": "",
            "work_permit_confirmed_at_1": "",
            "is_active": "on",
            "date_joined_0": worker.date_joined.strftime("%Y-%m-%d"),
            "date_joined_1": worker.date_joined.strftime("%H:%M:%S"),
            # The worker profile inline: one existing profile, sent back unchanged.
            "worker_profile-TOTAL_FORMS": "1",
            "worker_profile-INITIAL_FORMS": "1",
            "worker_profile-0-id": worker.worker_profile.pk,
            "worker_profile-0-user": worker.pk,
            "worker_profile-0-team_size": "3",
            "worker_profile-0-skills": ["demolition", "carrying"],
            "worker_profile-0-languages": ["ru", "de"],
            "worker_profile-0-legal_status": "gewerbe",
        },
    )

    assert response.status_code == 302, response.context["adminform"].form.errors
    worker.refresh_from_db()
    assert worker.work_permit_confirmed_at is None
    assert worker.can_apply() is False
