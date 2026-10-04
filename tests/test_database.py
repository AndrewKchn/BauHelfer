"""Checks that development and tests run on the same database as production (#2)."""

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


def test_database_is_postgresql():
    assert connection.vendor == "postgresql"


def test_postgresql_major_version_matches_production():
    # pg_version is e.g. 170006 for 17.6; production (Supabase) runs PostgreSQL 17.
    assert connection.pg_version // 10000 == 17
