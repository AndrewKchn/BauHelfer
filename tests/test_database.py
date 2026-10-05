"""Integration tests: development and tests use the same database as production (#2)."""

import pytest
from django.db import connection

pytestmark = [pytest.mark.django_db, pytest.mark.story(2)]


def test_database_is_postgresql():
    """Development and tests run on PostgreSQL, like production.

    1. Check the database connection
    2. Expect: PostgreSQL
    """
    assert connection.vendor == "postgresql"


def test_postgresql_major_version_matches_production():
    """The local PostgreSQL has the same major version as production.

    1. Read the database server version
    2. Expect: major version 17
    """
    # pg_version is e.g. 170006 for 17.6; production (Supabase) runs PostgreSQL 17.
    assert connection.pg_version // 10000 == 17
