"""Unit tests: turning a test's story number and docstring into Allure labels (#89)."""

import json

import pytest

from tests.story_labels import labels_for, load_stories, split_docstring

pytestmark = pytest.mark.story(89)

STORIES = {
    9: {
        "title": "Registration, login, logout, password reset",
        "milestone": "M2 · Accounts & Profiles",
        "labels": ["backend", "frontend"],
    }
}


def test_split_docstring_into_title_and_steps():
    """The first line becomes the title, the rest becomes the description.

    1. Take a docstring with a short line, an empty line and numbered steps
    2. Expect: the title is the short line, the description holds only the steps
    """
    doc = """Wrong password: the user sees an error.

    1. An account exists
    2. Expect: an error box
    """

    title, description = split_docstring(doc)

    assert title == "Wrong password: the user sees an error."
    assert description == "1. An account exists\n2. Expect: an error box"


def test_split_docstring_with_only_a_title():
    """A one-line docstring gives a title and no description.

    1. Take a docstring with one line
    2. Expect: that line as the title, an empty description
    """
    assert split_docstring("Signup stores the email in lowercase.") == (
        "Signup stores the email in lowercase.",
        "",
    )


@pytest.mark.parametrize("doc", [None, "", "   \n  "])
def test_split_docstring_without_text(doc):
    """No docstring means no title: the hook reports it as a problem.

    1. Take a missing, empty or blank docstring
    2. Expect: an empty title and an empty description
    """
    assert split_docstring(doc) == ("", "")


def test_load_stories_from_gh_issue_list_output(tmp_path):
    """Reads the file that `gh issue list --json number,title,milestone,labels` writes.

    1. Write a file in the format of the gh command
    2. Expect: a dict by issue number with title, milestone and label names
    """
    path = tmp_path / "stories.json"
    path.write_text(
        json.dumps(
            [
                {
                    "number": 9,
                    "title": "Registration, login, logout, password reset",
                    "milestone": {"title": "M2 · Accounts & Profiles"},
                    "labels": [{"name": "backend"}, {"name": "frontend"}],
                },
                {"number": 52, "title": "Real crews", "milestone": None, "labels": []},
            ]
        )
    )

    stories = load_stories(path)

    assert stories[9] == STORIES[9]
    assert stories[52] == {"title": "Real crews", "milestone": "", "labels": []}


def test_load_stories_without_the_file_gives_nothing(tmp_path):
    """A local run without `gh` has no stories.json; tests must still run.

    1. Point to a file that does not exist
    2. Expect: an empty dict, no error
    """
    assert load_stories(tmp_path / "missing.json") == {}


def test_labels_for_a_known_story():
    """A known story gets its title, milestone as epic and labels as features.

    1. Ask for the labels of story 9
    2. Expect: story "#9 <title>", epic = milestone, features = issue labels
    3. Expect: a link to the GitHub issue named "#9"
    """
    labels = labels_for(9, STORIES)

    assert labels["story"] == "#9 Registration, login, logout, password reset"
    assert labels["epic"] == "M2 · Accounts & Profiles"
    assert labels["features"] == ["backend", "frontend"]
    assert labels["issue_url"] == "https://github.com/AndrewKchn/BauHelfer/issues/9"
    assert labels["issue_name"] == "#9"


def test_labels_for_an_unknown_story_fall_back_to_the_number():
    """Without data from GitHub the report still groups by "#N".

    1. Ask for the labels of a story that is not in the data
    2. Expect: story "#77", no epic, no features, the issue link still works
    """
    labels = labels_for(77, STORIES)

    assert labels["story"] == "#77"
    assert labels["epic"] == ""
    assert labels["features"] == []
    assert labels["issue_url"] == "https://github.com/AndrewKchn/BauHelfer/issues/77"
