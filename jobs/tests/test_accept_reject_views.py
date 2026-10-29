"""Integration tests: the employer accepts or rejects an application on the job page (#24).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/accept-reject.md, iteration 1 (R5-R10, D1, D3, D5, D8, D9, D15),
acceptance criteria AC6-AC8. The model's rules are in test_accept_reject.py.
"""

import re

import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, ApplicationStateError, Job

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(24)]

ACTIONS = ["application_accept", "application_reject"]


@pytest.fixture
def employer():
    """The employer who posted the job."""
    return make_employer("anna@example.com")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the job's employer."""
    client.force_login(employer)
    return client


@pytest.fixture
def job(employer):
    """An open demolition job next week for 3 workers."""
    return make_job(employer, workers_needed=3)


def apply(job, email, name, workers_offered=1, **fields):
    """Save an application to `job` from a new crew of 3 called `name`."""
    worker = make_worker(email)
    worker.name = name
    worker.save()
    return Application.objects.create(
        job=job, worker=worker, workers_offered=workers_offered, **fields
    )


def action_url(name, application):
    """The accept or reject URL of one application."""
    return reverse(name, args=[application.pk])


def detail_url(job):
    """The job's page."""
    return reverse("job_detail", args=[job.pk])


def back_url(application):
    """The job's page, scrolled to this application (spec R6, D8)."""
    return f"{detail_url(application.job)}#application-{application.pk}"


# Accept and reject (R5, R6, D8; AC6)


def test_owner_accepts_a_crew_and_comes_back_to_it(employer_client, job):
    """Accept saves the decision and goes back to the same application with a message.

    1. Save a pending crew of Ivan offering 2 workers to a job for 3
    2. POST to its accept URL as the job's employer
    3. Expect: the application is accepted with 2 workers; a redirect to the job's page at
       #application-<id>
    4. Expect: the job's page says "Accepted: 2 workers from Ivan Petrenko."
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko", 2)

    response = employer_client.post(action_url("application_accept", application))

    application.refresh_from_db()
    assert application.status == Application.Status.ACCEPTED
    assert application.workers_accepted == 2
    assert response.status_code == 302
    assert response.url == back_url(application)
    page = employer_client.get(detail_url(job))
    assertContains(page, "Accepted: 2 workers from Ivan Petrenko.")


def test_accepting_the_last_places_says_the_job_is_filled(employer_client, job):
    """When the job fills, the employer is told that the others were closed (spec R6).

    1. On a job for 3, save an accepted crew of 2, a pending Ivan and a pending Olga
    2. Accept Ivan
    3. Expect: the job is filled, Olga's application closed
    4. Expect: the job's page says "Accepted: 1 worker from Ivan Petrenko." and "The job is
       filled. The other pending applications were closed."
    """
    apply(job, "a@example.com", "Crew", 2, status="accepted", workers_accepted=2)
    ivan = apply(job, "ivan@example.com", "Ivan Petrenko")
    olga = apply(job, "olga@example.com", "Olga Popescu")

    employer_client.post(action_url("application_accept", ivan))

    job.refresh_from_db()
    olga.refresh_from_db()
    assert job.status == Job.Status.FILLED
    assert olga.status == Application.Status.CLOSED
    page = employer_client.get(detail_url(job))
    assertContains(page, "Accepted: 1 worker from Ivan Petrenko.")
    assertContains(
        page, "The job is filled. The other pending applications were closed."
    )


def test_owner_rejects_an_application_and_comes_back_to_it(employer_client, job):
    """Reject saves the decision and goes back to the same application with a message.

    1. Save a pending application of Ivan
    2. POST to its reject URL as the job's employer
    3. Expect: the application is rejected; a redirect to the job's page at its anchor
    4. Expect: the job's page says "Rejected: Ivan Petrenko."
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")

    response = employer_client.post(action_url("application_reject", application))

    application.refresh_from_db()
    assert application.status == Application.Status.REJECTED
    assert response.url == back_url(application)
    page = employer_client.get(detail_url(job))
    assertContains(page, "Rejected: Ivan Petrenko.")


