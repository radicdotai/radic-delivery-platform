"""Small, deterministic regex parsers for test-tool output (research.md D2).

Deliberately not a general-purpose parser: each function targets one tool's
own stable, default terminal summary format. Documented, accepted trade-off:
more brittle to an output-format change than a structured report would be
(research.md D2's "Risk accepted and documented").
"""

from __future__ import annotations

import re

from radic_delivery.gate.result import CoverageResult, TestRunResult

_PASSED_RE = re.compile(r"(\d+)\s+passed")
_FAILED_RE = re.compile(r"(\d+)\s+failed")
_SKIPPED_RE = re.compile(r"(\d+)\s+skipped")

_PYTEST_COV_TOTAL_RE = re.compile(r"^TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", re.MULTILINE)

# vitest --coverage summary table, e.g.:
# % Lines    87.5 | % Stmts    87.5 | % Branch    75 | % Funcs   100
_VITEST_LINES_RE = re.compile(r"%\s*Lines\s+(\d+(?:\.\d+)?)")
_VITEST_STMTS_RE = re.compile(r"%\s*Stmts\s+(\d+(?:\.\d+)?)")
_VITEST_BRANCH_RE = re.compile(r"%\s*Branch\s+(\d+(?:\.\d+)?)")
_VITEST_FUNCS_RE = re.compile(r"%\s*Funcs\s+(\d+(?:\.\d+)?)")


def parse_test_run(runner: str, stdout: str) -> TestRunResult:
    """Parse a pytest or vitest terminal summary into pass/fail/skip counts.

    Both tools' default summaries contain the words "passed"/"failed"/
    "skipped" next to a count; counts are extracted independently of each
    other's position so word order doesn't matter.
    """
    del runner  # pytest and vitest's summary wording is close enough to share one parser
    passed_match = _PASSED_RE.search(stdout)
    failed_match = _FAILED_RE.search(stdout)
    skipped_match = _SKIPPED_RE.search(stdout)
    return TestRunResult(
        passed=int(passed_match.group(1)) if passed_match else 0,
        failed=int(failed_match.group(1)) if failed_match else 0,
        skipped=int(skipped_match.group(1)) if skipped_match else 0,
    )


def parse_coverage(runner: str, stdout: str) -> CoverageResult | None:
    """Parse pytest-cov's TOTAL line or vitest --coverage's summary table.

    Returns None if no recognisable coverage summary is present in stdout
    (the gate then reports coverage as not measurable rather than guessing).
    """
    if runner == "pytest":
        match = _PYTEST_COV_TOTAL_RE.search(stdout)
        if match is None:
            return None
        return CoverageResult(global_=float(match.group(1)))

    if runner == "vitest":
        lines = _VITEST_LINES_RE.search(stdout)
        stmts = _VITEST_STMTS_RE.search(stdout)
        branch = _VITEST_BRANCH_RE.search(stdout)
        funcs = _VITEST_FUNCS_RE.search(stdout)
        if not (lines and stmts and branch and funcs):
            return None
        return CoverageResult(
            lines=float(lines.group(1)),
            statements=float(stmts.group(1)),
            branches=float(branch.group(1)),
            functions=float(funcs.group(1)),
        )

    return None
