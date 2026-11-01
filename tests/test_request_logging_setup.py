"""Unit tests: gunicorn's arguments on Render and where the request log is switched on (#137).

Render starts gunicorn with its own GUNICORN_CMD_ARGS unless render.yaml sets them; its
default writes an access log with the User-Agent, the Referer and every full path
(docs/specs/request-logging.md).
"""

import importlib
import re
import shlex

import pytest
from django.conf import settings
from gunicorn.config import Config

from tests.test_deploy import PRODUCTION_ENV

pytestmark = pytest.mark.story(137)

REQUEST_LOG = "config.middleware.RequestLogMiddleware"
WHITENOISE = "whitenoise.middleware.WhiteNoiseMiddleware"


@pytest.fixture
def production(monkeypatch):
    """production.py loaded fresh, with the variables Render sets (photos #64, email #27)."""
    for name, value in PRODUCTION_ENV.items():
        monkeypatch.setenv(name, value)
    from config.settings import production

    return importlib.reload(production)


def gunicorn_args_from_render_yaml():
    """The value of GUNICORN_CMD_ARGS in render.yaml, parsed as gunicorn parses it."""
    text = (settings.BASE_DIR / "render.yaml").read_text()
    match = re.search(r"- key: GUNICORN_CMD_ARGS\n\s+value: ([^#\n]+)", text)
    assert match, "render.yaml does not set GUNICORN_CMD_ARGS"
    return Config().parser().parse_args(shlex.split(match.group(1)))


def test_render_starts_gunicorn_without_an_access_log():
    """render.yaml sets gunicorn's arguments: no access log, Render's port (R1, AC1).

    1. Read GUNICORN_CMD_ARGS from render.yaml
    2. Parse it with gunicorn's own argument parser
    3. Expect: no access log file, bind to 0.0.0.0:10000, the app preloaded
    """
    args = gunicorn_args_from_render_yaml()

    assert args.accesslog is None
    assert args.bind == ["0.0.0.0:10000"]
    assert args.preload_app is True


def test_production_logs_requests_right_after_whitenoise(production):
    """The request log is the middleware right after WhiteNoise in production (R6, AC9).

    1. Load production.py
    2. Expect: RequestLogMiddleware comes right after WhiteNoise, so static files skip it
    """
    middleware = production.MIDDLEWARE

    assert middleware[middleware.index(WHITENOISE) + 1] == REQUEST_LOG


def test_local_settings_do_not_log_requests():
    """Locally runserver prints its own request lines; ours would repeat them (D6, AC9).

    1. Read the settings the tests run with (local.py)
    2. Expect: RequestLogMiddleware is not in MIDDLEWARE
    """
    assert REQUEST_LOG not in settings.MIDDLEWARE


def test_request_lines_are_logged_at_info(production):
    """The middleware's logger lets INFO through in production (R7).

    1. Load production.py
    2. Expect: the "config" logger has level INFO
    """
    assert production.LOGGING["loggers"]["config"]["level"] == "INFO"
