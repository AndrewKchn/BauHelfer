"""Integration tests: new chat messages without a reload, HTMX polling (#35).

Each test goes through the whole stack: middleware, URL, view, template and database.
Spec: docs/specs/chat.md, iteration 2 (R13-R18, D11-D14), acceptance criteria AC8-AC10.
The chat page itself is in test_views.py.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from pytest_django.asserts import assertContains, assertNotContains

from jobs.tests.test_application import make_worker

from .helpers import DAY, NOW, TODAY, apply, chat_url, write

pytestmark = [pytest.mark.django_db, pytest.mark.story(35)]

HINT = "New messages appear every few seconds."


# The list asks (R13, R18, D12-D14; AC8)


def test_open_chat_asks_every_4_seconds_after_its_last_message(
    client, application, employer, worker
):
    """A writable chat polls with the id of its last message (R13, R18).

    1. Save two messages; open the chat as Ivan
    2. Expect: the list polls every 4 s, sends "after" = the second message's id, and
       takes itself (its own id) out of the answer; the hint above the form
    """
    write(application, worker, "Hello")
    last = write(application, employer, "Hi")
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, 'hx-trigger="every 4s"', count=1)
    assertContains(response, f'"after": {last.pk}')
    assertContains(response, 'id="chat-messages"', count=1)
    assertContains(response, 'hx-select="#chat-messages"', count=1)
    assertContains(response, HINT)


def test_empty_chat_asks_after_0(client, application, worker):
    """No message yet: "after" is 0, so the first message is new (R13).

    1. Open the empty chat as Ivan
    2. Expect: "after": 0
    """
    client.force_login(worker)

    response = client.get(chat_url(application))

    assertContains(response, '"after": 0')


def test_closed_chat_does_not_ask(client, employer, worker):
    """A chat that can only be read gets no new messages: no polling, no hint (D12).

    1. Save Ivan's cancelled application with a message
    2. Open the chat as Ivan
    3. Expect: no hx-trigger, no hint
    """
    cancelled = apply(employer, worker, "cancelled")
    write(cancelled, employer, "Sorry.")
    client.force_login(worker)

    response = client.get(chat_url(cancelled))

    assertNotContains(response, "hx-trigger")
    assertNotContains(response, HINT)


# The answer (R14-R16, D11; AC9)


def test_nothing_new_is_an_empty_204(client, application, worker):
    """Nothing after the last message: 204, empty, and HTMX changes nothing (R14, D11).

    1. Save one message; ask with after = its id
    2. Expect: 204 and an empty body
    """
    last = write(application, worker, "Hello")
    client.force_login(worker)

    response = client.get(chat_url(application), {"after": last.pk})

    assert (response.status_code, response.content) == (204, b"")


def test_a_newer_message_gives_the_whole_list(client, application, employer, worker):
    """Something new: the page with the new message and the new last id (R15).

    1. Save Ivan's message, then Anna's answer
    2. Ask as Ivan with after = Ivan's message
    3. Expect: 200 with Anna's answer; the list now asks after the answer
    """
    seen = write(application, worker, "Is there parking?")
    answer = write(application, employer, "Yes, in the yard.", NOW + DAY / 24)
    client.force_login(worker)

    response = client.get(chat_url(application), {"after": seen.pk})

    assertContains(response, "Yes, in the yard.")
    assertContains(response, f'"after": {answer.pk}')


def test_after_that_is_not_a_number_is_ignored(client, application, worker):
    """?after=abc: the whole page, as without it (R16).

    1. Save one message; ask with after=abc
    2. Expect: 200 with the message
    """
    write(application, worker, "Hello")
    client.force_login(worker)

    response = client.get(chat_url(application), {"after": "abc"})

    assertContains(response, "Hello")


def test_stranger_asking_gets_404(client, application, worker):
    """The access check comes before the 204: a stranger learns nothing (R14, D4).

    1. Save one message; ask with after = its id as another worker
    2. Expect: 404
    """
    last = write(application, worker, "Hello")
    client.force_login(make_worker("olga@example.com"))

    response = client.get(chat_url(application), {"after": last.pk})

    assert response.status_code == 404


# The cost (R17; AC10)


def test_204_renders_no_page(client, application, employer, worker):
    """ "Nothing new" skips the template, and asks the database no more than the page (R17).

    The saving is the page itself (~9 KB, about half the time), not the queries: both make
    4 (session, user, application, then the messages or one EXISTS).

    1. Save three messages; count the queries of the page and of an ask after the last
    2. Expect: the ask renders no template and makes no more queries than the page
    """
    for text in ("one", "two"):
        write(application, worker, text)
    last = write(application, employer, "three")
    client.force_login(worker)

    with CaptureQueriesContext(connection) as page:
        client.get(chat_url(application))
    with CaptureQueriesContext(connection) as ask:
        response = client.get(chat_url(application), {"after": last.pk})

    assert response.status_code == 204
    assert response.templates == []
    assert len(ask) <= len(page)


def test_chat_of_tomorrow_still_asks(client, employer, worker):
    """A chat of a job tomorrow is writable, so it polls too (R13).

    1. Save Ivan's accepted application of a job tomorrow
    2. Open the chat as Ivan
    3. Expect: the polling attribute
    """
    tomorrow = apply(employer, worker, date=TODAY + DAY)
    client.force_login(worker)

    response = client.get(chat_url(tomorrow))

    assertContains(response, 'hx-trigger="every 4s"')
