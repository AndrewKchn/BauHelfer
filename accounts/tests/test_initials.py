"""Unit tests: the avatar initials of a user (#23).

Spec: docs/specs/applications-list.md, iteration 2 (R11, D13), acceptance criterion AC11.
No database: User(...) is only built in memory, never saved.
"""

import pytest

from accounts.models import User

pytestmark = pytest.mark.story(23)


@pytest.mark.parametrize(
    ("name", "initials"),
    [
        ("Andrii Petrenko", "AP"),
        ("Maria del Carmen García López", "ML"),
        ("Mehmet", "M"),
        ("Іван Петренко", "ІП"),
        ("  ion   popescu ", "IP"),
        ("", ""),
    ],
    ids=["two-words", "five-words", "one-word", "cyrillic", "spaces-small", "empty"],
)
def test_initials_take_the_first_and_the_last_word(name, initials):
    """The avatar shows the first letters of the first and the last word (spec D13).

    1. Build a user with the name
    2. Call initials()
    3. Expect: two capital letters, one for a one-word name, none for an empty name
    """
    assert User(name=name).initials() == initials
