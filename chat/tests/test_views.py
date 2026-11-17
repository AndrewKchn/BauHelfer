"""Integration tests: the chat page and the "Chat" links to it (#35).

Each test goes through the whole stack: middleware, URL, view, form, template and database.
Spec: docs/specs/chat.md, iteration 1 (R4-R11, D1, D4, D6-D8), acceptance criteria AC3-AC7.
When a chat can be written and read is in test_models.py.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from chat.models import Message
from jobs.models import Application
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(35)]

# A fixed "now": 17 November 2026, 10:00 in Munich.
MUNICH = ZoneInfo("Europe/Berlin")
NOW = datetime.datetime(2026, 11, 17, 10, 0, tzinfo=MUNICH)
TODAY = NOW.date()
DAY = datetime.timedelta(days=1)

CLOSED = "This chat is closed. You can still read it."
EMPTY = "No messages yet. Write the first one."


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    """Fix the clock at NOW, so the test does not depend on when it runs."""
    monkeypatch.setattr(timezone, "now", lambda: NOW)


@pytest.fixture
def employer():
    """Anna Huber, the employer of the job."""
    return make_employer("anna@example.com", name="Anna Huber")


@pytest.fixture
def worker():
    """Ivan Petrenko, the worker."""
    user = make_worker("ivan@example.com")
    user.name = "Ivan Petrenko"
    user.save()
    return user


def apply(employer, worker, status="accepted", date=TODAY):
    """`worker`'s application to a new job of `employer` on `date`."""
    taken = 1 if status in ("accepted", "cancelled") else 0
    return Application.objects.create(
        job=make_job(employer, date=date),
        worker=worker,
        status=status,
        workers_accepted=taken,
    )


@pytest.fixture
def application(employer, worker):
    """Ivan's accepted application to Anna's job today."""
    return apply(employer, worker)


def write(application, sender, text, at=NOW):
    """Save a message of `sender`, sent at `at`."""
    message = Message.objects.create(application=application, sender=sender, text=text)
    Message.objects.filter(pk=message.pk).update(created_at=at)
    return message


def chat_url(application):
    """The chat page of `application`."""
    return reverse("chat", args=[application.pk])


# Who gets the page (R4, D4; AC3)


@pytest.mark.parametrize("who", ["worker", "employer"])
def test_both_participants_see_the_messages_oldest_first(
    client, application, employer, worker, who
):
    """The worker and the employer read the same chat, oldest message on top (R4, R5).

    1. Save Ivan's question at 08:14 and Anna's answer at 08:20
    2. Open the chat as Ivan / as Anna
    3. Expect: 200; the question above the answer
    """
    write(application, worker, "Is there parking?", NOW.replace(hour=8, minute=14))
    write(application, employer, "Yes, in the yard.", NOW.replace(hour=8, minute=20))
    client.force_login(worker if who == "worker" else employer)

    response = client.get(chat_url(application))

    page = response.content.decode()
    assert response.status_code == 200
    assert page.index("Is there parking?") < page.index("Yes, in the yard.")


@pytest.mark.parametrize("role", ["worker", "employer"])
def test_stranger_gets_404(client, application, role):
    """Another worker or employer cannot tell the chat exists (R4, D4).

    1. Log in as another worker / another employer
    2. GET the chat; POST a message to it
    3. Expect: 404 both times; no message saved
    """
    if role == "worker":
        stranger = make_worker("olga@example.com")
    else:
        stranger = make_employer("bob@example.com")
    client.force_login(stranger)

    get = client.get(chat_url(application))
    post = client.post(chat_url(application), {"text": "Hi"})

    assert (get.status_code, post.status_code) == (404, 404)
    assert not Message.objects.exists()


def test_guest_is_sent_to_login(client, application):
    """Logged in only (R4).

    1. Open the chat without logging in
    2. Expect: a redirect to the login page
    """
    response = client.get(chat_url(application))

    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


def test_pending_application_has_no_chat(client, employer, worker):
    """Not accepted: nothing to read or write, 404 (R3, R4).

    1. Save Ivan's pending application
    2. Open its chat as Ivan and as Anna
    3. Expect: 404 both times
    """
    pending = apply(employer, worker, "pending")

    client.force_login(worker)
    as_worker = client.get(chat_url(pending)).status_code
    client.force_login(employer)
    as_employer = client.get(chat_url(pending)).status_code

    assert (as_worker, as_employer) == (404, 404)


# Sending (R6; AC4)


@pytest.mark.parametrize("who", ["worker", "employer"])
def test_participant_sends_a_message(client, application, employer, worker, who):
    """POST saves the message with its sender and goes back to the chat (R6).

    1. Log in as Ivan / Anna; POST "See you at 7"
    2. Expect: a redirect to the chat; one message with that text and sender
    """
    sender = worker if who == "worker" else employer
    client.force_login(sender)

    response = client.post(chat_url(application), {"text": "See you at 7"})

    assert response.status_code == 302
    assert response.url == chat_url(application)
    message = application.messages.get()
    assert (message.text, message.sender) == ("See you at 7", sender)


