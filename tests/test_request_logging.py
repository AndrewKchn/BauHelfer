"""Integration tests: one line per request in production, without personal data (#137).

The tests run with production's MIDDLEWARE, so the request log sits where it does on
Render. A line is "<METHOD> <path> <status> <ms>ms" (docs/specs/request-logging.md R2).
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.templatetags.static import static
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from tests.test_request_logging_setup import production  # noqa: F401 (a fixture)

pytestmark = [pytest.mark.django_db, pytest.mark.story(137)]

User = get_user_model()

RESET_PATTERN = "/accounts/reset/<uidb64>/<token>/"


@pytest.fixture(autouse=True)
def production_middleware(production, settings):  # noqa: F811 (the fixture above)
    """Run every request through production's middleware, the request log included."""
    settings.MIDDLEWARE = production.MIDDLEWARE


def request_lines(caplog):
    """The messages the request log wrote, without other loggers' records."""
    return [r.getMessage() for r in caplog.records if r.name == "config.middleware"]


def test_page_is_logged_with_method_path_status_and_time(client, caplog):
    """Opening a page writes one INFO line: method, path, status, time (R2, AC2).

    1. Open the home page
    2. Expect: one INFO record from config.middleware, "GET / 200 <n>ms"
    """
    client.get(reverse("home"))

    [record] = [r for r in caplog.records if r.name == "config.middleware"]
    assert record.levelname == "INFO"
    assert re.fullmatch(r"GET / 200 \d+ms", record.getMessage())


def test_post_with_redirect_is_logged_with_its_status(client, caplog):
    """A form sent with POST that redirects is logged with 302 (AC3).

    1. Send POST to the logout page (it redirects to the home page)
    2. Expect: the line starts with "POST /accounts/logout/ 302 "
    """
    client.post(reverse("logout"))

    [line] = request_lines(caplog)
    assert line.startswith(f"POST {reverse('logout')} 302 ")


def test_page_not_found_is_logged_with_404(client, caplog):
    """A path that matches no URL is logged with status 404 (AC4).

    1. Open /no-such-page/
    2. Expect: the line starts with "GET /no-such-page/ 404 "
    """
    client.get("/no-such-page/")

    [line] = request_lines(caplog)
    assert line.startswith("GET /no-such-page/ 404 ")


def test_query_string_is_not_logged(client, caplog):
    """The path is logged without the part after "?" (R3, AC5).

    1. Open /?q=secret-word
    2. Expect: the line starts with "GET / 200 "; "secret-word" is in no record
    """
    client.get("/?q=secret-word")

    [line] = request_lines(caplog)
    assert line.startswith("GET / 200 ")
    assert "secret-word" not in caplog.text


def test_password_reset_link_is_logged_without_uid_and_token(client, caplog):
    """The reset link from the email is logged as its URL pattern (R4, AC6).

    1. Create a user and the reset link Django would email to them
    2. Open the link; Django redirects to …/set-password/, follow it
    3. Expect: two lines, both with the pattern "/accounts/reset/<uidb64>/<token>/"
    4. Expect: neither the uid nor the token is in any record
    """
    user = User.objects.create_user(email="anna@example.com", password="Gerüst-2026")
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    client.get(
        reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token}),
        follow=True,
    )

    lines = request_lines(caplog)
    assert [line.split()[:3] for line in lines] == [
        ["GET", RESET_PATTERN, "302"],
        ["GET", RESET_PATTERN, "200"],
    ]
    assert token not in caplog.text
    assert uid not in caplog.text


def test_reset_link_is_hidden_when_a_middleware_answers_first(client, caplog):
    """The reset link stays hidden when a middleware redirects before the URL is matched.

    1. Log in as a user without a role
    2. Open a reset link: OnboardingMiddleware (#10) redirects to the role choice before
       Django matches the URL
    3. Expect: one line "GET /accounts/reset/<uidb64>/<token>/ 302 …"
    4. Expect: neither the uid nor the token is in any record
    """
    user = User.objects.create_user(email="ben@example.com", password="Gerüst-2026")
    client.force_login(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    client.get(
        reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
    )

    [line] = request_lines(caplog)
    assert line.startswith(f"GET {RESET_PATTERN} 302 ")
    assert token not in caplog.text
    assert uid not in caplog.text


def test_render_health_check_is_not_logged(client, caplog):
    """Render's health check gets the page but writes no line (R5, D4, AC7).

    1. Open the home page with User-Agent "Render/1.0"
    2. Expect: status 200, no record from config.middleware
    """
    response = client.get(reverse("home"), headers={"user-agent": "Render/1.0"})

    assert response.status_code == 200
    assert request_lines(caplog) == []


def test_user_agent_and_referer_are_not_logged(client, caplog):
    """The browser's User-Agent and the Referer reach no record (AC8).

    1. Open the home page with a browser User-Agent and a Referer
    2. Expect: one line; neither header value is in any record
    """
    client.get(
        reverse("home"),
        headers={
            "user-agent": "Mozilla/5.0 TestBrowser/1.0",
            "referer": "https://example.com/came-from-here/",
        },
    )

    assert len(request_lines(caplog)) == 1
    assert "TestBrowser" not in caplog.text
    assert "came-from-here" not in caplog.text


def test_static_file_is_not_logged(client, caplog):
    """WhiteNoise answers static files before the request log sees them (R6, AC10).

    1. Fetch htmx.min.js the way the browser does
    2. Expect: status 200, no record from config.middleware
    """
    response = client.get(static("js/htmx.min.js"))

    assert response.status_code == 200
    assert request_lines(caplog) == []
