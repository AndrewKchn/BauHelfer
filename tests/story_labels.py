"""Pytest plugin: groups the Allure report by story, the GitHub issue a test belongs to (#89).

A test file says only which issue its tests belong to: pytest.mark.story(9) in pytestmark.
When pytest collects the tests, this plugin adds the Allure labels: the issue title (story),
its milestone (epic) and a link to it. The first docstring line becomes the test title in
the report, the steps below it become the description.

Tabs in the report: Behaviors = milestone -> story; Suites = level -> story. The level is
the start of the test file's docstring: "Unit tests:", "Integration tests:" or "E2E tests:".

Issue titles come from stories.json, written in CI before the tests run:
    gh issue list --state all --limit 300 --json number,title,milestone > stories.json
Tests never call GitHub themselves. Without the file (local run) the story is just "#9".

Loaded for every test run by the root conftest.py.
"""

import inspect
import json
import os
from pathlib import Path

import pytest

REPO_URL = "https://github.com/AndrewKchn/BauHelfer"
LEVELS = ("Unit", "Integration", "E2E")
STORIES_FILE = Path(__file__).resolve().parent.parent / "stories.json"


def split_docstring(doc):
    """Split a docstring into its first line (the title) and the rest (the steps)."""
    text = inspect.cleandoc(doc or "")
    title, _, rest = text.partition("\n")
    return title.strip(), rest.strip()


def level_of(module_doc):
    """The test level from a file docstring like "Unit tests: ..."; "" if there is none."""
    for level in LEVELS:
        if (module_doc or "").startswith(f"{level} tests:"):
            return level
    return ""


def load_stories(path):
    """Read the `gh issue list` output: {number: {"title", "milestone"}}."""
    path = Path(path)
    if not path.exists():
        return {}
    stories = {}
    for issue in json.loads(path.read_text()):
        stories[issue["number"]] = {
            "title": issue["title"],
            "milestone": (issue.get("milestone") or {}).get("title", ""),
        }
    return stories


def labels_for(number, stories):
    """The Allure labels for a story number; only "#N" when there is no data for it."""
    story = stories.get(number, {})
    title = story.get("title", "")
    return {
        "story": f"#{number} {title}" if title else f"#{number}",
        "epic": story.get("milestone", ""),
        "issue_url": f"{REPO_URL}/issues/{number}",
        "issue_name": f"#{number}",
    }


def pytest_configure(config):
    """Register the story marker, also for runs outside this project (pytester)."""
    config.addinivalue_line(
        "markers", "story(number): the GitHub issue (story) the test belongs to"
    )


def pytest_collection_modifyitems(config, items):
    """Add the Allure labels to every test; stop the run if a test has no story or docstring."""
    stories = load_stories(os.environ.get("STORIES_FILE", STORIES_FILE))
    problems = []
    for item in items:
        # The marker on the test itself, else the one from the file's pytestmark.
        marker = item.get_closest_marker("story")
        function = getattr(item, "function", None)
        title, description = split_docstring(getattr(function, "__doc__", None))
        if marker is None:
            problems.append(f"{item.nodeid}: no story, add pytest.mark.story(N)")
        level = level_of(getattr(item.module, "__doc__", None))
        if not level:
            problems.append(
                f"{item.nodeid}: the file docstring must start with "
                '"Unit tests:", "Integration tests:" or "E2E tests:"'
            )
        if not title:
            problems.append(
                f"{item.nodeid}: no docstring, add one (short line + steps)"
            )
        if marker is None or not title or not level:
            continue

        labels = labels_for(marker.args[0], stories)
        item.add_marker(pytest.mark.allure_label(labels["story"], label_type="story"))
        if labels["epic"]:
            item.add_marker(pytest.mark.allure_label(labels["epic"], label_type="epic"))
        # Replace the file-based suites of allure-pytest: level -> story in the Suites tab.
        item.add_marker(pytest.mark.allure_label(level, label_type="parentSuite"))
        item.add_marker(pytest.mark.allure_label(labels["story"], label_type="suite"))
        # "link", not "issue": Allure draws issue links as bugs, ours point to a story.
        item.add_marker(
            pytest.mark.allure_link(
                labels["issue_url"], name=labels["issue_name"], link_type="link"
            )
        )
        if description:
            item.add_marker(pytest.mark.allure_description(description))
        function.__allure_display_name__ = title  # the name Allure shows for the test

    if problems:
        raise pytest.UsageError(
            "Every test needs a story and a docstring (#89):\n  "
            + "\n  ".join(problems)
        )
