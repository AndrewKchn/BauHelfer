"""Unit tests: when a message was read, and how many are unread (#35).

Spec: docs/specs/chat.md, iteration 3 (R19, R21, D15), acceptance criterion AC12. Marking
read, the badge and the "Chats" page are in test_unread_views.py.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from chat.models import unread_count
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer

from .helpers import NOW, apply, write

pytestmark = [pytest.mark.django_db, pytest.mark.story(35)]


def read(message):
    """Mark `message` read now."""
    message.read_at = NOW
    message.save()
    return message


def test_new_message_is_unread(application, worker):
    """A message starts unread (R19).

    1. Save a message of Ivan
    2. Expect: read_at is empty
    """
    assert write(application, worker, "Hello").read_at is None


def test_unread_count_counts_the_other_side_in_all_chats(application, employer, worker):
    """The other people's unread messages in all the user's chats (R21, D15).

    1. In Anna's chat with Ivan: two unread and one read message of Ivan, one of Anna
    2. In Anna's chat with Olga (another job): one unread message of Olga
    3. In Bob's chat with Petr (not Anna's): one unread message of Petr
    4. Expect: Anna 3 (Ivan's two + Olga's); Ivan 1 (Anna's); Olga 0
    """
    write(application, worker, "One")
    write(application, worker, "Two")
    read(write(application, worker, "Seen"))
    write(application, employer, "From Anna")
    olga = make_worker("olga@example.com")
    write(apply(employer, olga), olga, "From Olga")
    petr = make_worker("petr@example.com")
    write(apply(make_employer("bob@example.com"), petr), petr, "Not Anna's")

    counts = (unread_count(employer), unread_count(worker), unread_count(olga))

    assert counts == (3, 1, 0)


def test_unread_count_is_one_query(application, employer, worker):
    """However many chats, one query (R21): it runs on every page.

    1. Save unread messages in two chats of Anna
    2. Count Anna's unread messages
    3. Expect: 2, and one query
    """
    write(application, worker, "One")
    olga = make_worker("olga@example.com")
    write(apply(employer, olga), olga, "Two")

    with CaptureQueriesContext(connection) as queries:
        count = unread_count(employer)

    assert (count, len(queries)) == (2, 1)
