"""E2E tests: the M4 application flows in a real browser (Chromium via Playwright) (#28).

A worker and an employer act at the same time, each on their own 360 px phone: two browser
contexts, each with its own cookies, so both stay logged in. The emails the flow sends land
in the test mailbox (`mailoutbox`): the live server runs in this test process.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from playwright.sync_api import expect

from accounts.models import EmployerProfile, WorkerProfile
from jobs.models import Application
from jobs.tests.test_views import make_job

from .helpers import PASSWORD, PHONE, assert_fits_the_screen, log_in

pytestmark = [pytest.mark.django_db, pytest.mark.story(28)]

User = get_user_model()

EMPLOYER_PHONE = "+49 170 1111111"
WORKER_PHONE = "+49 170 2222222"


def make_employer(email="anna@example.com"):
    """An employer with a company profile, a phone and a confirmed email."""
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        role="employer",
        name="Anna Huber",
        phone=EMPLOYER_PHONE,
        email_verified_at=timezone.now(),  # emails go only to a confirmed address (#81)
    )
    EmployerProfile.objects.create(
        user=user, company_name="Huber Bau GmbH", trades=["demolition"]
    )
    return user


def make_worker(email, name, team_size=1, phone=""):
    """A worker who can apply: profile, work permit, confirmed email."""
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        role="worker",
        name=name,
        phone=phone,
        email_verified_at=timezone.now(),
        work_permit_confirmed_at=timezone.now(),
    )
    WorkerProfile.objects.create(
        user=user,
        team_size=team_size,
        skills=["demolition"],
        languages=["de"],
        legal_status="minijob",
    )
    return user


def phone_page(new_context, email):
    """A new 360 px phone (its own cookies), logged in as `email`."""
    page = new_context(viewport=PHONE).new_page()
    log_in(page, email)
    return page


def link_in(email):
    """The first link in an email's body."""
    return re.search(r"https?://\S+", email.body).group()


