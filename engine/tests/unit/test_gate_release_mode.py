"""Tests for `gate evaluate --mode release-gate`: reuses ci-gate's real
checks unchanged, plus the new stage_regression check against a local
test-result record (research.md D1/D2). Fake runner — no real subprocess,
matching test_gate_evaluator.py's own pattern; real fixture repos are
reserved for the CLI-level tests in test_quality_gate_completion_cli.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from radic_delivery.gate.commands import ToolInvocation
from radic_delivery.gate.evaluator import evaluate
from radic_delivery.gate.result import GateResult
from radic_delivery.gate.runner import RunOutcome

_DIGEST = "sha256:" + "3" * 64


def _descriptor() -> dict[str, object]:
    return {
        "service": {"name": "sample"},
        "quality": {
            "lint": {"tool": "ruff"},
            "typecheck": {"tool": "mypy", "blocking": True},
            "unit": {"runner": "pytest"},
            "coverage_floor": {"global": 90},
        },
    }


def _ok(_inv: ToolInvocation, _cwd: Path) -> RunOutcome:
    return RunOutcome(launched=True, exit_code=0, stdout="TOTAL 10 0 100%\n2 passed in 0.01s\n", stderr="")


def _run_fn(inv: ToolInvocation, cwd: Path) -> RunOutcome:
    return _ok(inv, cwd)


def _run_release_gate(results_dir: Path | None, digest: str | None, **kwargs: Any) -> GateResult:
    return evaluate(
        _descriptor(),
        mode="release-gate",
        run_mutation=False,
        repo_root=Path("."),
        run_fn=_run_fn,
        results_dir=results_dir,
        digest=digest,
        **kwargs,
    )


def _write_stage_record(path: Path, **overrides: Any) -> None:
    record = {
        "environment": "stage",
        "digest": _DIGEST,
        "scope": "full",
        "result": "pass",
        "counts": {"total": 10, "passed": 10, "failed": 0, "skipped": 0, "quarantined": 0},
    }
    record.update(overrides)
    path.write_text(json.dumps(record))


def test_matching_passing_record_passes_the_gate(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json")

    result = _run_release_gate(results_dir, _DIGEST)

    assert result.overall == "pass"
    assert {c.name for c in result.checks} == {
        "lint", "typecheck", "unit", "coverage", "skip_budget", "stage_regression",
    }
    stage_check = next(c for c in result.checks if c.name == "stage_regression")
    assert stage_check.status == "pass"


def test_missing_record_fails_the_gate_naming_stage_regression(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    result = _run_release_gate(results_dir, _DIGEST)

    assert result.overall == "fail"
    stage_check = next(c for c in result.checks if c.name == "stage_regression")
    assert stage_check.status == "fail"
    assert _DIGEST in stage_check.detail
    other_checks = [c for c in result.checks if c.name != "stage_regression"]
    assert all(c.status == "pass" for c in other_checks)


def test_failing_stage_result_fails_the_check(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json", result="fail")

    result = _run_release_gate(results_dir, _DIGEST)

    stage_check = next(c for c in result.checks if c.name == "stage_regression")
    assert stage_check.status == "fail"


def test_skipped_tests_in_stage_record_fails_the_check(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(
        results_dir / "stage-sample-e2e.json",
        counts={"total": 10, "passed": 9, "failed": 0, "skipped": 1, "quarantined": 0},
    )

    result = _run_release_gate(results_dir, _DIGEST)

    stage_check = next(c for c in result.checks if c.name == "stage_regression")
    assert stage_check.status == "fail"


def test_wrong_scope_fails_the_check(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json", scope="regression")

    result = _run_release_gate(results_dir, _DIGEST)

    stage_check = next(c for c in result.checks if c.name == "stage_regression")
    assert stage_check.status == "fail"


def test_record_for_a_different_digest_is_treated_as_missing(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json", digest="sha256:" + "9" * 64)

    result = _run_release_gate(results_dir, _DIGEST)

    stage_check = next(c for c in result.checks if c.name == "stage_regression")
    assert stage_check.status == "fail"
    assert "no stage test-result record found" in stage_check.detail


def test_dev_environment_record_is_ignored(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "dev-sample-unit.json", environment="dev")

    result = _run_release_gate(results_dir, _DIGEST)

    stage_check = next(c for c in result.checks if c.name == "stage_regression")
    assert stage_check.status == "fail"


def test_missing_results_dir_and_digest_reports_not_executable() -> None:
    result = _run_release_gate(None, None)

    stage_check = next(c for c in result.checks if c.name == "stage_regression")
    assert stage_check.status == "not_executable"


def test_release_gate_reuses_ci_gate_checks_identically() -> None:
    """Confirms no duplicated/diverged logic (research.md D1): the same
    descriptor + run_fn produce identical lint/typecheck/unit/coverage/
    skip_budget results for both modes."""
    ci_gate_result = evaluate(
        _descriptor(), mode="ci-gate", run_mutation=False, repo_root=Path("."), run_fn=_run_fn
    )
    release_gate_result = evaluate(
        _descriptor(),
        mode="release-gate",
        run_mutation=False,
        repo_root=Path("."),
        run_fn=_run_fn,
        results_dir=None,
        digest=None,
    )

    shared_names = {"lint", "typecheck", "unit", "coverage", "skip_budget"}
    ci_checks = {c.name: c.status for c in ci_gate_result.checks if c.name in shared_names}
    release_checks = {c.name: c.status for c in release_gate_result.checks if c.name in shared_names}
    assert ci_checks == release_checks


# --- US3 (specs/019): Prereqs and Depends-on checks ---------------------------

REPO = "radicdotai/web-bff"


def _write_change_note(
    notes_dir: Path, sha: str, *, prereqs: list[dict] | None = None, depends_on: list[str] | None = None
) -> None:
    path = notes_dir / "change-notes" / REPO / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repo": REPO,
                "sha": sha,
                "type": "fix",
                "audience": "customer",
                "title": "A title",
                "summary": "...",
                "jira_key": "RAD-12",
                "prereqs": prereqs or [],
                "depends_on": depends_on or [],
            }
        )
    )


def _manifest(tickets: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "release_id": "2026.11.03-1",
        "kind": "release",
        "status": "proposed",
        "repo": REPO,
        "created_at": "2026-11-03T00:00:00Z",
        "initiator": "alice",
        "base": {"branch": "dev", "sha": "0" * 40},
        "selection": {"tickets": tickets, "held_back": [], "non_jira_prs": []},
    }


def test_omitting_manifest_adds_no_new_checks_no_regression(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json")

    result = _run_release_gate(results_dir, _DIGEST)

    assert {c.name for c in result.checks} == {
        "lint", "typecheck", "unit", "coverage", "skip_budget", "stage_regression",
    }
    assert result.overall == "pass"


def test_unticked_prereq_fails_naming_the_ticket_and_item(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json")
    notes_dir = tmp_path / "notes"
    sha = "1" * 40
    _write_change_note(notes_dir, sha, prereqs=[{"item": "flag created", "done": False}])
    manifest = _manifest([{"key": "RAD-12", "origin": "bot-proposal", "commits": [{"dev_sha": sha}]}])

    result = _run_release_gate(results_dir, _DIGEST, manifest=manifest, change_notes_dir=notes_dir)

    prereqs_check = next(c for c in result.checks if c.name == "prereqs")
    assert prereqs_check.status == "fail"
    assert "RAD-12" in prereqs_check.detail
    assert "flag created" in prereqs_check.detail
    assert result.overall == "fail"


def test_unmet_dependency_fails_naming_the_ticket_and_dependency(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json")
    notes_dir = tmp_path / "notes"
    sha = "1" * 40
    _write_change_note(notes_dir, sha, depends_on=["RAD-11"])
    manifest = _manifest([{"key": "RAD-12", "origin": "bot-proposal", "commits": [{"dev_sha": sha}]}])

    result = _run_release_gate(results_dir, _DIGEST, manifest=manifest, change_notes_dir=notes_dir)

    depends_on_check = next(c for c in result.checks if c.name == "depends_on")
    assert depends_on_check.status == "fail"
    assert "RAD-12" in depends_on_check.detail
    assert "RAD-11" in depends_on_check.detail
    assert result.overall == "fail"


def test_dependency_satisfied_via_known_prod_tickets_passes(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json")
    notes_dir = tmp_path / "notes"
    sha = "1" * 40
    _write_change_note(notes_dir, sha, depends_on=["RAD-11"])
    manifest = _manifest([{"key": "RAD-12", "origin": "bot-proposal", "commits": [{"dev_sha": sha}]}])

    result = _run_release_gate(
        results_dir, _DIGEST, manifest=manifest, change_notes_dir=notes_dir, known_prod_tickets=["RAD-11"]
    )

    depends_on_check = next(c for c in result.checks if c.name == "depends_on")
    assert depends_on_check.status == "pass"
    assert result.overall == "pass"


def test_fully_complete_prereqs_and_dependencies_pass_both_checks(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json")
    notes_dir = tmp_path / "notes"
    sha = "1" * 40
    _write_change_note(notes_dir, sha, prereqs=[{"item": "flag created", "done": True}])
    manifest = _manifest([{"key": "RAD-12", "origin": "bot-proposal", "commits": [{"dev_sha": sha}]}])

    result = _run_release_gate(results_dir, _DIGEST, manifest=manifest, change_notes_dir=notes_dir)

    assert next(c for c in result.checks if c.name == "prereqs").status == "pass"
    assert next(c for c in result.checks if c.name == "depends_on").status == "pass"
    assert result.overall == "pass"


def test_manifest_without_change_notes_dir_reports_not_executable(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_stage_record(results_dir / "stage-sample-e2e.json")
    manifest = _manifest([{"key": "RAD-12", "origin": "bot-proposal", "commits": [{"dev_sha": "1" * 40}]}])

    result = _run_release_gate(results_dir, _DIGEST, manifest=manifest, change_notes_dir=None)

    assert next(c for c in result.checks if c.name == "prereqs").status == "not_executable"
    assert next(c for c in result.checks if c.name == "depends_on").status == "not_executable"
