"""E2E tests: every page fits a 360 px phone in German, our longest language (#40).

Moved here from #30 (translations.md D3): a badge or button made too long by a translation
fails CI instead of waiting for someone to see it on a phone. The language is switched with
the header menu (#29), as a user does. The data is chosen so the long pieces appear: a badge
of every status, "Work permit not confirmed", ratings, a chat.
"""

import datetime

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from chat.models import Message
from jobs.models import Application
from jobs.tests.test_views import make_job
from reviews.models import Review

from .helpers import (
    PHONE,
    assert_fits_the_screen,
    make_employer,
    make_worker,
    phone_page,
)

pytestmark = [pytest.mark.django_db, pytest.mark.story(40)]

DAY = datetime.timedelta(days=1)


def switch_to_german(page):
    """Open the header's language menu and choose Deutsch (#29)."""
    page.goto("/")
    page.locator("summary", has_text="EN").click()
    page.get_by_role("button", name="Deutsch").click()
    expect(page.locator("html")).to_have_attribute("lang", "de")


def pages_too_wide(page, paths):
    """Open each path; return the messages of the pages wider than the screen."""
    too_wide = []
    for path in paths:
        response = page.goto(path)
        assert response.ok, f"{path} answered {response.status}"
        try:
            assert_fits_the_screen(page)
        except AssertionError as error:
            too_wide.append(str(error))
    return too_wide


def test_every_page_fits_a_phone_in_german(new_context):
    """A guest, a worker and an employer open every page in German at 360 px: none is wider.

    1. Create an employer with an open job (Olga, without a confirmed work permit, and Ivan
       applied), a filled one (Ivan accepted, a chat), a done one (Ivan, rated both ways), a
       done one nobody rated yet and a cancelled one
    2. A guest, Ivan and the employer each switch to Deutsch with the header menu on their
       own 360 px phone
    3. Each opens every page they can reach with a GET: lists, job pages, forms, profiles,
       chats, review forms
    4. Expect: every page answers 200 and none is wider than the screen; a failure names
       all the pages that are
    """
    today = timezone.localdate()
    employer = make_employer()
    ivan = make_worker("ivan@example.com", "Ivan Petrov")
    olga = make_worker("olga@example.com", "Olga Nowak")
    olga.work_permit_confirmed_at = None
    olga.save()

    open_job = make_job(employer, date=today + 7 * DAY)
    Application.objects.create(
        job=open_job, worker=olga, workers_offered=1, message="Ich habe Werkzeug."
    )
    Application.objects.create(job=open_job, worker=ivan, workers_offered=1)

    filled_job = make_job(employer, workers_needed=1, date=today + 7 * DAY)
    chat = Application.objects.create(job=filled_job, worker=ivan, workers_offered=1)
    chat.accept()
    Message.objects.create(application=chat, sender=ivan, text="Ich komme um acht.")
    Message.objects.create(application=chat, sender=employer, text="Gut, bis morgen.")

    def done_job(rated):
        job = make_job(employer, workers_needed=1, date=today - DAY)
        application = Application.objects.create(
            job=job, worker=ivan, workers_offered=1
        )
        application.accept()
        job.refresh_from_db()
        job.mark_done()
        if rated:
            Review.objects.create(application=application, author=employer, rating=5)
            Review.objects.create(application=application, author=ivan, rating=4)
        return job, application

    rated_job, _ = done_job(rated=True)
    unrated_job, unrated = done_job(rated=False)
    make_job(employer, date=today + 7 * DAY).cancel()

    guest = new_context(viewport=PHONE, has_touch=True).new_page()
    switch_to_german(guest)
    worker = phone_page(new_context, "ivan@example.com")
    switch_to_german(worker)
    boss = phone_page(new_context, "anna@example.com")
    switch_to_german(boss)

    too_wide = pages_too_wide(
        guest,
        [
            "/",
            f"/jobs/{open_job.pk}/",
            f"/accounts/employers/{employer.pk}/",
            "/accounts/login/",
            "/accounts/register/",
            "/accounts/register/done/",
            "/accounts/verify/resend/",
            "/accounts/password-reset/",
            "/accounts/password-reset/done/",
        ],
    )
    too_wide += pages_too_wide(
        worker,
        [
            "/",
            f"/jobs/{open_job.pk}/",
            f"/jobs/{filled_job.pk}/",
            f"/jobs/{rated_job.pk}/",
            "/jobs/applications/",
            "/accounts/profile/worker/",
            "/accounts/profile/worker/edit/",
            f"/accounts/employers/{employer.pk}/",
            "/chat/",
            f"/chat/{chat.pk}/",
            f"/applications/{unrated.pk}/review/",
        ],
    )
    too_wide += pages_too_wide(
        boss,
        [
            "/jobs/mine/",
            "/jobs/new/",
            f"/jobs/{open_job.pk}/",
            f"/jobs/{open_job.pk}/edit/",
            f"/jobs/{open_job.pk}/cancel/",
            f"/jobs/{filled_job.pk}/",
            f"/jobs/{unrated_job.pk}/",
            "/accounts/profile/employer/",
            "/accounts/profile/employer/edit/",
            f"/accounts/workers/{ivan.pk}/",
            f"/accounts/workers/{olga.pk}/",
            "/chat/",
            f"/chat/{chat.pk}/",
            f"/applications/{unrated.pk}/review/",
        ],
    )
    assert not too_wide, "\n".join(too_wide)
