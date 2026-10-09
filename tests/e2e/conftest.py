"""Pytest setup for the E2E tests: a real browser (Playwright) against a real server (#14).

pytest-django's live_server starts the whole site on a free port in a background thread of
the test process, with the test database. Playwright's `page` opens Chromium against it.
"""

import os

import pytest

# Playwright's sync API runs an asyncio event loop in the test thread. Django sees it and
# refuses database calls from the test ("SynchronousOnlyOperation"), a guard for real async
# code. Our tests are plain sync code, so the guard is off, only in this test process: the
# site itself never reads this file. Set at import, before the test database is created.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture(scope="session")
def base_url(live_server):
    """Make page.goto("/accounts/login/") open the live server, not a fixed address."""
    return live_server.url
