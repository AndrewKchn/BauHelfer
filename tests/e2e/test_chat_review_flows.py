"""E2E tests: the M6 chat and review flows in a real browser (Chromium via Playwright) (#40).

A worker and an employer act at the same time, each on their own 360 px phone, as in
test_application_flows.py. They read the site in two languages: the chat translates each
message into the reader's language. Translations come from FakeClaudeBackend (base.py), which
marks a text with the target language: "[en] Привіт" is the English "translation".

What only a browser shows here: a message arriving by HTMX polling without a reload, "Show
original" swapping one bubble, the "Mark as done" confirm dialog, the stars of the review form.
"""

import datetime

import pytest
from django.utils import timezone, translation
from playwright.sync_api import expect

from jobs.models import Application, Job
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

# The chat asks for new messages every 4 s (chat.html); Playwright waits 5 s by default.
POLL_WAIT = 10_000  # ms


def ukrainian(text, plural=None, count=None):
    """The Ukrainian of a UI string, so the worker's steps name what the worker sees."""
    with translation.override("uk"):
        if plural is None:
            return translation.gettext(text)
        return translation.ngettext(text, plural, count) % {"stars": count}


def test_chat_done_and_reviews_on_two_phones_in_two_languages(new_context):
    """Worker and employer chat in two languages, the job is done, both rate, ratings show.

    1. Create an employer (English) and a job next week for 1 worker; Ivan (Ukrainian) is
       accepted; each logs in on a 360 px phone
    2. Ivan opens "My applications", taps "Chat" (in Ukrainian), sends two messages
    3. The employer opens the chat from the job page and leaves it open
    4. Expect: both messages as "[en] …" with "Translated from Ukrainian by AI"
    5. Ivan sends a third message; the employer does nothing
    6. Expect: on the employer's phone it appears within a poll, translated, no reload
    7. The employer taps "Show original" under the second message, then under the first
    8. Expect: each tap swaps only its bubble: both show Ivan's Ukrainian text, the third
       stays "[en] …"; "Show translation" under the second brings back only its "[en] …",
       the first stays original; no reload
    9. The employer answers; Expect: on Ivan's open chat, "[uk] …" appears within a poll
    10. The work day passes (the job moves to yesterday)
    11. The employer opens "My jobs", taps "Mark as done", dismisses the dialog
    12. Expect: the job is not done; tap again and accept: "Job marked as done."
    13. The employer taps "Rate the workers", "Rate", picks 5 stars, publishes
    14. Expect: "Review published.", Ivan's application still "No reviews yet" (hidden until
        Ivan rates too)
    15. Ivan opens "My applications", taps "Rate the employer", picks 4 stars, publishes
    16. Expect: the employer sees "★ 5.0 (1)" on Ivan's application and "★ 5.0 (1 review)"
        on Ivan's profile; Ivan sees the employer's "★ 4,0 (1 …)" in Ukrainian
    17. Expect: no page on the way is wider than the screen
    """
    employer = make_employer(language="en")
    job = make_job(
        employer,
        workers_needed=1,
        date=timezone.localdate() + datetime.timedelta(days=7),
    )
    ivan = make_worker("ivan@example.com", "Ivan Petrov", language="uk")
    application = Application.objects.create(job=job, worker=ivan, workers_offered=1)
    application.accept()  # the model's own accept: the job is filled (the #28 flow)
    worker = phone_page(new_context, "ivan@example.com")
    boss = phone_page(new_context, "anna@example.com")

    # 2. Ivan writes from "My applications"
    worker.goto("/jobs/applications/")
    worker.get_by_role("link", name=ukrainian("Chat"), exact=True).click()
    for text in ("Привіт, я буду о восьмій.", "Чи потрібні рукавиці?"):
        worker.get_by_role("textbox").fill(text)
        worker.get_by_role("button", name=ukrainian("Send")).click()
    expect(worker.get_by_text("Чи потрібні рукавиці?")).to_be_visible()
    assert_fits_the_screen(worker)

    # 3-4. The employer opens the chat: Ivan's messages in English
    boss.goto(f"/jobs/{job.pk}/")
    boss.get_by_role("link", name="Chat", exact=True).click()
    first = boss.locator(".chat-start").nth(0)
    second = boss.locator(".chat-start").nth(1)
    expect(first).to_contain_text("[en] Привіт, я буду о восьмій.")
    expect(second).to_contain_text("[en] Чи потрібні рукавиці?")
    expect(second).to_contain_text("Translated from Ukrainian by AI")
    assert_fits_the_screen(boss)
    mark_page(boss)

    # 5-6. A new message reaches the open chat by polling
    worker.get_by_role("textbox").fill("Я вже на місці.")
    worker.get_by_role("button", name=ukrainian("Send")).click()
    expect(boss.get_by_text("[en] Я вже на місці.")).to_be_visible(timeout=POLL_WAIT)
    assert_not_reloaded(boss)

    # 7-8. "Show original" swaps only its own bubble: the one shown before stays
    first, second, third = (
        boss.locator(".chat-start .chat-bubble").nth(i) for i in range(3)
    )
    boss.locator(".chat-start").nth(1).get_by_role("link", name="Show original").click()
    expect(second).to_have_text("Чи потрібні рукавиці?")
    expect(first).to_have_text("[en] Привіт, я буду о восьмій.")
    boss.locator(".chat-start").nth(0).get_by_role("link", name="Show original").click()
    expect(first).to_have_text("Привіт, я буду о восьмій.")
    expect(second).to_have_text("Чи потрібні рукавиці?")
    expect(third).to_have_text("[en] Я вже на місці.")
    boss.locator(".chat-start").nth(1).get_by_role(
        "link", name="Show translation"
    ).click()
    expect(second).to_have_text("[en] Чи потрібні рукавиці?")
    expect(first).to_have_text("Привіт, я буду о восьмій.")
    assert_not_reloaded(boss)

    # 9. The answer reaches Ivan's open chat, in Ukrainian
    boss.get_by_role("textbox").fill("Yes, bring gloves.")
    boss.get_by_role("button", name="Send").click()
    expect(worker.get_by_text("[uk] Yes, bring gloves.")).to_be_visible(
        timeout=POLL_WAIT
    )

    # 10. The work day passes
    Job.objects.filter(pk=job.pk).update(
        date=timezone.localdate() - datetime.timedelta(days=1)
    )

    # 11-12. "Mark as done" asks first; "Cancel" changes nothing
    boss.goto("/jobs/mine/")
    boss.once("dialog", lambda dialog: dialog.dismiss())
    boss.get_by_role("button", name="Mark as done").click()
    expect(boss.get_by_role("button", name="Mark as done")).to_be_visible()
    job.refresh_from_db()
    assert job.status == Job.Status.FILLED
    boss.once("dialog", lambda dialog: dialog.accept())
    boss.get_by_role("button", name="Mark as done").click()
    expect(boss.get_by_text("Job marked as done.")).to_be_visible()
    assert_fits_the_screen(boss)

    # 13-14. The employer rates Ivan; the review waits for Ivan's
    boss.get_by_role("link", name="Rate the workers").click()
    boss.get_by_role("link", name="Rate", exact=True).click()
    boss.get_by_role("radio", name="5 stars").check()
    assert_fits_the_screen(boss)
    boss.get_by_role("button", name="Publish review").click()
    expect(boss.get_by_text("Review published.")).to_be_visible()
    expect(boss.locator("#applications")).to_contain_text("No reviews yet")

    # 15. Ivan rates the employer
    worker.goto("/jobs/applications/")
    worker.get_by_role("link", name=ukrainian("Rate the employer")).click()
    worker.get_by_role(
        "radio", name=ukrainian("%(stars)s star", "%(stars)s stars", 4)
    ).check()
    assert_fits_the_screen(worker)
    worker.get_by_role("button", name=ukrainian("Publish review")).click()
    expect(worker.get_by_text(ukrainian("Review published."))).to_be_visible()

    # 16. Both reviews are visible now
    boss.goto(f"/jobs/{job.pk}/")
    expect(boss.locator("#applications")).to_contain_text("★ 5.0 (1)")
    boss.goto(f"/accounts/workers/{ivan.pk}/")
    expect(boss.get_by_text("★ 5.0 (1 review)")).to_be_visible()
    assert_fits_the_screen(boss)
    worker.goto(f"/accounts/employers/{employer.pk}/")
    expect(worker.get_by_text("★ 4,0 (1")).to_be_visible()
    assert_fits_the_screen(worker)
    assert application.reviews.count() == 2
