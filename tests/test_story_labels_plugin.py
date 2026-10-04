"""Integration tests: the story plugin inside a real pytest run with Allure (#89).

Each test writes a small test file, runs pytest on it with the plugin (pytester) and reads
the result files that Allure writes, the same way the report is built in CI.
"""

import json

import pytest

pytestmark = pytest.mark.story(89)

PLUGIN = "tests.story_labels"

STORIES_JSON = [
    {
        "number": 9,
        "title": "Registration, login, logout, password reset",
        "milestone": {"title": "M2 · Accounts & Profiles"},
        "labels": [{"name": "backend"}, {"name": "frontend"}],
    }
]

TAGGED_TEST_FILE = '''
import pytest

pytestmark = pytest.mark.story(9)


def test_wrong_password():
    """Wrong password: the user sees an error and stays logged out.

    1. An account exists
    2. Expect: an error box
    """


@pytest.mark.story(13)
def test_work_permit():
    """Signup is refused without the work permit checkbox."""
'''


@pytest.fixture
def run_with_allure(pytester, monkeypatch):
    """Run pytest with the plugin on the given test file; return the Allure results by test."""

    def run(test_file, stories=STORIES_JSON):
        stories_path = pytester.path / "stories.json"
        stories_path.write_text(json.dumps(stories))
        monkeypatch.setenv("STORIES_FILE", str(stories_path))
        pytester.makepyfile(test_file)
        results_dir = pytester.path / "allure-results"
        outcome = pytester.runpytest("-p", PLUGIN, f"--alluredir={results_dir}")
        results = {}
        for path in results_dir.glob("*-result.json"):
            data = json.loads(path.read_text())
            results[data["fullName"].rsplit("#", 1)[-1]] = data
        return outcome, results

    return run


def labels(result, name):
    """All values of one Allure label type, e.g. every "feature" of a test."""
    return [label["value"] for label in result["labels"] if label["name"] == name]


def test_story_epic_and_features_come_from_github_data(run_with_allure):
    """A test tagged story(9) is grouped under #9 with its milestone and labels.

    1. A test file tagged story(9) for all its tests
    2. Run pytest with Allure
    3. Expect: story "#9 <title>", epic = milestone, features = issue labels
    """
    outcome, results = run_with_allure(TAGGED_TEST_FILE)

    outcome.assert_outcomes(passed=2)
    result = results["test_wrong_password"]
    assert labels(result, "story") == ["#9 Registration, login, logout, password reset"]
    assert labels(result, "epic") == ["M2 · Accounts & Profiles"]
    assert labels(result, "feature") == ["backend", "frontend"]


def test_docstring_gives_the_title_and_the_steps(run_with_allure):
    """The report shows the short line as the test name and the steps as its description.

    1. A tagged test with a docstring: short line + steps
    2. Run pytest with Allure
    3. Expect: name = short line, description = only the steps
    """
    _, results = run_with_allure(TAGGED_TEST_FILE)

    result = results["test_wrong_password"]
    assert (
        result["name"] == "Wrong password: the user sees an error and stays logged out."
    )
    assert result["description"] == "1. An account exists\n2. Expect: an error box"


def test_issue_link_points_to_github(run_with_allure):
    """Every test links to its GitHub issue.

    1. A test tagged story(9)
    2. Run pytest with Allure
    3. Expect: an issue link "#9" to the GitHub issue page
    """
    _, results = run_with_allure(TAGGED_TEST_FILE)

    links = results["test_wrong_password"]["links"]
    assert {
        "type": "issue",
        "name": "#9",
        "url": "https://github.com/AndrewKchn/BauHelfer/issues/9",
    } in links


def test_story_on_the_test_wins_over_the_file(run_with_allure):
    """A test from another ticket in a shared file keeps its own story.

    1. A file tagged story(9) with one test tagged story(13)
    2. Run pytest with Allure (no GitHub data for #13)
    3. Expect: that test is under "#13", the others under #9
    """
    _, results = run_with_allure(TAGGED_TEST_FILE)

    assert labels(results["test_work_permit"], "story") == ["#13"]


def test_test_without_docstring_stops_the_run(run_with_allure):
    """A test without a description is not allowed into the report.

    1. A tagged test without a docstring
    2. Run pytest
    3. Expect: the run stops before any test, the error names the test
    """
    outcome, _ = run_with_allure(
        "import pytest\n\npytestmark = pytest.mark.story(9)\n\ndef test_bare():\n    pass\n"
    )

    assert outcome.ret != 0
    outcome.assert_outcomes()
    assert "test_bare" in outcome.stdout.str() + outcome.stderr.str()
    assert "docstring" in outcome.stdout.str() + outcome.stderr.str()


def test_test_without_story_stops_the_run(run_with_allure):
    """A test that belongs to no story is not allowed into the report.

    1. A test with a docstring but without story(N)
    2. Run pytest
    3. Expect: the run stops before any test, the error names the test
    """
    outcome, _ = run_with_allure('def test_lonely():\n    """Has a docstring."""\n')

    assert outcome.ret != 0
    outcome.assert_outcomes()
    assert "test_lonely" in outcome.stdout.str() + outcome.stderr.str()
    assert "story" in outcome.stdout.str() + outcome.stderr.str()
