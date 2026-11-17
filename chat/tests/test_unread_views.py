"""Integration tests: marking messages read, the unread badge and the "Chats" page (#35).

Each test goes through the whole stack: middleware, URL, view, context processor, template
and database. Spec: docs/specs/chat.md, iteration 3 (R20, R22-R26, D16-D21), acceptance
criteria AC11, AC13, AC14. The count itself is in test_unread.py.
"""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from chat.models import Message
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer

from .helpers import NOW, apply, chat_url, write

pytestmark = [pytest.mark.django_db, pytest.mark.story(35)]

HOUR = datetime.timedelta(hours=1)
CHATS_URL = "/chat/"  # chat_list (R24); a plain string, so the tests fail, not crash, until it exists
NO_CHATS = "No chats yet. A chat opens when an application is accepted."


def read_at(message):
    """When `message` was read, as saved now."""
    message.refresh_from_db()
    return message.read_at


# Marking read (R20, D17; AC11)


def test_opening_the_chat_marks_the_other_side_read(
    client, application, employer, worker
):
    """Opening is reading: Anna's messages are read, Ivan's own and other chats are not.

    1. Save two messages of Anna and one of Ivan; one of Bob in another chat of Ivan
    2. Open the chat with Anna as Ivan
    3. Expect: Anna's two read now; Ivan's own and Bob's still unread
    """
    first = write(application, employer, "One")
    second = write(application, employer, "Two")
    own = write(application, worker, "Mine")
    bob = make_employer("bob@example.com")
    other = write(apply(bob, worker), bob, "Other chat")
    client.force_login(worker)

    client.get(chat_url(application))

    assert [read_at(m) for m in (first, second, own, other)] == [NOW, NOW, None, None]


def test_an_empty_answer_marks_nothing(client, application, employer, worker):
    """A 204 draws nothing, so nothing is read (R20, D17).

    1. Save a message of Anna; ask as Ivan after its id (nothing newer)
    2. Expect: 204; the message still unread
    """
    message = write(application, employer, "Hello")
    client.force_login(worker)

    response = client.get(chat_url(application), {"after": message.pk})

    assert response.status_code == 204
    assert read_at(message) is None


def test_a_poll_with_a_new_message_marks_it(client, application, employer, worker):
    """The poll that brings Anna's answer draws it on Ivan's page: read (R20, D17).

    1. Save Ivan's question and Anna's answer
    2. Ask as Ivan after the question
    3. Expect: the answer is read
    """
    question = write(application, worker, "Is there parking?")
    answer = write(application, employer, "Yes.", NOW + HOUR)
    client.force_login(worker)

    client.get(chat_url(application), {"after": question.pk})

    assert read_at(answer) == NOW


def test_a_form_error_marks_read_too(client, application, employer, worker):
    """The page with the form error shows the messages too (R20).

    1. Save a message of Anna; POST an empty message as Ivan
    2. Expect: Anna's message is read
    """
    message = write(application, employer, "Hello")
    client.force_login(worker)

    client.post(chat_url(application), {"text": ""})

    assert read_at(message) == NOW


def test_the_badge_counts_what_the_page_has_just_shown(
    client, application, employer, worker
):
    """On the chat page itself the badge is drawn after marking, so it does not count it.

    1. Save a message of Anna; open the chat as Ivan
    2. Expect: no unread badge
    """
    write(application, employer, "Hello")
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertNotContains(response, "unread message")


# The badge (R21-R23, D18, D19; AC13)


@pytest.mark.parametrize("who", ["worker", "employer"])
def test_badge_shows_the_unread_count(client, application, employer, worker, who):
    """The menu button and "Chats" show the count, for both sides (R23, D19).

    1. Save three messages to the user from the other side
    2. Open "My applications" / "My jobs"
    3. Expect: "3 unread messages" twice (the menu button and "Chats"); the "Chats" link
    """
    me, other = (worker, employer) if who == "worker" else (employer, worker)
    for text in ("One", "Two", "Three"):
        write(application, other, text)
    client.force_login(me)
    page = "my_applications" if who == "worker" else "my_jobs"

    response = client.get(reverse(page))

    assertContains(response, "3 unread messages", count=2)
    assertContains(response, f'href="{CHATS_URL}"')


def test_one_unread_message_is_singular(client, application, employer, worker):
    """One message: "1 unread message", the singular (R23).

    1. Save one message of Anna; open "My applications" as Ivan
    2. Expect: "1 unread message", not "messages"
    """
    write(application, employer, "Hello")
    client.force_login(worker)

    response = client.get(reverse("my_applications"))

    assertContains(response, "1 unread message<")
    assertNotContains(response, "1 unread messages")


def test_no_badge_without_unread_messages(client, application, employer, worker):
    """Nothing unread: no badge, but the "Chats" link stays (R23).

    1. Save a read message of Anna; open "My applications" as Ivan
    2. Expect: no "unread"; the "Chats" link
    """
    message = write(application, employer, "Hello")
    Message.objects.filter(pk=message.pk).update(read_at=NOW)
    client.force_login(worker)

    response = client.get(reverse("my_applications"))

    assertNotContains(response, "unread message")
    assertContains(response, f'href="{CHATS_URL}"')