@pytest.mark.parametrize("text", ["", "   "], ids=["empty", "spaces"])
def test_empty_message_is_refused(client, application, worker, text):
    """Nothing to send: the form error, nothing saved (R6).

    1. POST an empty text / only spaces as Ivan
    2. Expect: 200 with the form error; no message
    """
    client.force_login(worker)

    response = client.post(chat_url(application), {"text": text})

    assert response.status_code == 200
    assert response.context["form"].errors["text"]
    assert not Message.objects.exists()


def test_message_longer_than_1000_characters_is_refused(client, application, worker):
    """The form says so before the database would (R1, D5).

    1. POST 1001 characters as Ivan
    2. Expect: 200 with the form error; no message
    """
    client.force_login(worker)

    response = client.post(chat_url(application), {"text": "a" * 1001})

    assert response.context["form"].errors["text"]
    assert not Message.objects.exists()


def test_closed_chat_takes_no_message(client, employer, worker):
    """After the day of the job the chat can be read, not written: POST gives 404 (R6).

    1. Save Ivan's accepted application of a job yesterday, with one message
    2. POST a new message as Ivan
    3. Expect: 404; still one message
    """
    yesterday = apply(employer, worker, date=TODAY - DAY)
    write(yesterday, worker, "Thanks for the work!", NOW - DAY)
    client.force_login(worker)

    response = client.post(chat_url(yesterday), {"text": "Where is my money?"})

    assert response.status_code == 404
    assert yesterday.messages.count() == 1


# The page (R5, R7-R10, D7, D8; AC5, AC6)


def test_closed_chat_shows_the_messages_without_the_form(client, employer, worker):
    """A cancelled application with messages: read only (R9, D1).

    1. Save Ivan's cancelled application with one message
    2. Open the chat as Ivan
    3. Expect: the message and the "closed" line; no text field
    """
    cancelled = apply(employer, worker, "cancelled")
    write(cancelled, employer, "Sorry, the customer postponed it.")
    client.force_login(worker)

    response = client.get(chat_url(cancelled))

    assertContains(response, "Sorry, the customer postponed it.")
    assertContains(response, CLOSED)
    assertNotContains(response, 'name="text"')


def test_open_chat_shows_the_form(client, application, worker):
    """A writable chat has the text field and no "closed" line (R5, R9, R10).

    1. Open the empty chat of Ivan's accepted application as Ivan
    2. Expect: the text field, the "no messages yet" line; not the "closed" line
    """
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, 'name="text"')
    assertContains(response, EMPTY)
    assertNotContains(response, CLOSED)


def test_own_messages_are_on_the_right(client, application, employer, worker):
    """Own messages: right, primary colour, "you"; the other's on the left (R8, D7).

    1. Save one message of Anna and one of Ivan
    2. Open the chat as Ivan
    3. Expect: one chat-end bubble in the primary colour and one chat-start bubble
    """
    write(application, employer, "Yes, in the yard.")
    write(application, worker, "Thanks!")
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, "chat-end", count=1)
    assertContains(response, "chat-start", count=1)
    assertContains(response, "chat-bubble-primary", count=1)


def test_time_is_munich_time(client, application, worker):
    """The time under a message is Munich time, hours and minutes (R8).

    1. Save a message at 08:14 UTC, which is 09:14 in Munich in November
    2. Open the chat as Ivan
    3. Expect: "09:14"
    """
    utc_time = datetime.datetime(2026, 11, 17, 8, 14, tzinfo=datetime.UTC)
    write(application, worker, "Hello", utc_time)
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, "09:14")


def test_one_date_line_per_day(client, application, employer, worker):
    """A date line before the first message of each day (R8, D8).

    1. Save two messages yesterday and one today
    2. Open the chat as Ivan
    3. Expect: two date lines
    """
    write(application, worker, "One", NOW - DAY)
    write(application, employer, "Two", NOW - DAY)
    write(application, worker, "Three", NOW)
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, "data-day=", count=2)


def test_date_line_follows_the_munich_day(client, application, worker):
    """After midnight in Munich is a new day, although it is still the same day in UTC (R8).

    1. Save a message at 22:00 and one at 00:30 the next night, Munich time (21:00 and
       23:30 UTC, the same UTC day)
    2. Open the chat as Ivan
    3. Expect: two date lines
    """
    write(
        application,
        worker,
        "Late",
        datetime.datetime(2026, 11, 16, 22, 0, tzinfo=MUNICH),
    )
    write(
        application,
        worker,
        "Later",
        datetime.datetime(2026, 11, 17, 0, 30, tzinfo=MUNICH),
    )
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, "data-day=", count=2)


