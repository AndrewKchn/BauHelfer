"""Integration tests: the worker withdraws an application on "My applications" (#26).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/my-applications.md, iteration 2 (R18-R21, D4, D19, D20), acceptance
criteria AC15-AC18. The model's rules are in test_withdraw.py.
"""

import datetime

import pytest
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from jobs.models import Application, Job

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(26)]

MY_APPLICATIONS = reverse_lazy("my_applications")
WORKER_PHONE = "+49 151 2345678"
TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)


@pytest.fixture
def employer():
    """The employer who posted the job."""
    return make_employer("anna@example.com")


@pytest.fixture
def job(employer):
    """An open job next week for 3 workers."""
    return make_job(employer, workers_needed=3)


@pytest.fixture
def ivan():
    """The worker who withdraws, with a name and a phone."""
    worker = make_worker("ivan@example.com")
    worker.name = "Ivan Petrenko"
    worker.phone = WORKER_PHONE
    worker.save()
    return worker


@pytest.fixture
def ivan_client(client, ivan):
    """A browser logged in as Ivan."""
    client.force_login(ivan)
    return client


def apply(job, worker, status="pending"):
    """Save an application of `worker` to `job`; an accepted one takes 1 worker."""
    taken = 1 if status == "accepted" else 0
    return Application.objects.create(
        job=job, worker=worker, status=status, workers_accepted=taken
    )


def withdraw_url(application):
    """The withdraw URL of one application."""
    return reverse("application_withdraw", args=[application.pk])


def messages_of(response):
    """The texts of the messages shown on the page after the redirect."""
    return [str(message) for message in response.context["messages"]]


# The view (#26, docs/specs/my-applications.md R18; AC15)


def test_worker_withdraws_and_comes_back_to_my_applications(ivan_client, ivan, job):
    """A POST withdraws the worker's own application (R18).

    1. Save Ivan's pending application
    2. POST to its withdraw URL as Ivan, following the redirect
    3. Expect: back on "My applications" with "Application withdrawn."; it is withdrawn
    """
    application = apply(job, ivan)

    response = ivan_client.post(withdraw_url(application), follow=True)

    assertRedirects(response, MY_APPLICATIONS)
    assert messages_of(response) == ["Application withdrawn."]
    application.refresh_from_db()
    assert application.status == Application.Status.WITHDRAWN


def test_withdrawing_from_a_filled_job_opens_it(ivan_client, ivan, job):
    """Through the view too, the job opens again (R17, D18).

    1. Save Ivan's accepted application; set the job filled
    2. POST to its withdraw URL as Ivan
    3. Expect: the job is open
    """
    application = apply(job, ivan, "accepted")
    Job.objects.filter(pk=job.pk).update(status=Job.Status.FILLED)

    ivan_client.post(withdraw_url(application))

    job.refresh_from_db()
    assert job.status == Job.Status.OPEN


def test_application_that_cannot_be_withdrawn_says_so(ivan_client, ivan, job):
    """A rejected application stays; the worker is told (R18).

    1. Save Ivan's rejected application
    2. POST to its withdraw URL as Ivan, following the redirect
    3. Expect: back on "My applications" with "This application can no longer be
       withdrawn."; it is still rejected
    """
    application = apply(job, ivan, "rejected")

    response = ivan_client.post(withdraw_url(application), follow=True)

    assertRedirects(response, MY_APPLICATIONS)
    assert messages_of(response) == ["This application can no longer be withdrawn."]
    application.refresh_from_db()
    assert application.status == Application.Status.REJECTED


def test_other_workers_application_gets_404(client, job, ivan):
    """Only one's own application; another one is not even shown to exist (R18).

    1. Save Ivan's pending application
    2. POST to its withdraw URL as Olga
    3. Expect: 404; it is still pending
    """
    application = apply(job, ivan)
    client.force_login(make_worker("olga@example.com"))

    response = client.post(withdraw_url(application))

    assert response.status_code == 404
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING


def test_guest_is_sent_to_login(client, job, ivan):
    """A guest is asked to log in first.

    1. Save Ivan's pending application
    2. POST to its withdraw URL without logging in
    3. Expect: a redirect to the login page; it is still pending
    """
    application = apply(job, ivan)

    response = client.post(withdraw_url(application))

    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING


def test_employer_gets_403(client, employer, job, ivan):
    """Withdrawing is for workers only; the employer cancels instead.

    1. Save Ivan's accepted application
    2. POST to its withdraw URL as the job's employer
    3. Expect: 403
    """
    application = apply(job, ivan, "accepted")
    client.force_login(employer)

    assert client.post(withdraw_url(application)).status_code == 403


def test_get_is_not_allowed(ivan_client, ivan, job):
    """A link must not withdraw: only POST (R18).

    1. Save Ivan's pending application
    2. GET its withdraw URL as Ivan
    3. Expect: 405; it is still pending
    """
    application = apply(job, ivan)

    assert ivan_client.get(withdraw_url(application)).status_code == 405
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING


# The button (R19, D19; AC16)


@pytest.mark.parametrize("status", ["pending", "accepted", "closed"])
def test_application_in_play_has_a_withdraw_button(ivan_client, ivan, job, status):
    """While can_withdraw, the card has a "Withdraw" form (R19).

    1. Save Ivan's application in this status
    2. Open "My applications"
    3. Expect: a form posting to its withdraw URL with a "Withdraw" button
    """
    application = apply(job, ivan, status)

    response = ivan_client.get(MY_APPLICATIONS)

    assertContains(response, f'action="{withdraw_url(application)}"')
    assertContains(response, ">Withdraw</button>")