def test_worker_applies_and_the_employer_accepts_on_two_phones(new_context, mailoutbox):
    """A worker applies, the employer accepts: the job is filled, both see the contacts.

    1. Create an employer and a job for 2 workers at Lindwurmstraße 1; Olga has already
       applied alone; Ivan, a crew of 3, and the employer each log in on a 360 px phone
    2. Ivan opens the job
    3. Expect: no address, only "The exact address is shown after the employer accepts you."
    4. Ivan writes a message, chooses 2 workers, clicks "Send application"
    5. Expect: "Application sent.", "You applied · 2 workers" with "Pending"
    6. Expect: the employer got "New application: …"; open its link on the employer's phone
    7. Expect: Ivan's message, "Accept 2" and "Accepting fills the job: …" under it
    8. Click "Accept 2"
    9. Expect: "Accepted: 2 workers from Ivan Petrov." and "The job is filled. …",
       the job is "Filled", 2 / 2 workers found, Ivan's phone as a tel: link,
       Olga's application "Job filled" and no buttons left
    10. Expect: Ivan got "You are accepted: …"; open its link on Ivan's phone
    11. Expect: "My applications" with "Contact": Anna Huber, her phone, the address
    12. Ivan opens the job again
    13. Expect: "Address: Lindwurmstraße 1" and the employer's phone, status "Accepted"
    14. Expect: no page on the way is wider than the screen
    """
    employer = make_employer()
    job = make_job(employer, workers_needed=2, address="Lindwurmstraße 1")
    olga = make_worker("olga@example.com", "Olga Nowak")
    Application.objects.create(job=job, worker=olga, workers_offered=1)
    make_worker("ivan@example.com", "Ivan Petrov", team_size=3, phone=WORKER_PHONE)
    worker = phone_page(new_context, "ivan@example.com")
    boss = phone_page(new_context, "anna@example.com")

    worker.goto(f"/jobs/{job.pk}/")
    expect(
        worker.get_by_text("The exact address is shown after the employer accepts you.")
    ).to_be_visible()
    expect(worker.get_by_text("Lindwurmstraße 1")).to_have_count(0)
    assert_fits_the_screen(worker)

    worker.get_by_label("Message to the employer").fill(
        "We are two, with our own tools."
    )
    worker.get_by_label("Workers I bring").fill("2")
    worker.get_by_role("button", name="Send application").click()

    expect(worker.get_by_text("Application sent.")).to_be_visible()
    expect(worker.get_by_text("You applied")).to_be_visible()
    expect(worker.get_by_text("2 workers", exact=True)).to_be_visible()
    expect(worker.get_by_text("Pending", exact=True)).to_be_visible()

    (new_application,) = mailoutbox
    assert new_application.to == ["anna@example.com"]
    assert new_application.subject.startswith("New application: ")
    boss.goto(link_in(new_application))

    ivan_card = boss.locator("li", has_text="Ivan Petrov")
    expect(ivan_card.get_by_text("We are two, with our own tools.")).to_be_visible()
    expect(
        ivan_card.get_by_text("Accepting fills the job: the other pending applications")
    ).to_be_visible()
    assert_fits_the_screen(boss)
    ivan_card.get_by_role("button", name="Accept 2").click()

    expect(boss.get_by_text("Accepted: 2 workers from Ivan Petrov.")).to_be_visible()
    expect(boss.get_by_text("The job is filled.")).to_be_visible()
    expect(boss.get_by_text("Filled", exact=True)).to_be_visible()
    expect(boss.get_by_text("2 / 2")).to_be_visible()
    expect(ivan_card.get_by_role("link", name=WORKER_PHONE)).to_have_attribute(
        "href", f"tel:{WORKER_PHONE}"
    )
    olga_card = boss.locator("li", has_text="Olga Nowak")
    expect(olga_card.get_by_text("Job filled")).to_be_visible()
    expect(
        boss.get_by_role("button", name=re.compile("^(Accept|Reject)"))
    ).to_have_count(0)
    assert_fits_the_screen(boss)

    accepted = mailoutbox[-1]
    assert accepted.to == ["ivan@example.com"]
    assert accepted.subject.startswith("You are accepted: ")
    worker.goto(link_in(accepted))

    expect(worker.get_by_role("heading", name="My applications")).to_be_visible()
    contact = worker.locator("li", has_text="Contact")
    expect(contact).to_contain_text("Anna Huber")
    expect(contact.get_by_role("link", name=EMPLOYER_PHONE)).to_be_visible()
    expect(contact).to_contain_text("Lindwurmstraße 1")
    assert_fits_the_screen(worker)

    worker.goto(f"/jobs/{job.pk}/")
    expect(worker.get_by_text("Address: Lindwurmstraße 1")).to_be_visible()
    expect(worker.get_by_role("link", name=EMPLOYER_PHONE)).to_be_visible()
    expect(worker.get_by_text("Accepted", exact=True)).to_be_visible()
    assert_fits_the_screen(worker)


# The browser asks before an action that cannot be undone: onsubmit="return confirm(…)"
# (#24 accept-reject.md D16, #26 my-applications.md D4). The test client runs no JavaScript,
# so only these tests see the question and that "Cancel" in it sends nothing.

# An apostrophe in the name: the question is inside a JavaScript string in onsubmit, so
# |escapejs must keep it from ending the string (accept-reject.md D16).
NAME = "Liam O'Connor"


def click_and_answer(page, button, ok):
    """Click `button`, answer the browser's question with OK or Cancel; return the question."""
    questions = []

    def answer(dialog):
        questions.append(dialog.message)
        if ok:
            dialog.accept()
        else:
            dialog.dismiss()

    page.once("dialog", answer)
    button.click()
    assert questions, "the browser asked nothing"
    return questions[0]