@pytest.mark.parametrize(
    ("name", "method"), [(ACTIONS[0], "accept"), (ACTIONS[1], "reject")]
)
def test_decision_made_meanwhile_is_reported(
    employer_client, job, monkeypatch, name, method
):
    """A decision that lost the race says so instead of failing (spec R6, D6).

    1. Save a pending application; make its accept() / reject() raise
       ApplicationStateError, as when another tab decided it a moment earlier
    2. POST to the accept / reject URL as the job's employer
    3. Expect: a redirect to the application on the job's page, which says "This
       application was already decided."
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")

    def decided_meanwhile(self):
        raise ApplicationStateError

    monkeypatch.setattr(Application, method, decided_meanwhile)

    response = employer_client.post(action_url(name, application))

    assert response.url == back_url(application)
    page = employer_client.get(detail_url(job))
    assertContains(page, "This application was already decided.")


# Who may decide (R5, D5; AC7)


@pytest.mark.parametrize("name", ACTIONS)
def test_guest_is_sent_to_login(client, job, name):
    """A guest's POST changes nothing and goes to the login page.

    1. Save a pending application
    2. POST to its accept / reject URL without logging in
    3. Expect: a redirect to login; the application is still pending
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")

    response = client.post(action_url(name, application))

    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING


@pytest.mark.parametrize("name", ACTIONS)
def test_worker_gets_403(client, job, name):
    """A worker, even the one who applied, cannot decide.

    1. Save a pending application of Ivan
    2. Log in as Ivan and POST to its accept / reject URL
    3. Expect: 403; the application is still pending
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")
    client.force_login(application.worker)

    response = client.post(action_url(name, application))

    assert response.status_code == 403
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING


@pytest.mark.parametrize("name", ACTIONS)
def test_other_employer_gets_404(client, job, name):
    """Another employer cannot even tell that the application exists (spec R5).

    1. Save a pending application to Anna's job
    2. Log in as another employer and POST to its accept / reject URL
    3. Expect: 404; the application is still pending
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")
    client.force_login(make_employer("bob@example.com"))

    response = client.post(action_url(name, application))

    assert response.status_code == 404
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING


@pytest.mark.parametrize("name", ACTIONS)
def test_unknown_application_gets_404(employer_client, name):
    """An id that does not exist gives 404.

    1. POST to the accept / reject URL of application 999999 as an employer
    2. Expect: 404
    """
    response = employer_client.post(reverse(name, args=[999999]))

    assert response.status_code == 404


@pytest.mark.parametrize("name", ACTIONS)
@pytest.mark.parametrize("status", ["accepted", "rejected", "closed"])
def test_decided_application_gets_404(employer_client, job, name, status):
    """Only a pending application can be decided (spec R5).

    1. Save an application that is already accepted, rejected or closed
    2. POST to its accept / reject URL as the job's employer
    3. Expect: 404; the status is unchanged
    """
    taken = 1 if status == "accepted" else 0
    application = apply(
        job, "ivan@example.com", "Ivan Petrenko", status=status, workers_accepted=taken
    )

    response = employer_client.post(action_url(name, application))

    assert response.status_code == 404
    application.refresh_from_db()
    assert application.status == status


@pytest.mark.parametrize("name", ACTIONS)
@pytest.mark.parametrize("status", ["filled", "done", "cancelled"])
def test_job_that_is_not_open_gets_404(employer_client, job, name, status):
    """Decisions only on an open job (spec D5).

    1. Save a pending application, then set the job filled, done or cancelled
    2. POST to its accept / reject URL as the job's employer
    3. Expect: 404; the application is still pending
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")
    Job.objects.filter(pk=job.pk).update(status=status)

    response = employer_client.post(action_url(name, application))

    assert response.status_code == 404
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING


@pytest.mark.parametrize("name", ACTIONS)
def test_get_is_not_allowed(employer_client, job, name):
    """A link or a prefetching browser must not decide: only POST (spec R5).

    1. Save a pending application
    2. GET its accept / reject URL as the job's employer
    3. Expect: 405; the application is still pending
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")

    response = employer_client.get(action_url(name, application))

    assert response.status_code == 405
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING


# The buttons on the job page (R7-R9, D1, D9; AC8)