def test_withdraw_asks_the_browser_first(ivan_client, ivan, job):
    """A tap by mistake is caught by the browser's own dialog (R19).

    1. Save Ivan's pending application
    2. Open "My applications"
    3. Expect: the form has onsubmit="return confirm('Withdraw your application? This
       cannot be undone.')"
    """
    apply(job, ivan)

    response = ivan_client.get(MY_APPLICATIONS)

    assertContains(
        response,
        "onsubmit=\"return confirm('Withdraw your application? "
        "This cannot be undone.')\"",
    )


@pytest.mark.parametrize("status", ["rejected", "cancelled", "withdrawn"])
def test_closed_application_has_no_withdraw_button(ivan_client, ivan, job, status):
    """Nothing to withdraw: no button (R19).

    1. Save Ivan's application in this status
    2. Open "My applications"
    3. Expect: no form posting to its withdraw URL
    """
    application = apply(job, ivan, status)

    response = ivan_client.get(MY_APPLICATIONS)

    assertNotContains(response, withdraw_url(application))


def test_started_job_has_no_withdraw_button(ivan_client, ivan, employer):
    """After the start the button is gone (D17).

    1. Save Ivan's accepted application to a job that started yesterday
    2. Open "My applications"
    3. Expect: no form posting to its withdraw URL
    """
    application = apply(make_job(employer, date=TODAY - DAY), ivan, "accepted")

    response = ivan_client.get(MY_APPLICATIONS)

    assertNotContains(response, withdraw_url(application))


def test_job_page_has_no_withdraw_button(ivan_client, ivan, job):
    """The button is only on "My applications" (D19).

    1. Save Ivan's pending application
    2. Open the job's page as Ivan
    3. Expect: no form posting to its withdraw URL
    """
    application = apply(job, ivan)

    response = ivan_client.get(reverse("job_detail", args=[job.pk]))

    assertNotContains(response, withdraw_url(application))


# After withdrawing (R20, R21, D4, D20; AC17, AC18)


def test_employer_sees_withdrawn_without_buttons_or_phone(client, employer, job, ivan):
    """The employer sees that Ivan left, and can do nothing more with it (R20, D4).

    1. Save Ivan's withdrawn application to the job
    2. Open the job's page as its employer
    3. Expect: Ivan with a grey "Withdrawn" badge; no accept, reject or cancel form for
       it; no phone
    """
    application = apply(job, ivan, "withdrawn")
    client.force_login(employer)

    response = client.get(reverse("job_detail", args=[job.pk]))

    assertContains(response, "Ivan Petrenko")
    assertContains(response, 'badge-neutral">Withdrawn</span>')
    for name in ("application_accept", "application_reject", "application_cancel"):
        assertNotContains(response, reverse(name, args=[application.pk]))
    assertNotContains(response, WORKER_PHONE)


def test_worker_cannot_apply_again_after_withdrawing(ivan_client, ivan, job):
    """Withdrawn is final: the job page shows it, not the form (R21, D4).

    1. Save Ivan's withdrawn application
    2. Open the job's page as Ivan
    3. Expect: "You applied" with "Withdrawn"; no "Send application"
    """
    apply(job, ivan, "withdrawn")

    response = ivan_client.get(reverse("job_detail", args=[job.pk]))

    assertContains(response, "You applied")
    assertContains(response, ">Withdrawn</span>")
    assertNotContains(response, "Send application")


def test_withdrawn_tab_comes_after_cancelled_and_before_past(
    ivan_client, ivan, employer
):
    """The worker's tabs: … Cancelled, Withdrawn, Past (R21), grey (D20).

    1. Save Ivan's applications: past, withdrawn, cancelled (in this order)
    2. Open "My applications"
    3. Expect: the tabs cancelled, withdrawn, past; the withdrawn tab grey
    """
    apply(make_job(employer, date=TODAY - DAY), ivan)
    apply(make_job(employer), ivan, "withdrawn")
    apply(make_job(employer), ivan, "cancelled")

    response = ivan_client.get(MY_APPLICATIONS)

    statuses = [group["status"] for group in response.context["groups"]]
    assert statuses == ["cancelled", "withdrawn", "past"]
    assertContains(response, 'href="#tab-withdrawn"')
    assertContains(response, ">Withdrawn 1</a>")


def test_withdrawn_card_says_so(ivan_client, ivan, job):
    """The card says who ended it (R9, D16).

    1. Save Ivan's withdrawn application
    2. Open "My applications"
    3. Expect: "You withdrew this application."
    """
    apply(job, ivan, "withdrawn")

    response = ivan_client.get(MY_APPLICATIONS)

    assertContains(response, "You withdrew this application.")


# Log lines (#124)


def jobs_records(caplog):
    """The records our jobs app wrote, without Django's own ones."""
    return [r.getMessage() for r in caplog.records if r.name.startswith("jobs")]


def test_withdrawing_and_reopening_are_logged_with_ids_only(
    ivan_client, ivan, job, caplog
):
    """Withdraw and the reopened job each write one INFO line with ids.

    1. Save Ivan's accepted application; set the job filled
    2. Withdraw it as Ivan
    3. Expect: "Application withdrawn: application_id=… job_id=… worker_id=…" and "Job
       reopened: job_id=… worker_id=…"; Ivan's email is in no line
    """
    application = apply(job, ivan, "accepted")
    Job.objects.filter(pk=job.pk).update(status=Job.Status.FILLED)

    with caplog.at_level("INFO"):
        ivan_client.post(withdraw_url(application))

    records = jobs_records(caplog)
    assert (
        f"Application withdrawn: application_id={application.pk} job_id={job.pk} "
        f"worker_id={ivan.pk}"
    ) in records
    assert f"Job reopened: job_id={job.pk} worker_id={ivan.pk}" in records
    assert not any("ivan@example.com" in r for r in records)
