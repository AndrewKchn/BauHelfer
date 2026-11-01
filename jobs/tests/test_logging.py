"""Integration tests: posting and cancelling a job are logged with ids only (#124)."""

import pytest
from django.urls import reverse

from jobs.models import Application, Job

from .test_application import make_worker
from .test_notifications import confirmed
from .test_views import form_data, make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(124)]


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the employer."""
    client.force_login(employer)
    return client


def app_records(caplog):
    """The records our jobs app wrote, without Django's own ones."""
    return [r for r in caplog.records if r.name.startswith("jobs")]


def test_posting_a_job_is_logged_with_its_id_and_the_employer_id(
    employer_client, employer, caplog
):
    """Posting a job writes one INFO record with the job id and the employer id.

    1. Log in as an employer and post a correctly filled job form
    2. Expect: one INFO record "Job created: job_id=<id> employer_id=<id>"
    3. Expect: the employer's email is in no record
    """
    employer_client.post(reverse("job_create"), form_data())

    job = Job.objects.get()
    [record] = app_records(caplog)
    assert record.levelname == "INFO"
    assert record.getMessage() == (
        f"Job created: job_id={job.pk} employer_id={employer.pk}"
    )
    assert "anna@example.com" not in caplog.text


def test_invalid_job_form_is_not_logged(employer_client, caplog):
    """A form with errors saves nothing, so nothing is logged as created.

    1. Post the job form with an empty address
    2. Expect: no record from the jobs app
    """
    employer_client.post(reverse("job_create"), form_data(address=""))

    assert app_records(caplog) == []


def test_cancelling_a_job_is_logged_with_its_id_and_the_employer_id(
    employer_client, employer, caplog
):
    """Cancelling a job writes one INFO record with the job id and the employer id.

    1. Log in as the owner and confirm the cancel of an open job
    2. Expect: one INFO record "Job cancelled: job_id=<id> employer_id=<id>"
    3. Expect: the employer's email is in no record
    """
    job = make_job(employer)

    employer_client.post(reverse("job_cancel", args=[job.pk]))

    [record] = app_records(caplog)
    assert record.levelname == "INFO"
    assert record.getMessage() == (
        f"Job cancelled: job_id={job.pk} employer_id={employer.pk}"
    )
    assert "anna@example.com" not in caplog.text


@pytest.mark.story(22)
def test_applying_is_logged_with_ids_and_without_the_message(client, employer, caplog):
    """Applying writes INFO records with ids only, never the message (#22 spec R7, D9).

    1. Log in as a worker who can apply and send the apply form with a message
    2. Expect: two INFO records:
       "Application created: application_id=<id> job_id=<id> worker_id=<id>", then the
       employer's email "Notification sent: kind=new_application application_id=<id>" (#27)
    3. Expect: the message and the worker's email are in no record
    """
    job = make_job(confirmed(employer))  # only a confirmed address gets the email (#27)
    worker = make_worker()
    client.force_login(worker)

    client.post(
        reverse("job_apply", args=[job.pk]),
        {"workers_offered": 2, "message": "Call me on 0176 1234567"},
    )

    application = Application.objects.get()
    created = (
        f"Application created: application_id={application.pk} job_id={job.pk} "
        f"worker_id={worker.pk}"
    )
    sent = f"Notification sent: kind=new_application application_id={application.pk}"
    records = [(r.levelname, r.getMessage()) for r in app_records(caplog)]
    assert records == [("INFO", created), ("INFO", sent)]
    assert "0176" not in caplog.text
    assert "ivan@example.com" not in caplog.text


@pytest.mark.story(22)
def test_refused_application_is_not_logged(client, employer, caplog):
    """A form with errors saves nothing, so nothing is logged as created (#22).

    1. Log in as a crew of 3 and send the apply form with 3 workers to a job for 2
    2. Expect: no record from the jobs app
    """
    job = make_job(employer)
    client.force_login(make_worker())

    client.post(reverse("job_apply", args=[job.pk]), {"workers_offered": 3})

    assert app_records(caplog) == []