def test_pending_application_has_accept_and_reject_buttons(employer_client, job):
    """A pending application of an open job gets both forms (spec R7).

    1. Save a pending crew of Ivan offering 2 workers to a job for 3
    2. Open the job's page as its employer
    3. Expect: the application has id="application-<id>"; a form posting to its accept URL
       with "Accept 2" and one posting to its reject URL with "Reject"
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko", 2)

    response = employer_client.get(detail_url(job))

    assertContains(response, f'id="application-{application.pk}"')
    assertContains(
        response, f'action="{action_url("application_accept", application)}"'
    )
    assertContains(
        response, f'action="{action_url("application_reject", application)}"'
    )
    assertContains(response, "Accept 2")
    assertContains(response, "Reject")


def test_reject_asks_the_browser_first(employer_client, job):
    """A Reject tap by mistake is caught by the browser's own dialog (spec D27).

    1. Save a pending application of Ivan O'Brien
    2. Open the job's page as its employer
    3. Expect: the reject form has onsubmit="return confirm(…)" with "Reject Ivan
       O'Brien? This cannot be undone.", the apostrophe escaped for JavaScript only;
       the accept form has no onsubmit
    """
    application = apply(job, "ivan@example.com", "Ivan O'Brien")

    response = employer_client.get(detail_url(job))

    reject = action_url("application_reject", application)
    assertContains(
        response,
        f'action="{reject}" onsubmit="return confirm(\'Reject Ivan O\\u0027Brien? '
        "This cannot be undone.')\"",
    )
    accept = action_url("application_accept", application)
    assertContains(response, f'action="{accept}">')


def test_crew_bigger_than_the_places_left_gets_accept_part(employer_client, job):
    """The button says how many of the crew are taken (spec R7, D1).

    1. On a job for 3, save an accepted crew of 2 and a pending crew of Ivan offering 2
    2. Open the job's page as its employer
    3. Expect: "Accept 1 of 2"
    """
    apply(job, "a@example.com", "Crew", 2, status="accepted", workers_accepted=2)
    apply(job, "ivan@example.com", "Ivan Petrenko", 2)

    response = employer_client.get(detail_url(job))

    assertContains(response, "Accept 1 of 2")


def test_warning_shown_only_when_accepting_fills_the_job(employer_client, job):
    """The employer is told before the tap that the others will be closed (spec R8, D9).

    1. On a job for 3, save a pending crew of Ivan offering 2: the page has no warning
    2. Accept another worker, so 2 places are left: Ivan's crew would fill the job
    3. Expect: now the page says "Accepting fills the job: the other pending applications
       will be closed."
    """
    apply(job, "ivan@example.com", "Ivan Petrenko", 2)
    warning = "Accepting fills the job: the other pending applications will be closed."

    assertNotContains(employer_client.get(detail_url(job)), warning)

    apply(job, "a@example.com", "Solo", 1, status="accepted", workers_accepted=1)

    assertContains(employer_client.get(detail_url(job)), warning)


@pytest.mark.parametrize("status", ["accepted", "rejected", "closed"])
def test_decided_application_has_no_buttons(employer_client, job, status):
    """Buttons only on pending applications (spec R7).

    1. Save an accepted, rejected or closed application
    2. Open the job's page as its employer
    3. Expect: no form posting to its accept or reject URL
    """
    taken = 1 if status == "accepted" else 0
    application = apply(
        job, "ivan@example.com", "Ivan Petrenko", status=status, workers_accepted=taken
    )

    response = employer_client.get(detail_url(job))

    assertNotContains(response, action_url("application_accept", application))
    assertNotContains(response, action_url("application_reject", application))


def test_job_that_is_not_open_has_no_buttons(employer_client, job):
    """A cancelled job's applications are history (spec D5).

    1. Save a pending application, then cancel the job
    2. Open the job's page as its employer
    3. Expect: no accept or reject form
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")
    Job.objects.filter(pk=job.pk).update(status=Job.Status.CANCELLED)

    response = employer_client.get(detail_url(job))

    assertNotContains(response, action_url("application_accept", application))
    assertNotContains(response, action_url("application_reject", application))


def test_part_of_a_crew_accepted_is_shown(employer_client, job):
    """The employer sees that only part of the crew was taken (spec R9).

    1. Save an accepted crew of Ivan offering 2 with 1 taken
    2. Open the job's page as its employer
    3. Expect: "Accepted" and "1 of 2 workers" in place of "2 workers" (D22)
    """
    apply(
        job,
        "ivan@example.com",
        "Ivan Petrenko",
        2,
        status="accepted",
        workers_accepted=1,
    )

    response = employer_client.get(detail_url(job))

    assertContains(response, "Accepted")
    assertContains(response, "1 of 2 workers")
    # "2 workers" right after a tag would be the plain count, which it replaces.
    assert not re.search(r">\s*2 workers", response.content.decode())


def test_closed_application_says_job_filled(employer_client, job):
    """An application closed when the job filled shows why (spec D15).

    1. Save a closed application
    2. Open the job's page as its employer
    3. Expect: "Job filled"
    """
    apply(job, "ivan@example.com", "Ivan Petrenko", status="closed")

    response = employer_client.get(detail_url(job))

    assertContains(response, "Job filled")


# Log lines (R10)


