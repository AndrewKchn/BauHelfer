"""Calls every function in ci_gate_demo, so test coverage stays above 80%."""

import ci_gate_demo


def test_all_functions_are_called():
    """Each function returns its own number."""
    functions = [getattr(ci_gate_demo, f"no_docstring_{i}") for i in range(1, 9)]
    assert [f() for f in functions] == list(range(1, 9))
