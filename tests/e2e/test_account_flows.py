"""E2E tests: the M2 account flows in a real browser (Chromium via Playwright) (#14).

Unlike the integration tests, nothing is called directly: the test clicks and types like a
user, the browser sends real HTTP requests to the live server, and the checks read what is
on the screen. This catches what the Django test client cannot see: a button outside the
<form>, a missing CSRF token in the HTML, a link to a wrong URL, a menu that does not open.

expect(...) waits up to 5 seconds for the page to reach the state, so no sleep() is needed.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from playwright.sync_api import expect

from accounts.models import EmployerProfile, WorkerProfile
from jobs.tests.test_views import make_job

from .helpers import LAPTOP, PASSWORD, PHONE, assert_fits_the_screen, log_in

pytestmark = [pytest.mark.django_db, pytest.mark.story(14)]

User = get_user_model()


def sign_up(page, email):
    """Fill in and send the registration form, starting from the home page."""
    page.goto("/")
    page.get_by_role("link", name="Register").click()
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_label("Password confirmation").fill(PASSWORD)
    page.get_by_role("button", name="Register").click()


def test_worker_signs_up_and_fills_in_the_profile_on_a_phone(page):
    """A new worker signs up, chooses the role and saves the profile on a phone.

    1. Set the browser window to a 360 x 740 phone screen
    2. Open the home page, click "Register", sign up as ana@example.com
    3. Expect: the role choice page with the welcome message
    4. Click "I am looking for work"
    5. Fill in name, phone, team size, a skill, a language, legal status, tick the permit box
    6. Click "Save profile"
    7. Expect: "Profile saved." and the profile page shows the entered data
    8. Expect: no page on the way is wider than the screen
    9. Open the header menu
    10. Expect: "My profile" and "Log out" are visible on the screen
    """
    page.set_viewport_size(PHONE)
    sign_up(page, "ana@example.com")

    expect(page.get_by_role("heading", name="Who are you?")).to_be_visible()
    expect(page.get_by_text("Welcome to BauHelfer!")).to_be_visible()
    assert_fits_the_screen(page)

    page.get_by_role("button", name="I am looking for work").click()

    expect(page).to_have_url(re.compile(r"/accounts/profile/worker/edit/$"))
    assert_fits_the_screen(page)
    page.get_by_label("Name", exact=True).fill("Ana Popescu")
    page.get_by_label("Phone").fill("+49 151 12345678")
    page.get_by_label("Team size").fill("3")
    page.get_by_label("Carrying materials").check()
    page.get_by_label("Romanian").check()
    page.get_by_label("Minijob").check()
    page.get_by_label("I am allowed to work in Germany").check()
    page.get_by_role("button", name="Save profile").click()

    expect(page).to_have_url(re.compile(r"/accounts/profile/worker/$"))
    expect(page.get_by_text("Profile saved.")).to_be_visible()
    main = page.get_by_role("main")
    for text in ("Ana Popescu", "+49 151 12345678", "Carrying materials", "Romanian"):
        expect(main.get_by_text(text)).to_be_visible()
    expect(main.get_by_text("Confirmed by the worker")).to_be_visible()
    assert_fits_the_screen(page)

    page.get_by_label("Menu").click()
    expect(page.get_by_role("link", name="My profile")).to_be_in_viewport()
    expect(page.get_by_role("button", name="Log out")).to_be_in_viewport()


def test_employer_signs_up_and_fills_in_the_profile_on_a_laptop(page):
    """A new employer signs up, chooses the role and saves the company profile on a laptop.

    1. Set the browser window to a 1366 x 768 laptop screen
    2. Sign up as boss@example.com, click "I need workers"
    3. Fill in name, company name and a trade, click "Save profile"
    4. Expect: "Profile saved." and "My company" shows the company and the trade
    5. Open the header menu
    6. Expect: it links to "My company", not to a worker profile
    """
    page.set_viewport_size(LAPTOP)
    sign_up(page, "boss@example.com")
    page.get_by_role("button", name="I need workers").click()

    expect(page).to_have_url(re.compile(r"/accounts/profile/employer/edit/$"))
    page.get_by_label("Name", exact=True).fill("Max Huber")
    page.get_by_label("Company name").fill("Huber Bau GmbH")
    page.get_by_label("Drywall").check()
    page.get_by_role("button", name="Save profile").click()

    expect(page.get_by_text("Profile saved.")).to_be_visible()
    expect(page.get_by_role("heading", name="My company")).to_be_visible()
    main = page.get_by_role("main")
    expect(main.get_by_text("Huber Bau GmbH")).to_be_visible()
    expect(main.get_by_text("Drywall")).to_be_visible()

    page.get_by_label("Menu").click()
    expect(page.get_by_role("link", name="My company")).to_be_visible()
    expect(page.get_by_role("link", name="My profile")).to_have_count(0)


def test_user_logs_out_and_logs_in_again(page):
    """A user logs out with the header menu, fails once, then logs in.

    1. Create a worker ivan@example.com, log in through the header link
    2. Expect: the header shows the email
    3. Open the menu, click "Log out"
    4. Expect: the header shows "Log in" again, no email
    5. Log in with a wrong password
    6. Expect: "Wrong email or password."
    7. Log in with the right password
    8. Expect: the home page, the header shows the email
    """
    User.objects.create_user(
        email="ivan@example.com", password=PASSWORD, role=User.Role.WORKER
    )
    header = page.get_by_role("banner")

    log_in(page, "ivan@example.com", PASSWORD)
    expect(header.get_by_text("ivan@example.com")).to_be_visible()

    page.get_by_label("Menu").click()
    page.get_by_role("button", name="Log out").click()
    expect(header.get_by_role("link", name="Log in")).to_be_visible()
    expect(header.get_by_text("ivan@example.com")).to_have_count(0)

    log_in(page, "ivan@example.com", "wrong-password")
    expect(page.get_by_text("Wrong email or password.")).to_be_visible()

    log_in(page, "ivan@example.com", PASSWORD)
    expect(page).to_have_url(re.compile(r"/$"))
    expect(header.get_by_text("ivan@example.com")).to_be_visible()


def test_user_resets_a_forgotten_password(page, mailoutbox):
    """A user asks for a reset link, sets a new password and logs in with it.

    1. Create olga@example.com, open "Log in", click "Forgot your password?"
    2. Send the form with olga@example.com
    3. Expect: "Check your email", one email to olga@example.com with a link
    4. Open the link from the email, set a new password twice, click "Save password"
    5. Expect: "Password changed"
    6. Log in with the old password
    7. Expect: "Wrong email or password."
    8. Log in with the new password
    9. Expect: the header shows the email
    """
    # Only a confirmed address gets a reset email (#27, notifications.md D13).
    User.objects.create_user(
        email="olga@example.com",
        password=PASSWORD,
        role=User.Role.WORKER,
        email_verified_at=timezone.now(),
    )
    new_password = "Neues-Passwort-2026"

    page.goto("/accounts/login/")
    page.get_by_role("link", name="Forgot your password?").click()
    page.get_by_label("Email").fill("olga@example.com")
    page.get_by_role("button", name="Send link").click()

    expect(page.get_by_role("heading", name="Check your email")).to_be_visible()
    # The live server runs in this process, so Django's test mailbox sees its emails.
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["olga@example.com"]
    link = re.search(r"https?://\S+/reset/\S+", mailoutbox[0].body).group()

    page.goto(link)
    page.get_by_label("New password", exact=True).fill(new_password)
    page.get_by_label("New password confirmation").fill(new_password)
    page.get_by_role("button", name="Save password").click()
    expect(page.get_by_role("heading", name="Password changed")).to_be_visible()

    log_in(page, "olga@example.com", PASSWORD)
    expect(page.get_by_text("Wrong email or password.")).to_be_visible()

    log_in(page, "olga@example.com", new_password)
    expect(page.get_by_role("banner").get_by_text("olga@example.com")).to_be_visible()


# The longest name and company name the forms accept (max_length=150), without a space the
# browser could break the line at; an email as long as a real one can get (found in #11, #12).
LONG_NAME = "Wolfeschlegelsteinhausenbergerdorff" * 4 + "x" * 10
LONG_EMAIL = "kontakt.baustellenkoordination.muenchen@hochundtiefbau-beispiel.de"


@pytest.mark.story(21)
def test_long_worker_name_fits_a_phone(page):
    """A worker name of 150 letters without spaces does not make pages scroll sideways.

    1. Create a worker with a 150-letter name, a long email and a profile
    2. Set a 360 x 740 phone screen, log in
    3. Open the profile page, the profile form and the job list with the header menu open
    4. Expect: no page is wider than the screen
    """
    user = User.objects.create_user(
        email=LONG_EMAIL, password=PASSWORD, role=User.Role.WORKER, name=LONG_NAME
    )
    WorkerProfile.objects.create(
        user=user,
        team_size=1,
        skills=["demolition"],
        languages=["de"],
        legal_status="minijob",
    )
    page.set_viewport_size(PHONE)
    log_in(page, LONG_EMAIL)

    for url in ("/accounts/profile/worker/", "/accounts/profile/worker/edit/", "/"):
        page.goto(url)
        page.get_by_label("Menu").click()
        assert_fits_the_screen(page)


@pytest.mark.story(21)
def test_long_company_name_fits_a_phone(page):
    """A company and person name of 150 letters without spaces fits a phone.

    1. Create an employer with a 150-letter name and company name, a long email and a job
    2. Set a 360 x 740 phone screen, log in
    3. Open "My company", its form, "My jobs" and the job page, with the header menu open
    4. Log out, open the job page as a guest
    5. Expect: no page is wider than the screen
    """
    user = User.objects.create_user(
        email=LONG_EMAIL, password=PASSWORD, role=User.Role.EMPLOYER, name=LONG_NAME
    )
    EmployerProfile.objects.create(
        user=user, company_name=LONG_NAME, trades=["demolition"]
    )
    job = make_job(user)
    page.set_viewport_size(PHONE)
    log_in(page, LONG_EMAIL)

    pages = (
        "/accounts/profile/employer/",
        "/accounts/profile/employer/edit/",
        "/jobs/mine/",
        f"/jobs/{job.pk}/",
    )
    for url in pages:
        page.goto(url)
        page.get_by_label("Menu").click()
        assert_fits_the_screen(page)

    page.get_by_role("button", name="Log out").click()
    page.goto(f"/jobs/{job.pk}/")
    assert_fits_the_screen(page)
