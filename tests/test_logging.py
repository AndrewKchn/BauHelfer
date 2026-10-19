"""Unit tests: the LOGGING setting that sends our events and Django's errors to stdout (#124).

Render shows everything the server prints to stdout in its Logs tab, so the console is the
only place logs need to go.
"""

import importlib
import logging

import pytest
from django.conf import settings
from django.test import override_settings
from django.utils.log import configure_logging

from tests.test_deploy import MEDIA_ENV

pytestmark = pytest.mark.story(124)


@pytest.fixture
def production(monkeypatch):
    """production.py loaded fresh, with the photo storage variables Render sets (#64)."""
    for name, value in MEDIA_ENV.items():
        monkeypatch.setenv(name, value)
    from config.settings import production

    return importlib.reload(production)


@pytest.fixture
def apply_logging():
    """Apply a LOGGING dict as Django does at startup; put the test settings back after.

    configure_logging applies Django's DEFAULT_LOGGING first, then ours on top of it.
    """
    yield lambda config: configure_logging(settings.LOGGING_CONFIG, config)
    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)


def test_production_logs_app_events_at_info(production):
    """On the live server our apps log INFO and up, not DEBUG.

    1. Load production.py
    2. Expect: the "accounts" and "jobs" loggers have level INFO
    """
    loggers = production.LOGGING["loggers"]

    assert loggers["accounts"]["level"] == "INFO"
    assert loggers["jobs"]["level"] == "INFO"


def test_local_logs_app_events_at_debug():
    """On a developer's machine our apps log everything, DEBUG included.

    1. Read the settings the tests run with (local.py)
    2. Expect: the "accounts" and "jobs" loggers have level DEBUG
    """
    loggers = settings.LOGGING["loggers"]

    assert loggers["accounts"]["level"] == "DEBUG"
    assert loggers["jobs"]["level"] == "DEBUG"


def test_local_settings_do_not_change_the_production_levels(production):
    """local.py makes its own LOGGING instead of editing the dict it shares with base.py.

    1. Load local.py, then production.py, in one process (as the tests do)
    2. Expect: production still logs at INFO
    """
    from config.settings import local

    importlib.reload(local)
    production = importlib.reload(production)

    assert production.LOGGING["loggers"]["accounts"]["level"] == "INFO"


@pytest.mark.parametrize("name", ["accounts.views", "jobs.views"])
def test_app_event_is_printed_to_stdout(production, apply_logging, capsys, name):
    """An INFO event of our apps reaches stdout in production, in the agreed format.

    1. Apply production's LOGGING
    2. Log "Job created: job_id=1" at INFO from a module of the app
    3. Expect: stdout shows "INFO <module> Job created: job_id=1"
    """
    apply_logging(production.LOGGING)

    logging.getLogger(name).info("Job created: job_id=%s", 1)

    assert f"INFO {name} Job created: job_id=1" in capsys.readouterr().out


def test_server_error_is_printed_to_stdout_with_debug_off(
    production, apply_logging, capsys
):
    """A 500 error reaches Render's logs: Django's default prints it only with DEBUG on.

    1. Apply production's LOGGING (DEBUG is off there)
    2. Log an error the way Django does for a crashed view
    3. Expect: stdout shows it at ERROR
    """
    assert production.DEBUG is False
    apply_logging(production.LOGGING)

    logging.getLogger("django.request").error("Internal Server Error: /jobs/")

    assert "ERROR django.request Internal Server Error: /jobs/" in (
        capsys.readouterr().out
    )


def test_server_error_is_printed_once_with_debug_on(apply_logging, capfd):
    """With DEBUG on, an error is printed once, not by Django's default handler as well.

    1. Apply local LOGGING (on top of Django's default, as at startup)
    2. With DEBUG on, log an error the way Django does for a crashed view
    3. Expect: the line appears once in stdout and stderr together
    """
    apply_logging(settings.LOGGING)

    with override_settings(DEBUG=True):  # Django's default prints only with DEBUG on
        logging.getLogger("django.request").error("Internal Server Error: /jobs/")

    out, err = capfd.readouterr()
    assert (out + err).count("Internal Server Error: /jobs/") == 1
