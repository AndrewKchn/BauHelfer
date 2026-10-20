"""E2E tests: the M3 job flows in a real browser (Chromium via Playwright) (#21).

Besides the flows, these tests check what only a browser can see: the JavaScript of the job
form ("Save changes" off until a change, "Leave page?" with unsaved changes, job-photos.md
D11, D22), a real file upload through <input type="file">, and that no page of the flow
scrolls sideways on a 360 px phone (the employer flow on a phone was promised in #14).
"""

import datetime
import io
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image
from playwright.sync_api import expect

from accounts.models import EmployerProfile, WorkerProfile
from jobs.models import JobPhoto, minimum_wage_on
from jobs.tests.images import make_upload
from jobs.tests.test_views import make_job

from .helpers import PASSWORD, PHONE, assert_fits_the_screen, log_in

pytestmark = [pytest.mark.django_db, pytest.mark.story(21)]

User = get_user_model()

NEXT_WEEK = timezone.localdate() + datetime.timedelta(days=7)
# Inside "Next 7 days", which ends on day 6 (#18, job-list.md D12): NEXT_WEEK is outside it.
IN_3_DAYS = timezone.localdate() + datetime.timedelta(days=3)


def make_employer(email):
    """An employer with a filled company profile, ready to post jobs."""
    user = User.objects.create_user(email=email, password=PASSWORD, role="employer")
    EmployerProfile.objects.create(
        user=user, company_name="Huber Bau GmbH", trades=["demolition"]
    )
    return user


def jpeg_file(name="baustelle.jpg"):
    """A small JPEG as Playwright hands it to <input type="file">, made in memory."""
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), "orange").save(buffer, "JPEG")
    return {"name": name, "mimeType": "image/jpeg", "buffer": buffer.getvalue()}


def test_employer_posts_edits_and_cancels_a_job_on_a_phone(page):
    """An employer posts a job, adds a photo, edits and cancels it on a phone.

    1. Create an employer with a company profile, set a 360 x 740 phone screen, log in
    2. Open "Post a job" from the header menu, fill in the form with 12.00 €/h
    3. Click "Publish job"
    4. Expect: the minimum-wage error under the rate, the typed values are kept
    5. Change the rate to 20.00, click "Publish job"
    6. Expect: the edit page with "Job posted. You can add photos below.",
       "Save changes" is off
    7. Choose one JPEG, click "Add photos"
    8. Expect: "1 photo added." and "Photos (1 of 5)"
    9. Change the rate to 22.00
    10. Expect: "Save changes" is on
    11. Click "Back to my jobs", answer "Stay" in the browser's "Leave page?" dialog
    12. Expect: the dialog came, the edit page is still open
    13. Click "Save changes"
    14. Expect: "My jobs" with "Job saved." and the job at 22.00 €/h
    15. Expect: the job is on the public job list
    16. Click "Cancel job", then "Yes, cancel the job"
    17. Expect: "Job cancelled.", the job is "Cancelled" in "My jobs" without "Edit"
    18. Expect: the job is no longer on the public job list
    19. Expect: no page on the way is wider than the screen
    """
    make_employer("max@example.com")
    page.set_viewport_size(PHONE)
    log_in(page, "max@example.com")
    main = page.get_by_role("main")

    page.get_by_label("Menu").click()
    page.get_by_role("link", name="Post a job").click()
    expect(page.get_by_role("heading", name="Post a job")).to_be_visible()
    assert_fits_the_screen(page)
    page.get_by_label("Job type").select_option(label="Carrying materials")
    page.get_by_label("Description").fill("Carry tiles to the third floor.")
    page.get_by_label("Address").fill("Leopoldstraße 50")
    page.get_by_label("District").select_option(label="Schwabing-West")
    page.get_by_label("Date").fill(NEXT_WEEK.isoformat())
    page.get_by_label("Start time").fill("07:30")
    page.get_by_label("Hours").fill("4")
    page.get_by_label("Workers needed").fill("3")
    page.get_by_label("Hourly rate, €").fill("12.00")
    page.get_by_role("button", name="Publish job").click()

    wage = minimum_wage_on(NEXT_WEEK)
    expect(
        main.get_by_text(f"At least {wage} € on this date (German minimum wage).")
    ).to_be_visible()
    expect(page.get_by_label("Address")).to_have_value("Leopoldstraße 50")
    assert_fits_the_screen(page)

    page.get_by_label("Hourly rate, €").fill("20.00")
    page.get_by_role("button", name="Publish job").click()

    expect(page).to_have_url(re.compile(r"/jobs/\d+/edit/#photos$"))
    expect(page.get_by_text("Job posted. You can add photos below.")).to_be_visible()
    save = page.get_by_role("button", name="Save changes")
    expect(save).to_be_disabled()
    assert_fits_the_screen(page)

    page.get_by_label("Photos").set_input_files(jpeg_file())
    page.get_by_role("button", name="Add photos").click()
    expect(page.get_by_text("1 photo added.")).to_be_visible()
    expect(page.get_by_role("heading", name="Photos (1 of 5)")).to_be_visible()
    assert_fits_the_screen(page)

    page.get_by_label("Hourly rate, €").fill("22.00")
    expect(save).to_be_enabled()

    # The browser asks "Leave page?" itself; Playwright sees it as a "beforeunload" dialog.
    dialogs = []

    def stay_on_the_page(dialog):
        dialogs.append(dialog.type)
        dialog.dismiss()  # "Stay"

    page.once("dialog", stay_on_the_page)
    page.get_by_role("link", name="Back to my jobs").click(no_wait_after=True)
    expect(page).to_have_url(re.compile(r"/jobs/\d+/edit/"))
    assert dialogs == ["beforeunload"]
    expect(page.get_by_label("Hourly rate, €")).to_have_value("22.00")

    save.click()
    expect(page).to_have_url(re.compile(r"/jobs/mine/$"))
    expect(page.get_by_text("Job saved.")).to_be_visible()
    card = main.get_by_role("listitem").filter(has_text="Carrying materials")
    expect(card.get_by_text("22.00 €/h")).to_be_visible()
    assert_fits_the_screen(page)

    page.goto("/")
    expect(main.get_by_role("link", name="Carrying materials")).to_be_visible()

    page.goto("/jobs/mine/")
    card.get_by_role("link", name="Cancel job").click()
    expect(page.get_by_role("heading", name="Cancel this job?")).to_be_visible()
    assert_fits_the_screen(page)
    page.get_by_role("button", name="Yes, cancel the job").click()

    expect(page.get_by_text("Job cancelled.")).to_be_visible()
    expect(card.get_by_text("Cancelled")).to_be_visible()
    expect(card.get_by_role("link", name="Edit")).to_have_count(0)
    assert_fits_the_screen(page)

    page.goto("/")
    expect(main.get_by_role("link", name="Carrying materials")).to_have_count(0)


