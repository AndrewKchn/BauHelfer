"""Unit tests: the chat message, and when a chat can be written and read (#35).

Spec: docs/specs/chat.md, iteration 1 (R1-R3, D1, D3, D5), acceptance criteria AC1 and AC2.
The chat page is in test_views.py.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.db import DataError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from chat.models import Message, with_has_messages
from jobs.models import Application
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(35)]

# A fixed "now": 17 November 2026, 10:00 in Munich.
MUNICH = ZoneInfo("Europe/Berlin")
NOW = datetime.datetime(2026, 11, 17, 10, 0, tzinfo=MUNICH)
TODAY = NOW.date()
DAY = datetime.timedelta(days=1)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    """Fix the clock at NOW, so the test does not depend on when it runs."""
    monkeypatch.setattr(timezone, "now", lambda: NOW)


@pytest.fixture
def employer():
    """Anna, the employer of the job."""
    return make_employer("anna@example.com")


@pytest.fixture
def worker():
    """Ivan, the worker."""
    return make_worker("ivan@example.com")


def application(employer, worker, status="accepted", date=TODAY):
    """Ivan's application to Anna's job on `date` (08:00, 6 hours)."""
    taken = 1 if status in ("accepted", "cancelled") else 0
    return Application.objects.create(
        job=make_job(employer, date=date),
        worker=worker,
        status=status,
        workers_accepted=taken,
    )


def write(application, sender, text="Is there parking for a van?"):
    """Save a message of `sender` in the chat of `application`."""
    return Message.objects.create(application=application, sender=sender, text=text)


# The message (R1, D5)


def test_message_keeps_sender_text_and_time(employer, worker):
    """A message knows its chat, who wrote it, what and when (R1).

    1. Save a message of Ivan in the chat of his accepted application
    2. Expect: it is in application.messages, with Ivan, the text and the time now
    """
    accepted = application(employer, worker)

    write(accepted, worker, "Hello!")

    message = accepted.messages.get()
    assert (message.sender, message.text, message.created_at) == (worker, "Hello!", NOW)


def test_messages_are_oldest_first(employer, worker):
    """The chat reads from top to bottom: oldest first, then by id (R1).

    1. Save three messages; give the second one a time before the first
    2. Expect: the second, the first, the third
    """
    accepted = application(employer, worker)
    first = write(accepted, worker, "first")
    second = write(accepted, employer, "second")
    third = write(accepted, worker, "third")
    Message.objects.filter(pk=second.pk).update(created_at=NOW - DAY)

    assert list(accepted.messages.all()) == [second, first, third]


def test_text_longer_than_1000_characters_is_refused_by_the_database(employer, worker):
    """At most 1000 characters, the limit of a translation (R1, D5).

    1. Save a message of 1000 characters, then one of 1001
    2. Expect: the first is saved; the second raises DataError (varchar(1000))
    """
    accepted = application(employer, worker)
    write(accepted, worker, "a" * 1000)

    with pytest.raises(DataError), transaction.atomic():
        write(accepted, worker, "a" * 1001)

    assert accepted.messages.count() == 1


def test_messages_go_with_their_application(employer, worker):
    """Deleting the application deletes its chat (R1).

    1. Save a message, then delete the application
    2. Expect: no message left
    """
    accepted = application(employer, worker)
    write(accepted, worker)

    accepted.delete()

    assert not Message.objects.exists()


# Who may write: chat_writable (R2, D1; AC1)


@pytest.mark.parametrize(
    ("status", "date", "writable"),
    [
        ("accepted", TODAY, True),
        ("accepted", TODAY + DAY, True),
        ("accepted", TODAY - DAY, False),
        ("pending", TODAY, False),
        ("rejected", TODAY, False),
        ("closed", TODAY, False),
        ("cancelled", TODAY, False),
        ("withdrawn", TODAY, False),
    ],
    ids=[
        "accepted-today",
        "accepted-tomorrow",
        "accepted-yesterday",
        "pending",
        "rejected",
        "closed",
        "cancelled",
        "withdrawn",
    ],
)
def test_chat_is_writable_only_while_the_contacts_are_shown(
    employer, worker, status, date, writable
):
    """Writing: accepted, until the day of the job is over (R2, D1).

    1. Save an application with this status, its job on this day
    2. Expect: chat_writable True only for an accepted one whose day is not over
    """
    assert application(employer, worker, status, date).chat_writable is writable


# Who may read: chat_readable (R3, D1, D3; AC2)


@pytest.mark.parametrize(
    ("status", "date", "with_message", "readable"),
    [
        ("accepted", TODAY, False, True),
        ("accepted", TODAY - DAY, True, True),
        ("accepted", TODAY - DAY, False, False),
        ("cancelled", TODAY, True, True),
        ("cancelled", TODAY, False, False),
        ("withdrawn", TODAY, True, True),
        ("withdrawn", TODAY, False, False),
        ("pending", TODAY, False, False),
    ],
    ids=[
        "writable",
        "over-with-message",
        "over-without",
        "cancelled-with-message",
        "cancelled-without",
        "withdrawn-with-message",
        "withdrawn-without",
        "pending",
    ],
)
@pytest.mark.parametrize("annotated", [False, True], ids=["plain", "annotated"])
def test_chat_is_readable_while_writable_or_with_messages(
    employer, worker, status, date, with_message, readable, annotated
):
    """Reading: while it can be written, and afterwards if it has a message (R3, D1, D3).

    1. Save an application with this status and day; a message in its chat or none
       (saved directly: the database does not ask chat_writable)
    2. Read it again, plain or with with_has_messages()
    3. Expect: chat_readable as in the table, the same both ways
    """
    saved = application(employer, worker, status, date)
    if with_message:
        write(saved, worker)
    queryset = Application.objects.all()
    if annotated:
        queryset = with_has_messages(queryset)

    assert queryset.get(pk=saved.pk).chat_readable is readable


def test_annotated_readable_makes_no_query(employer, worker):
    """With has_messages loaded, chat_readable asks the database nothing (R3).

    1. Save a cancelled application with a message; load it with with_has_messages()
    2. Ask chat_readable
    3. Expect: True, and no query
    """
    saved = application(employer, worker, "cancelled")
    write(saved, worker)
    loaded = with_has_messages(Application.objects.all()).get(pk=saved.pk)

    with CaptureQueriesContext(connection) as queries:
        readable = loaded.chat_readable

    assert (readable, len(queries)) == (True, 0)
