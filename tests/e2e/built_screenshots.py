"""E2E tests: saves the "built" screenshots next to the mockups in docs/mockups/built/ (#95).

Not a regular test: the name has no `test_` prefix, so `uv run pytest` skips it. Run it on
purpose when a ticket changes a screen from docs/mockups/ (CLAUDE.md, ticket workflow step 3):

    uv run pytest tests/e2e/built_screenshots.py

It fills the test database with made-up jobs and accounts (never real data) and overwrites
the PNGs: 390 px wide like the mockups, light theme, full page. A ticket that adds a screen
adds one `shoot()` line here.
"""

import datetime
import io
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageDraw

from accounts.models import EmployerProfile, WorkerProfile
from jobs.models import JobPhoto
from jobs.tests.test_views import make_job

from .helpers import PASSWORD, log_in

pytestmark = [pytest.mark.django_db, pytest.mark.story(95)]

User = get_user_model()
OUT = Path("docs/mockups/built")
MOCKUP = {"width": 390, "height": 844}
DAY = datetime.timedelta(days=1)


def photo_bytes(colour):
    """A made-up 'photo': a coloured picture with a few shapes."""
    image = Image.new("RGB", (1200, 900), colour)
    draw = ImageDraw.Draw(image)
    draw.rectangle((150, 350, 1050, 900), fill=(120, 110, 100))
    draw.polygon([(100, 380), (600, 120), (1100, 380)], fill=(90, 80, 70))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


def shoot(page, path, name):
    """Open `path` and save a full-page screenshot as docs/mockups/built/<name>.png."""
    page.goto(path)
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)


def test_save_built_screenshots(page):
    """Save the built screenshots of the screens that exist.

    1. Create an employer with three jobs (one with three photos) and a worker
    2. Open the job list as a guest, the job page as the worker, "Post a job" and "My jobs"
       as the employer, on a 390 x 844 screen in the light theme
    3. Expect: one full-page PNG per screen in docs/mockups/built/
    """
    OUT.mkdir(exist_ok=True)
    employer = User.objects.create_user(
        email="max@example.com", password=PASSWORD, role="employer", name="Max Huber"
    )
    EmployerProfile.objects.create(
        user=employer, company_name="Huber Bau GmbH", trades=["demolition"]
    )
    today = timezone.localdate()
    job = make_job(
        employer,
        job_type="carrying",
        description="Carry 200 tiles to the third floor, no lift. Gloves provided.",
        district="sendling",
        date=today + 2 * DAY,
        workers_needed=3,
        hourly_rate="18.50",
    )
    for colour in ("#d9822b", "#7a8a99", "#b5a47a"):
        JobPhoto.objects.create(
            job=job, image=ContentFile(photo_bytes(colour), name="p.jpg")
        )
    make_job(
        employer, job_type="demolition", district="schwabing_west", date=today + 3 * DAY
    )
    make_job(
        employer,
        job_type="site_cleaning",
        district="laim",
        date=today + 5 * DAY,
        hours=4,
    )
    worker = User.objects.create_user(
        email="ana@example.com", password=PASSWORD, role="worker", name="Ana"
    )
    WorkerProfile.objects.create(
        user=worker,
        team_size=1,
        skills=["carrying"],
        languages=["de"],
        legal_status="gewerbe",
    )
    worker.work_permit_confirmed_at = timezone.now()
    worker.save()

    # live_server does not serve uploads (in-memory storage): answer every photo address.
    picture = photo_bytes("#d9822b")
    page.route(
        "**/media/**",
        lambda route: route.fulfill(body=picture, content_type="image/jpeg"),
    )
    page.emulate_media(color_scheme="light")
    page.set_viewport_size(MOCKUP)
    shoot(page, "/", "jobs-list")
    log_in(page, "ana@example.com")
    shoot(page, f"/jobs/{job.pk}/", "job-detail")
    page.context.clear_cookies()
    log_in(page, "max@example.com")
    shoot(page, "/jobs/new/", "post-a-job")
    shoot(page, "/jobs/mine/", "my-jobs")
