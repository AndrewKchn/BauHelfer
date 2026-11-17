"""Fixtures for every test in chat/tests/ (#35): pytest finds this file by its name.

test_models.py defines its own employer and worker; a fixture in a test file wins over one
here.
"""

import pytest
from django.utils import timezone

from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer

from .helpers import NOW, apply


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    """Fix the clock at NOW, so the test does not depend on when it runs."""
    monkeypatch.setattr(timezone, "now", lambda: NOW)


@pytest.fixture
def employer():
    """Anna Huber, the employer of the job."""
    return make_employer("anna@example.com", name="Anna Huber")


@pytest.fixture
def worker():
    """Ivan Petrenko, the worker."""
    user = make_worker("ivan@example.com")
    user.name = "Ivan Petrenko"
    user.save()
    return user


@pytest.fixture
def application(employer, worker):
    """Ivan's accepted application to Anna's job today."""
    return apply(employer, worker)
