def test_ci_turns_red():
    """Deliberately failing: proves a red check blocks the merge (#4). Never merge."""
    assert False
