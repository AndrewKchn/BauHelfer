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
from django.utils import timezone
from PIL import Image
from playwright.sync_api import expect

from accounts.models import EmployerProfile
from jobs.models import minimum_wage_on

from .helpers import PASSWORD, PHONE, assert_fits_the_screen, log_in

pytestmark = [pytest.mark.django_db, pytest.mark.story(21)]

User = get_user_model()

NEXT_WEEK = timezone.localdate() + datetime.timedelta(days=7)


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
