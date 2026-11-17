"""E2E tests: the M5 "Show original" toggles in a real browser (Chromium via Playwright) (#40).

M5 had no E2E ticket: the Django test client checked the HTML of both states and the HTMX
attributes (job-translation.md R13, application-translation.md R17); the click itself was
checked by hand. Here the browser clicks: HTMX fetches the other state and swaps one block,
without a reload. Translations come from FakeClaudeBackend: "[en] Abriss" is the English one.
"""

import pytest
from playwright.sync_api import expect

from jobs.models import Application
from jobs.tests.test_views import make_job

from .helpers import (
    assert_fits_the_screen,
    assert_not_reloaded,
    make_employer,
    make_worker,
    mark_page,
    phone_page,
)

pytestmark = [pytest.mark.django_db, pytest.mark.story(40)]

DESCRIPTION = "Gartenhaus abreißen, Schutt in den Container."


def test_worker_switches_the_job_description_to_the_original_and_back(new_context):
    """A job in German: "Show original" and "Show translation" swap the description card.

    1. Create an employer's job described in German; Ivan reads the site in English and
       opens the job on a 360 px phone
    2. Expect: "[en] Gartenhaus abreißen, …" and "Translated from German by AI"
    3. Tap "Show original"
    4. Expect: the German text, "Original · Show translation", the same page (no reload)
    5. Tap "Show translation"
    6. Expect: "[en] …" again with "Show original", still no reload; the page fits the screen
    """
    job = make_job(make_employer(), description=DESCRIPTION, original_language="de")
    make_worker("ivan@example.com", "Ivan Petrov", language="en")
    worker = phone_page(new_context, "ivan@example.com")

    worker.goto(f"/jobs/{job.pk}/")
    card = worker.locator("#description")
    expect(card).to_contain_text(f"[en] {DESCRIPTION}")
    expect(card).to_contain_text("Translated from German by AI")
    mark_page(worker)

    card.get_by_role("link", name="Show original").click()
    expect(card.locator("p").first).to_have_text(DESCRIPTION)
    expect(card).to_contain_text("Original")
    assert_not_reloaded(worker)

    card.get_by_role("link", name="Show translation").click()
    expect(card.locator("p").first).to_have_text(f"[en] {DESCRIPTION}")
    expect(card.get_by_role("link", name="Show original")).to_be_visible()
    assert_not_reloaded(worker)
    assert_fits_the_screen(worker)


def test_employer_switches_one_application_message_without_touching_the_other(
    new_context,
):
    """Two messages in other languages: each "Show original" swaps only its own message.

    1. Create a job; Olga applies in Polish, Ivan in Ukrainian; the employer reads the site
       in English and opens the job on a 360 px phone
    2. Expect: both messages as "[en] …"
    3. Tap "Show original" under Olga's message
    4. Expect: Olga's Polish text; Ivan's message still "[en] …"
    5. Tap "Show original" under Ivan's message
    6. Expect: Ivan's Ukrainian text; Olga's message still Polish (only Ivan's block swapped)
    7. Tap "Show translation" under Olga's message
    8. Expect: Olga's "[en] …" again, Ivan's still Ukrainian; no reload; fits the screen
    """
    employer = make_employer(language="en")
    job = make_job(employer)
    texts = {
        "olga@example.com": ("Olga Nowak", "pl", "Mam własne narzędzia."),
        "ivan@example.com": ("Ivan Petrov", "uk", "Маю власні інструменти."),
    }
    blocks = {}
    for email, (name, language, message) in texts.items():
        worker = make_worker(email, name, language=language)
        application = Application.objects.create(
            job=job,
            worker=worker,
            workers_offered=1,
            message=message,
            original_language=language,
        )
        blocks[email] = f"#message-{application.pk}"
    boss = phone_page(new_context, "anna@example.com")

    boss.goto(f"/jobs/{job.pk}/")
    olga = boss.locator(blocks["olga@example.com"])
    ivan = boss.locator(blocks["ivan@example.com"])
    expect(olga.locator("p").first).to_have_text("“[en] Mam własne narzędzia.”")
    expect(ivan.locator("p").first).to_have_text("“[en] Маю власні інструменти.”")
    mark_page(boss)

    olga.get_by_role("link", name="Show original").click()
    expect(olga.locator("p").first).to_have_text("“Mam własne narzędzia.”")
    expect(ivan.locator("p").first).to_have_text("“[en] Маю власні інструменти.”")

    ivan.get_by_role("link", name="Show original").click()
    expect(ivan.locator("p").first).to_have_text("“Маю власні інструменти.”")
    expect(olga.locator("p").first).to_have_text("“Mam własne narzędzia.”")

    olga.get_by_role("link", name="Show translation").click()
    expect(olga.locator("p").first).to_have_text("“[en] Mam własne narzędzia.”")
    expect(ivan.locator("p").first).to_have_text("“Маю власні інструменти.”")
    assert_not_reloaded(boss)
    assert_fits_the_screen(boss)
