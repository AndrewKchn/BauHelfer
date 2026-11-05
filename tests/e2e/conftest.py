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
def browser_type_launch_args(browser_type_launch_args):
    """Chromium with its scrollbars shown, as on a Windows or Linux laptop (#28).

    Replaces pytest-playwright's fixture of the same name and extends its value.
    Playwright starts a headless Chromium with --hide-scrollbars. A scrollbar takes width
    from the page; a page that comes and goes with it made the status tabs stop 15 px off
    their group, and only a visible scrollbar shows that in CI.
    """
    return {**browser_type_launch_args, "ignore_default_args": ["--hide-scrollbars"]}


@pytest.fixture(scope="session")
def base_url(live_server):
    """Make page.goto("/accounts/login/") open the live server, not a fixed address."""
    return live_server.url
