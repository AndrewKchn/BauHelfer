"""Integration tests: contacts on the job page, cancelling a job, the phone hint (#25).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/contacts.md (R2-R7, D1, D3, D6-D8, D10), acceptance criteria AC3-AC9. The
rule itself (Application.shows_contacts) and Job.cancel() are in test_contacts.py.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(25)]

User = get_user_model()

ADDRESS = "Lindwurmstraße 1"  # make_job's address
EMPLOYER_PHONE = "+49 170 7654321"
WORKER_PHONE = "+49 151 2345678"
ADDRESS_HIDDEN = "The exact address is shown after the employer accepts you."
PHONE_HINT = "Shown only to the people you work with, until the day of the job is over."
YESTERDAY = timezone.localdate() - datetime.timedelta(days=1)


@pytest.fixture
def employer():
    """The employer who posted the job, with a phone."""
    return make_employer("anna@example.com", name="Anna Huber", phone=EMPLOYER_PHONE)


@pytest.fixture
def job(employer):
    """An open job next week for 3 workers."""
    return make_job(employer, workers_needed=3)


def worker(email="ivan@example.com", phone=WORKER_PHONE):
    """A worker who can apply, with a phone."""
    user = make_worker(email)
    user.phone = phone
    user.save()
    return user


def apply(job, user, status="pending"):
    """Save an application of `user` to `job`; an accepted one takes 1 worker."""
    taken = 1 if status == "accepted" else 0
    return Application.objects.create(
        job=job, worker=user, status=status, workers_accepted=taken
    )


def detail_url(job):
    """The job's page."""
    return reverse("job_detail", args=[job.pk])


# The worker's side (R3, R5; AC4, AC5)


def test_accepted_worker_sees_the_address_and_the_employers_phone(client, job):
    """After acceptance the worker can find the place and call the employer (R3).

    1. Save an accepted application of Ivan to a job next week
    2. Open the job's page as Ivan
    3. Expect: the address and the employer's phone are there; the employer's email and
       the "shown after the employer accepts you" line are not
    """
    ivan = worker()
    apply(job, ivan, "accepted")
    client.force_login(ivan)

    response = client.get(detail_url(job))

    assertContains(response, ADDRESS)
    assertContains(response, EMPLOYER_PHONE)
    assertNotContains(response, "anna@example.com")
    assertNotContains(response, ADDRESS_HIDDEN)


@pytest.mark.parametrize("status", ["pending", "rejected", "closed", "cancelled"])
def test_worker_not_accepted_sees_no_contacts(client, job, status):
    """Before acceptance and after a cancel: no address, no phone (R3, D2; AC4).

    1. Save Ivan's application with this status
    2. Open the job's page as Ivan
    3. Expect: neither the address nor the employer's phone nor email
    """
    ivan = worker()
    apply(job, ivan, status)
    client.force_login(ivan)

    response = client.get(detail_url(job))

    assertNotContains(response, ADDRESS)
    assertNotContains(response, EMPLOYER_PHONE)
    assertNotContains(response, "anna@example.com")


def test_accepted_worker_sees_no_contacts_the_day_after_the_job(client, employer):
    """The day after the job the contacts are gone, the status stays (R1, D4; AC4).

    1. Save Ivan's accepted application to a job yesterday
    2. Open the job's page as Ivan
    3. Expect: neither the address nor the employer's phone; still "Accepted"
    """
    job = make_job(employer, date=YESTERDAY)
    ivan = worker()
    apply(job, ivan, "accepted")
    client.force_login(ivan)

    response = client.get(detail_url(job))

    assertNotContains(response, ADDRESS)
    assertNotContains(response, EMPLOYER_PHONE)
    assertContains(response, "Accepted")


def test_employer_without_a_phone_is_shown_as_not_given(client):
    """An employer who gave no phone shares none (D1; AC5).

    1. Save a job of an employer without a phone and Ivan's accepted application
    2. Open the job's page as Ivan
    3. Expect: the address and "not given" for the phone
    """
    job = make_job(make_employer("karl@example.com"))
    ivan = worker()
    apply(job, ivan, "accepted")
    client.force_login(ivan)

    response = client.get(detail_url(job))

    assertContains(response, ADDRESS)
    assertContains(response, "not given")


def test_employer_without_a_profile_shows_the_phone_under_the_name(client):
    """A job made in the admin by an employer without a profile still shows the phone (R3).

    1. Save a job of an employer with a phone and no company profile, and Ivan's accepted
       application
    2. Open the job's page as Ivan
    3. Expect: the employer's name and phone
    """
    karl = User.objects.create_user(
        email="karl@example.com",
        password="x",
        role="employer",
        name="Karl Meier",
        phone=EMPLOYER_PHONE,
    )
    job = make_job(karl)
    ivan = worker()
    apply(job, ivan, "accepted")
    client.force_login(ivan)

    response = client.get(detail_url(job))

    assertContains(response, "Karl Meier")
    assertContains(response, EMPLOYER_PHONE)


# The employer's side (R4, R5, D6; AC6)