def jobs_records(caplog):
    """The records our jobs app wrote, without Django's own ones."""
    return [r.getMessage() for r in caplog.records if r.name.startswith("jobs")]


def test_accepting_and_filling_are_logged_with_ids_only(
    employer_client, employer, job, caplog
):
    """Accept and the filled job each write one INFO line with ids (#124).

    1. On a job for 3, save an accepted crew of 2 and a pending Ivan
    2. Accept Ivan as the job's employer
    3. Expect: "Application accepted: application_id=… job_id=… employer_id=…
       workers=1" and "Job filled: job_id=… employer_id=…"
    4. Expect: Ivan's email is in no line
    """
    apply(job, "a@example.com", "Crew", 2, status="accepted", workers_accepted=2)
    ivan = apply(job, "ivan@example.com", "Ivan Petrenko")

    with caplog.at_level("INFO"):
        employer_client.post(action_url("application_accept", ivan))

    records = jobs_records(caplog)
    assert (
        f"Application accepted: application_id={ivan.pk} job_id={job.pk} "
        f"employer_id={employer.pk} workers=1"
    ) in records
    assert f"Job filled: job_id={job.pk} employer_id={employer.pk}" in records
    assert not any("ivan@example.com" in r for r in records)


def test_rejecting_is_logged_with_ids_only(employer_client, employer, job, caplog):
    """Reject writes one INFO line with ids (#124).

    1. Save a pending application of Ivan
    2. Reject it as the job's employer
    3. Expect: "Application rejected: application_id=… job_id=… employer_id=…"
    """
    ivan = apply(job, "ivan@example.com", "Ivan Petrenko")

    with caplog.at_level("INFO"):
        employer_client.post(action_url("application_reject", ivan))

    assert (
        f"Application rejected: application_id={ivan.pk} job_id={job.pk} "
        f"employer_id={employer.pk}"
    ) in jobs_records(caplog)


# How an application looks (D21-D24)


@pytest.mark.parametrize(
    ("status", "colour"),
    [
        ("pending", "badge-warning"),
        ("accepted", "badge-success"),
        ("closed", "badge-info"),
        ("rejected", "badge-error"),
    ],
)
def test_status_badge_has_the_colour_of_its_status(
    employer_client, job, status, colour
):
    """Each status has its own colour, as the job statuses on "My jobs" (spec D21).

    1. Save an application in the given status
    2. Open the job's page as its employer
    3. Expect: the status badge carries the status's colour class
    """
    taken = 1 if status == "accepted" else 0
    application = apply(
        job, "ivan@example.com", "Ivan Petrenko", status=status, workers_accepted=taken
    )

    response = employer_client.get(detail_url(job))

    badge = f'{colour}">{application.get_status_display()}</span>'
    assertContains(response, badge)


def test_worker_sees_the_coloured_badge_of_their_application(client, job):
    """The worker's own application uses the same badge (spec D21).

    1. Save a rejected application of Ivan
    2. Open the job's page as Ivan
    3. Expect: "Rejected" in red (badge-error)
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko", status="rejected")
    client.force_login(application.worker)

    response = client.get(detail_url(job))

    assertContains(response, 'badge-error">Rejected</span>')


@pytest.mark.parametrize(
    ("status", "colour"),
    [
        ("filled", "badge-info"),
        ("done", "badge-secondary"),
        ("cancelled", "badge-error"),
    ],
)
def test_closed_job_status_has_its_colour(client, job, status, colour):
    """A filled, done or cancelled job shows its status in the "My jobs" colour (D24).

    1. Set the job filled, done or cancelled
    2. Open its page as a guest
    3. Expect: the status badge carries the status's colour class
    """
    Job.objects.filter(pk=job.pk).update(status=status)
    job.refresh_from_db()

    response = client.get(detail_url(job))

    assertContains(response, f'{colour}">{job.get_status_display()}</span>')


def test_application_shows_neither_crew_size_nor_confirmed_permit(employer_client, job):
    """Only what tells applications apart: no crew size, no "permit confirmed" (D22, D23).

    1. Save an application of Ivan, a crew of 3 with a confirmed permit, bringing 2
    2. Open the job's page as its employer
    3. Expect: "2 workers"; no "Crew of 3", "crew of 3" or "Work permit"
    """
    apply(job, "ivan@example.com", "Ivan Petrenko", 2)

    response = employer_client.get(detail_url(job))

    assertContains(response, "2 workers")
    assertNotContains(response, "rew of 3")
    assertNotContains(response, "Work permit")
