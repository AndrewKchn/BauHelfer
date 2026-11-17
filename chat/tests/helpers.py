"""Shared data for the chat's view tests (#35): a fixed "now" and small builders.

Not a test file (no test_ prefix); the fixtures that use it are in conftest.py.
"""

import datetime
from zoneinfo import ZoneInfo

from django.urls import reverse

from chat.models import Message
from jobs.models import Application
from jobs.tests.test_views import make_job

# A fixed "now": 17 November 2026, 10:00 in Munich.
MUNICH = ZoneInfo("Europe/Berlin")
NOW = datetime.datetime(2026, 11, 17, 10, 0, tzinfo=MUNICH)
TODAY = NOW.date()
DAY = datetime.timedelta(days=1)


def apply(employer, worker, status="accepted", date=TODAY):
    """`worker`'s application to a new job of `employer` on `date`."""
    taken = 1 if status in ("accepted", "cancelled") else 0
    return Application.objects.create(
        job=make_job(employer, date=date),
        worker=worker,
        status=status,
        workers_accepted=taken,
    )


def write(application, sender, text, at=NOW):
    """Save a message of `sender`, sent at `at`."""
    message = Message.objects.create(application=application, sender=sender, text=text)
    Message.objects.filter(pk=message.pk).update(created_at=at)
    return message


def chat_url(application):
    """The chat page of `application`."""
    return reverse("chat", args=[application.pk])