def test_worker_filters_the_jobs_and_opens_one_on_a_phone(page):
    """A guest filters the job list, opens a job, logs in as a worker and applies.

    1. Create three open jobs: carrying in Sendling in 3 days (with 3 photos), demolition
       in Sendling in 20 days, carrying in Schwabing-West in 3 days; a worker who can
       apply (profile, work permit)
    2. Set a 360 x 740 phone screen, open the home page
    3. Expect: "3 open"
    4. Choose "Next 7 days" and the district Sendling, click "Show"
    5. Expect: the choice is in the address, "1 open", only the carrying job
    6. Open the job
    7. Expect: no exact address, "1 / 3" on the screen
    8. Click "Next photo", then "Previous photo"
    9. Expect: "2 / 3", then "1 / 3" again on the screen
    10. Click "Log in to apply", log in as the worker
    11. Expect: back on the same job page
    12. Write a message to the employer, click "Send application" (#22)
    13. Expect: "Application sent." and "You applied" on the job page
    14. Open the filtered list again, click "Reset filters"
    15. Expect: "3 open" again
    16. Expect: no page on the way is wider than the screen
    """
    employer = make_employer("max@example.com")
    job = make_job(
        employer,
        job_type="carrying",
        district="sendling",
        address="Lindwurmstraße 1",
        date=IN_3_DAYS,
    )
    for _ in range(3):
        JobPhoto.objects.create(
            job=job, image=ContentFile(make_upload().read(), name="photo.jpg")
        )
    make_job(
        employer,
        job_type="demolition",
        district="sendling",
        date=timezone.localdate() + datetime.timedelta(days=20),
    )
    make_job(employer, job_type="carrying", district="schwabing_west", date=IN_3_DAYS)
    worker = User.objects.create_user(
        email="ana@example.com",
        password=PASSWORD,
        role="worker",
        work_permit_confirmed_at=timezone.now(),
    )
    WorkerProfile.objects.create(
        user=worker, skills=["carrying"], languages=["de"], legal_status="minijob"
    )
    page.set_viewport_size(PHONE)
    main = page.get_by_role("main")

    page.goto("/")
    expect(main.get_by_text("3 open")).to_be_visible()
    assert_fits_the_screen(page)

    page.get_by_label("Date").select_option(label="Next 7 days")
    page.get_by_label("District").select_option("sendling")
    page.get_by_role("button", name="Show").click()

    expect(page).to_have_url(re.compile(r"[?&]district=sendling"))
    expect(main.get_by_text("1 open")).to_be_visible()
    cards = main.get_by_role("listitem")
    expect(cards).to_have_count(1)
    expect(cards.get_by_text("Sendling")).to_be_visible()
    assert_fits_the_screen(page)

    cards.get_by_role("link", name="Carrying materials").click()
    expect(page).to_have_url(re.compile(rf"/jobs/{job.pk}/$"))
    expect(main.get_by_text("Lindwurmstraße")).to_have_count(0)
    expect(
        main.get_by_text("The exact address is shown after the employer accepts you.")
    ).to_be_visible()
    expect(main.get_by_text("1 / 3")).to_be_in_viewport()
    assert_fits_the_screen(page)

    page.get_by_role("button", name="Next photo").click()
    expect(main.get_by_text("2 / 3")).to_be_in_viewport()
    expect(main.get_by_text("1 / 3")).not_to_be_in_viewport()
    page.get_by_role("button", name="Previous photo").click()
    expect(main.get_by_text("1 / 3")).to_be_in_viewport()

    page.get_by_role("link", name="Log in to apply").click()
    page.get_by_label("Email").fill("ana@example.com")
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Log in").click()
    expect(page).to_have_url(re.compile(rf"/jobs/{job.pk}/$"))

    page.get_by_label("Message to the employer").fill("I can start at 8.")
    page.get_by_role("button", name="Send application").click()
    # The browser keeps the form's #apply after the redirect; the page then has no element
    # with that id, so it stays at the top with the message.
    expect(page).to_have_url(re.compile(rf"/jobs/{job.pk}/(#apply)?$"))
    expect(page.get_by_text("Application sent.")).to_be_visible()
    expect(main.get_by_text("You applied")).to_be_visible()
    assert_fits_the_screen(page)

    page.goto("/?date=7&district=sendling")
    page.get_by_role("link", name="Reset filters").click()
    expect(main.get_by_text("3 open")).to_be_visible()