def test_owner_sees_the_phone_of_an_accepted_worker_only(client, employer, job):
    """The phone is in the accepted application, not in the others (R4).

    1. On a job next week, save Ivan's accepted application and pending, rejected and
       cancelled ones of three other workers, each with their own phone
    2. Open the job's page as its employer
    3. Expect: Ivan's phone is there; the other phones and every email are not
    """
    apply(job, worker(), "accepted")
    others = {
        "pending": "+49 151 1111111",
        "rejected": "+49 151 2222222",
        "cancelled": "+49 151 3333333",
    }
    for status, phone in others.items():
        apply(job, worker(f"{status}@example.com", phone), status)
    client.force_login(employer)

    response = client.get(detail_url(job))

    assertContains(response, WORKER_PHONE)
    for status, phone in others.items():
        assertNotContains(response, phone)
        assertNotContains(response, f"{status}@example.com")
    assertNotContains(response, "ivan@example.com")


def test_owner_sees_no_phone_the_day_after_the_job(client, employer):
    """The day after the job the worker's phone is gone too (D4; AC6).

    1. Save Ivan's accepted application to a job yesterday
    2. Open the job's page as its employer
    3. Expect: Ivan's phone is not there
    """
    job = make_job(employer, date=YESTERDAY)
    apply(job, worker(), "accepted")
    client.force_login(employer)

    response = client.get(detail_url(job))

    assertNotContains(response, WORKER_PHONE)


def test_accepted_worker_without_a_phone_is_shown_as_not_given(client, employer, job):
    """A worker who gave no phone shares none (D1; AC6).

    1. Save an accepted application of a worker without a phone
    2. Open the job's page as its employer
    3. Expect: "not given" in the application
    """
    apply(job, worker(phone=""), "accepted")
    client.force_login(employer)

    response = client.get(detail_url(job))

    assertContains(response, "not given")


# Everyone else (AC7)


@pytest.mark.parametrize("who", ["guest", "other worker"], ids=lambda who: who)
def test_others_see_no_contacts_of_an_accepted_worker(client, employer, job, who):
    """Someone else's acceptance reveals nothing to a guest or another worker (AC7).

    1. Save Ivan's accepted application
    2. Open the job's page as a guest or as another worker
    3. Expect: neither the address nor either phone
    """
    apply(job, worker(), "accepted")
    if who == "other worker":
        client.force_login(worker("olga@example.com", "+49 151 9999999"))

    response = client.get(detail_url(job))

    assertNotContains(response, ADDRESS)
    assertNotContains(response, EMPLOYER_PHONE)
    assertNotContains(response, WORKER_PHONE)


# The "shown after the employer accepts you" line (R6, D8; AC8)


@pytest.mark.parametrize(
    ("status", "shown"),
    [
        (None, True),
        ("pending", True),
        ("closed", True),
        ("rejected", False),
        ("cancelled", False),
    ],
    ids=["no application", "pending", "closed", "rejected", "cancelled"],
)
def test_address_hint_only_for_who_can_still_be_accepted(client, job, status, shown):
    """No promise of the address to a worker who will not be accepted (R6, D8).

    1. Log in as a worker without an application or with one in this status
    2. Open the job's page
    3. Expect: the "shown after the employer accepts you" line only when the worker can
       still be accepted
    """
    ivan = worker()
    if status:
        apply(job, ivan, status)
    client.force_login(ivan)

    response = client.get(detail_url(job))

    assert (ADDRESS_HIDDEN in response.content.decode()) is shown


def test_address_hint_not_shown_the_day_after_the_job(client, employer):
    """An accepted worker of a past job gets no address line at all (R6).

    1. Save Ivan's accepted application to a job yesterday
    2. Open the job's page as Ivan
    3. Expect: no "shown after the employer accepts you" line
    """
    job = make_job(employer, date=YESTERDAY)
    ivan = worker()
    apply(job, ivan, "accepted")
    client.force_login(ivan)

    response = client.get(detail_url(job))

    assertNotContains(response, ADDRESS_HIDDEN)


# Cancelling the job (R2, D3; AC3)


def test_cancelling_a_job_takes_the_contacts_from_its_workers(client, employer, job):
    """The owner cancels the job; the accepted worker no longer sees contacts (D3).

    1. Save Ivan's accepted application
    2. POST to the job's cancel URL as its employer
    3. Expect: Ivan's application is cancelled
    4. Open the job's page as Ivan
    5. Expect: neither the address nor the employer's phone
    """
    ivan = worker()
    application = apply(job, ivan, "accepted")
    client.force_login(employer)

    client.post(reverse("job_cancel", args=[job.pk]))

    application.refresh_from_db()
    assert application.status == Application.Status.CANCELLED
    client.force_login(ivan)
    response = client.get(detail_url(job))
    assertNotContains(response, ADDRESS)
    assertNotContains(response, EMPLOYER_PHONE)


# The phone hint (R7, D10; AC9)


@pytest.mark.parametrize("role", ["worker", "employer"])
def test_profile_form_says_who_sees_the_phone(client, role):
    """Under the phone field the user reads who will see it (R7).

    1. Log in as a worker / an employer without a profile
    2. Open the profile form
    3. Expect: the format example and the line about who sees the phone
    """
    user = User.objects.create_user(
        email=f"{role}@example.com", password="x", role=role
    )
    client.force_login(user)

    response = client.get(reverse(f"{role}_profile_edit"))

    assertContains(response, "For example +49 151 12345678 or 0151 12345678.")
    assertContains(response, PHONE_HINT)
