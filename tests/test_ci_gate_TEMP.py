"""TEMPORARY — proves CI fails on a failing backend test. Remove before merge."""


def test_ci_gate_should_fail() -> None:
    assert 1 == 2, "intentional failure to prove the backend-tests CI gate works"
