"""Helpers shared by the E2E test files: screen sizes, logging in, the "fits the screen" check.

Not a test file (no `test_` prefix): the test files import from here (moved out of
test_account_flows.py in #21, when a second E2E file needed them). The users and the phone
came from test_application_flows.py in #40, for the M6 flows.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import EmployerProfile, WorkerProfile

# Most workers use a phone, many employers a laptop.
PHONE = {"width": 360, "height": 740}  # a small Android phone; base.html fits 360 px
LAPTOP = {"width": 1366, "height": 768}  # a common laptop screen

PASSWORD = "Gerüst-2026-Munich"
EMPLOYER_PHONE = "+49 170 1111111"
WORKER_PHONE = "+49 170 2222222"


def log_in(page, email, password=PASSWORD):
    """Log in through the "Log in" link in the header."""
    page.goto("/")
    page.get_by_role("link", name="Log in").click()
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Log in").click()


def assert_fits_the_screen(page):
    """The page is not wider than the screen: no sideways scrolling on a phone."""
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    # Below 0 on a laptop: the place kept for the scrollbar is not part of the page (#28).
    assert overflow <= 0, f"{page.url} is {overflow}px wider than the screen"


def make_employer(email="anna@example.com", language="en"):
    """An employer with a company profile, a phone and a confirmed email.

    `language`: the site language, also the one the chat translates into (#36).
    """
    user = get_user_model().objects.create_user(
        email=email,
        password=PASSWORD,
        role="employer",
        name="Anna Huber",
        phone=EMPLOYER_PHONE,
        preferred_language=language,
        email_verified_at=timezone.now(),  # emails go only to a confirmed address (#81)
    )
    EmployerProfile.objects.create(
        user=user, company_name="Huber Bau GmbH", trades=["demolition"]
    )
    return user


def make_worker(email, name, team_size=1, phone="", language="en"):
    """A worker who can apply: profile, work permit, confirmed email."""
    user = get_user_model().objects.create_user(
        email=email,
        password=PASSWORD,
        role="worker",
        name=name,
        phone=phone,
        preferred_language=language,
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
    """A new 360 px phone with a touch screen (its own cookies), logged in as `email`."""
    page = new_context(viewport=PHONE, has_touch=True).new_page()
    log_in(page, email)
    return page
