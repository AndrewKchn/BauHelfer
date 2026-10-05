"""Pytest setup shared by all tests in the project."""

pytest_plugins = [
    "pytester",  # runs pytest inside a test, used by tests/test_story_labels_plugin.py
    "tests.story_labels",  # Allure labels by story + every test needs a story and docstring
]