def test_message_text_is_escaped(client, application, employer, worker):
    """A message is text, never HTML: no script runs in the other person's browser.

    1. Save a message "<script>alert(1)</script>" of Anna
    2. Open the chat as Ivan
    3. Expect: the escaped text; no <script>alert
    """
    write(application, employer, "<script>alert(1)</script>")
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
    assertNotContains(response, "<script>alert(1)")


def test_worker_sees_the_employer_and_a_way_back(client, application, worker):
    """The header: the other person's name and the back link (R7).

    1. Open the chat as Ivan
    2. Expect: "Anna Huber"; the back link leads to "My applications" (checked in the
       context: the navigation has a link there too)
    """
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, "Anna Huber")
    assert response.context["back_url"] == reverse("my_applications")
    assertContains(response, f'href="{response.context["back_url"]}" class="btn')


def test_employer_sees_the_worker_and_a_way_back(client, application, employer):
    """The header: the worker's name and the back link to the application (R7).

    1. Open the chat as Anna
    2. Expect: "Ivan Petrenko" and a link to the job page at the application
    """
    client.force_login(employer)

    response = client.get(chat_url(application))

    back = reverse("job_detail", args=[application.job.pk])
    assertContains(response, "Ivan Petrenko")
    assertContains(response, f'href="{back}#application-{application.pk}"')


def count_queries(client, url):
    """How many database queries one GET of `url` makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url)
    assert response.status_code == 200
    return len(queries)


def test_queries_do_not_grow_with_the_messages(client, application, employer, worker):
    """Messages and their senders come at once, not per message (R5; AC6).

    1. Save one message; count the queries of the chat
    2. Add four more from both sides; count again
    3. Expect: the same number
    """
    write(application, worker, "1")
    client.force_login(worker)
    with_one = count_queries(client, chat_url(application))

    for text in "2345":
        write(application, employer if text in "24" else worker, text)
    with_five = count_queries(client, chat_url(application))

    assert with_five == with_one


# The "Chat" links (R11, D6; AC7)


@pytest.mark.parametrize(
    ("status", "with_message", "linked"),
    [
        ("accepted", False, True),
        ("pending", False, False),
        ("cancelled", True, True),
        ("cancelled", False, False),
    ],
    ids=["accepted", "pending", "cancelled-with-message", "cancelled-without"],
)
def test_my_applications_links_to_a_readable_chat(
    client, employer, worker, status, with_message, linked
):
    """The worker's card has "Chat" when the chat can be read (R11, D6).

    1. Save Ivan's application with this status; a message or none
    2. Open "My applications" as Ivan
    3. Expect: the link to its chat, or none
    """
    saved = apply(employer, worker, status)
    if with_message:
        write(saved, employer, "Sorry.")
    client.force_login(worker)

    response = client.get(reverse("my_applications"))

    assert (f'href="{chat_url(saved)}"' in response.content.decode()) is linked


@pytest.mark.parametrize(
    ("status", "with_message", "linked"),
    [
        ("accepted", False, True),
        ("pending", False, False),
        ("cancelled", True, True),
        ("cancelled", False, False),
    ],
    ids=["accepted", "pending", "cancelled-with-message", "cancelled-without"],
)
def test_job_page_links_the_owner_to_a_readable_chat(
    client, employer, worker, status, with_message, linked
):
    """The owner's list of applications has "Chat" when the chat can be read (R11, D6).

    1. Save Ivan's application with this status; a message or none
    2. Open the job page as Anna
    3. Expect: the link to its chat, or none
    """
    saved = apply(employer, worker, status)
    if with_message:
        write(saved, worker, "Hello.")
    client.force_login(employer)

    response = client.get(reverse("job_detail", args=[saved.job.pk]))

    assert (f'href="{chat_url(saved)}"' in response.content.decode()) is linked


def test_chat_links_cost_no_query_per_application(client, employer, worker):
    """has_messages comes with the applications, on both pages (R11).

    Cancelled applications with a message: their chat is readable only because of the
    message, so without has_messages each card would ask the database.

    1. One job of Anna with Ivan's cancelled application and a message; count the queries
       of "My applications" (as Ivan) and of the job page (as Anna)
    2. Add two more cancelled workers with messages to the job and two more cancelled
       applications of Ivan with messages; count again
    3. Expect: the same numbers
    """
    first = apply(employer, worker, "cancelled")
    job = first.job
    write(first, worker, "Hi")

    def counts():
        """Queries of "My applications" as Ivan and of the job page as Anna."""
        client.force_login(worker)
        mine = count_queries(client, reverse("my_applications"))
        client.force_login(employer)
        page = count_queries(client, reverse("job_detail", args=[job.pk]))
        return mine, page

    with_one = counts()

    job.workers_needed = 3
    job.save()
    for email in ("olga@example.com", "petr@example.com"):
        other = Application.objects.create(
            job=job, worker=make_worker(email), status="cancelled", workers_accepted=1
        )
        write(other, employer, "Hi")
    for email in ("bob@example.com", "eva@example.com"):
        write(apply(make_employer(email), worker, "cancelled"), worker, "Hi")

    assert counts() == with_one
