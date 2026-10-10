"""Unit tests: every model change has a migration in the repo (#15)."""

import pytest
from django.core.management import call_command

pytestmark = [pytest.mark.django_db, pytest.mark.story(15)]


def test_no_missing_migrations():
    """The models and the migrations in the repo match.

    1. Run makemigrations --check --dry-run for all apps
    2. Expect: no changes found (the command exits without an error)
    """
    # --check exits with an error when a model changed without a migration;
    # --dry-run makes sure no file is written during the test.
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