def test_employer_rejects_after_the_browser_asks(new_context, mailoutbox):
    """ "Reject" asks first: Cancel keeps the application, OK rejects it.

    1. Create a job with a pending application of Liam O'Connor; the employer logs in on
       a 360 px phone and opens the job
    2. Click "Reject", answer "Cancel" in the browser's question
    3. Expect: the question "Reject Liam O'Connor? This cannot be undone.", the
       application is still pending in the database, no email sent
    4. Click "Reject" again, answer "OK"
    5. Expect: "Rejected: Liam O'Connor.", the application is "Rejected" on the page and
       in the database, Liam got "Application not accepted: …"
    """
    job = make_job(make_employer())
    application = Application.objects.create(
        job=job, worker=make_worker("liam@example.com", NAME), workers_offered=1
    )
    boss = phone_page(new_context, "anna@example.com")
    boss.goto(f"/jobs/{job.pk}/")
    reject = boss.get_by_role("button", name="Reject")

    question = click_and_answer(boss, reject, ok=False)

    assert question == f"Reject {NAME}? This cannot be undone."
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING
    assert mailoutbox == []

    click_and_answer(boss, reject, ok=True)

    expect(boss.get_by_text(f"Rejected: {NAME}.")).to_be_visible()
    expect(boss.get_by_text("Rejected", exact=True)).to_be_visible()
    application.refresh_from_db()
    assert application.status == Application.Status.REJECTED
    (rejected,) = mailoutbox
    assert rejected.subject.startswith("Application not accepted: ")


def test_employer_cancels_an_accepted_worker_after_the_browser_asks(new_context):
    """ "Cancel" of an accepted worker asks first: Cancel keeps them, OK cancels them.

    1. Create a job for 1 worker; Liam O'Connor is accepted, so the job is filled; the
       employer logs in on a 360 px phone and opens the job
    2. Click "Cancel" in Liam's application, answer "Cancel" in the browser's question
    3. Expect: the question "Cancel Liam O'Connor? This cannot be undone.", Liam is still
       accepted, the job still filled
    4. Click "Cancel" again, answer "OK"
    5. Expect: "Cancelled: Liam O'Connor. The job is open again.", the application is
       "Cancelled", the job open
    """
    job = make_job(make_employer(), workers_needed=1)
    application = Application.objects.create(
        job=job, worker=make_worker("liam@example.com", NAME), workers_offered=1
    )
    application.accept()
    boss = phone_page(new_context, "anna@example.com")
    boss.goto(f"/jobs/{job.pk}/")
    cancel = boss.get_by_role("button", name="Cancel")

    question = click_and_answer(boss, cancel, ok=False)

    assert question == f"Cancel {NAME}? This cannot be undone."
    application.refresh_from_db()
    job.refresh_from_db()
    assert application.status == Application.Status.ACCEPTED
    assert job.status == job.Status.FILLED

    click_and_answer(boss, cancel, ok=True)

    expect(
        boss.get_by_text(f"Cancelled: {NAME}. The job is open again.")
    ).to_be_visible()
    application.refresh_from_db()
    job.refresh_from_db()
    assert application.status == Application.Status.CANCELLED
    assert job.status == job.Status.OPEN


def test_worker_withdraws_after_the_browser_asks(new_context):
    """ "Withdraw" asks first: Cancel keeps the application, OK withdraws it.

    1. Create a job with a pending application of Liam; Liam logs in on a 360 px phone and
       opens "My applications" from the header menu
    2. Click "Withdraw", answer "Cancel" in the browser's question
    3. Expect: the question "Withdraw your application? This cannot be undone.", the
       application is still pending
    4. Click "Withdraw" again, answer "OK"
    5. Expect: "Application withdrawn.", the application is "Withdrawn" in the database
    6. Expect: the page fits the screen
    """
    job = make_job(make_employer())
    application = Application.objects.create(
        job=job, worker=make_worker("liam@example.com", NAME), workers_offered=1
    )
    worker = phone_page(new_context, "liam@example.com")
    worker.get_by_label("Menu").click()
    worker.get_by_role("link", name="My applications").click()
    withdraw = worker.get_by_role("button", name="Withdraw")

    question = click_and_answer(worker, withdraw, ok=False)

    assert question == "Withdraw your application? This cannot be undone."
    application.refresh_from_db()
    assert application.status == Application.Status.PENDING

    click_and_answer(worker, withdraw, ok=True)

    expect(worker.get_by_text("Application withdrawn.")).to_be_visible()
    application.refresh_from_db()
    assert application.status == Application.Status.WITHDRAWN
    assert_fits_the_screen(worker)
