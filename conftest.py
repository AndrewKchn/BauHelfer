"""Pytest setup shared by all tests in the project."""

import pytest

pytest_plugins = [
    "pytester",  # runs pytest inside a test, used by tests/test_story_labels_plugin.py
    "tests.story_labels",  # Allure labels by story + every test needs a story and docstring
]


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """Hash test passwords with one MD5 round instead of a million PBKDF2 rounds (#14).

    The real hasher is slow on purpose (~0.7 s per password) to make stolen hashes hard to
    guess; every create_user and login in a test paid that. Test passwords protect nothing.
    `settings` puts the real value back after each test; the site never reads this file.
    tests/test_deploy.py checks that production still uses PBKDF2.
    """
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def in_memory_file_storage(settings):
    """Keep uploaded files in memory: no test writes to media/ or reaches the network (#64).

    Only "default" (uploads) is replaced; "staticfiles" stays, so CSS and JS still work.
    Changing the setting makes Django drop its cached storage, so default_storage and every
    FileField use the new one; each test starts with an empty store.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    }
