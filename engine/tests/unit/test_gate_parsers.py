"""Parser tests against captured sample tool output (no subprocess invoked)."""

from __future__ import annotations

from radic_delivery.gate.parsers import parse_coverage, parse_test_run


def test_parse_test_run_all_passed() -> None:
    stdout = "..                                                      [100%]\n\n2 passed in 0.02s\n"
    result = parse_test_run("pytest", stdout)
    assert result.passed == 2
    assert result.failed == 0
    assert result.skipped == 0


def test_parse_test_run_with_failure() -> None:
    result = parse_test_run("pytest", "1 failed, 1 passed in 0.03s\n")
    assert result.passed == 1
    assert result.failed == 1
    assert result.skipped == 0


def test_parse_test_run_with_skip() -> None:
    result = parse_test_run("pytest", "2 passed, 1 skipped in 0.02s\n")
    assert result.passed == 2
    assert result.skipped == 1


def test_parse_coverage_pytest_total_line() -> None:
    stdout = (
        "---------- coverage: platform darwin, python 3.11.0-final-0 ----------\n"
        "Name                     Stmts   Miss  Cover\n"
        "--------------------------------------------\n"
        "src/sample/__init__.py       5      0   100%\n"
        "--------------------------------------------\n"
        "TOTAL                       10      0   100%\n"
    )
    result = parse_coverage("pytest", stdout)
    assert result is not None
    assert result.global_ == 100.0


def test_parse_coverage_pytest_total_line_with_decimal() -> None:
    stdout = "TOTAL                       16      5    69%\n"
    result = parse_coverage("pytest", stdout)
    assert result is not None
    assert result.global_ == 69.0


def test_parse_coverage_missing_total_line_returns_none() -> None:
    assert parse_coverage("pytest", "no coverage summary here\n") is None


def test_parse_coverage_vitest_summary_table() -> None:
    stdout = "% Lines    87.5 | % Stmts    87.5 | % Branch    75 | % Funcs   100\n"
    result = parse_coverage("vitest", stdout)
    assert result is not None
    assert result.lines == 87.5
    assert result.statements == 87.5
    assert result.branches == 75.0
    assert result.functions == 100.0