def test_guest_page_does_not_count(client, monkeypatch):
    """A guest has no chats: the context processor asks the database nothing (R22, D18).

    1. Make unread_count fail if it is called
    2. Open the job list as a guest
    3. Expect: 200; no "Chats" link
    """

    def must_not_run(user):
        """Fails the test if a guest's page counts."""
        raise AssertionError("counted for a guest")

    monkeypatch.setattr("chat.context_processors.unread_count", must_not_run)

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assertNotContains(response, f'href="{CHATS_URL}"')


# The "Chats" page (R24, R25, D16, D20, D21; AC14)


def test_chats_page_lists_readable_chats_newest_first(client, employer, worker):
    """Every chat Ivan can read, the newest activity on top (R24, D20).

    The applications are saved in another order than the expected one (Eva first), so the
    order comes from the messages, not from the ids.

    1. Ivan's chats: with Eva (accepted now, no message yet), with Anna (last message 2
       hours ago), with Bob (1 hour ago)
    2. Not listed: a pending application to Karl; a cancelled one of Lena without
       messages; one of Mia accepted for yesterday without messages; Olga's chat with Anna
    3. Open "Chats" as Ivan
    4. Expect: Eva, Bob, Anna in this order; not Karl, Lena, Mia, Olga's chat
    """
    apply(make_employer("eva@example.com", name="Eva Engel"), worker)
    write(apply(employer, worker), employer, "Hi", NOW - 2 * HOUR)
    bob = make_employer("bob@example.com", name="Bob Berger")
    write(apply(bob, worker), bob, "Hi", NOW - HOUR)
    apply(make_employer("karl@example.com", name="Karl Kurz"), worker, "pending")
    apply(make_employer("lena@example.com", name="Lena Lang"), worker, "cancelled")
    mia = make_employer("mia@example.com", name="Mia Moser")
    apply(mia, worker, date=NOW.date() - datetime.timedelta(days=1))
    olga = make_worker("olga@example.com")
    write(apply(employer, olga), olga, "Message in the chat of Olga")
    client.force_login(worker)

    response = client.get(CHATS_URL)

    page = response.content.decode()
    assert page.index("Eva Engel") < page.index("Bob Berger") < page.index("Anna Huber")
    for absent in ("Karl Kurz", "Lena Lang", "Mia Moser", "chat of Olga"):
        assert absent not in page


def test_employer_sees_the_workers(client, application, employer, worker):
    """The employer's list names the workers and links to the chat (R24).

    1. Save a message of Ivan; open "Chats" as Anna
    2. Expect: "Ivan Petrenko", the job type, a link to the chat
    """
    write(application, worker, "Hello")
    client.force_login(employer)

    response = client.get(CHATS_URL)

    assertContains(response, "Ivan Petrenko")
    assertContains(response, "Demolition")
    assertContains(response, f'href="{chat_url(application)}"')


def test_row_shows_the_last_message_cut_and_its_unread_count(
    client, application, employer, worker
):
    """Each row: the last message, cut to 60 characters, and that chat's count (R24, D21).

    1. In the chat with Anna: an old message, then a long last one of Anna, both unread;
       before them an own message of Ivan that Anna has not read (not counted for Ivan)
    2. In the chat with Bob: one unread message
    3. Open "Chats" as Ivan
    4. Expect: the long message cut with "…", not the old one; "2 unread messages" for
       Anna's row, "1 unread message" for Bob's, "3 unread messages" in the menu
    """
    long_text = (
        "Please bring gloves, helmets, safety boots and two hammer drills for us."
    )
    write(application, worker, "Own message", NOW - 2 * HOUR)
    write(application, employer, "Old message", NOW - HOUR)
    write(application, employer, long_text)
    bob = make_employer("bob@example.com", name="Bob Berger")
    write(apply(bob, worker), bob, "Hi")
    client.force_login(worker)

    response = client.get(CHATS_URL)

    assertContains(response, long_text[:59] + "…")
    assertNotContains(response, long_text)
    assertNotContains(response, "Old message")
    assertContains(response, "2 unread messages")
    assertContains(response, "1 unread message<")
    assertContains(response, "3 unread messages")


def test_no_chats_yet(client, worker):
    """Nothing to list: the line says when a chat opens (R24).

    1. Open "Chats" as Ivan, who has no accepted application
    2. Expect: the empty line
    """
    client.force_login(worker)

    assertContains(client.get(CHATS_URL), NO_CHATS)


def test_guest_is_sent_to_login(client):
    """Logged in only (R24).

    1. Open "Chats" without logging in
    2. Expect: a redirect to the login page
    """
    response = client.get(CHATS_URL)

    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


def count_queries(client):
    """How many database queries the "Chats" page makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(CHATS_URL)
    assert response.status_code == 200
    return len(queries)


def test_queries_do_not_grow_with_the_chats(client, application, employer, worker):
    """Names, jobs, last messages and counts come at once, not per row (R25).

    The two added chats are cancelled: readable only because of their messages, so
    without has_messages each row would ask the database.

    1. One chat of Ivan with a message; count the queries of "Chats"
    2. Add two cancelled chats with messages; count again
    3. Expect: the same number
    """
    write(application, employer, "Hi")
    client.force_login(worker)
    with_one = count_queries(client)

    for email in ("bob@example.com", "eva@example.com"):
        other = make_employer(email)
        write(apply(other, worker, "cancelled"), other, "Hi")
    with_three = count_queries(client)

    assert with_three == with_one
