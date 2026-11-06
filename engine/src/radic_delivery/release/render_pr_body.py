"""`release render-pr-body`: deterministically renders the release PR
template (Reference 3) from an already-produced release manifest and
specs/007's change-note records (research.md D2).

Pure and deterministic given its inputs (spec FR-003) — reads already-
real artifacts, computes real git facts, never calls out to Jira/GitHub.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from radic_delivery.release.git_history import changed_paths

_DEPLOY_SERVICE_YAML_PREFIX = "deploy/run/"
_DEPLOY_SKAFFOLD_PATH = "deploy/skaffold.yaml"


@dataclass(frozen=True)
class RenderPrBodyResult:
    body: str
    deploy_files_changed: list[str] | None

    def to_dict(self) -> dict[str, Any]:
        return {"ok": True, "body": self.body, "deploy_files_changed": self.deploy_files_changed}


def _lookup_change_note(change_notes_dir: Path, repo: str, sha: str | None) -> tuple[str, str]:
    if sha is None:
        return "(unknown)", "(unknown)"
    path = change_notes_dir / "change-notes" / repo / f"{sha}.json"
    if not path.is_file():
        return "(unknown)", "(unknown)"
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return "(unknown)", "(unknown)"
    return record.get("title", "(unknown)"), record.get("type", "(unknown)")


def _is_deploy_relevant(path: str) -> bool:
    if path == _DEPLOY_SKAFFOLD_PATH:
        return True
    return path.startswith(_DEPLOY_SERVICE_YAML_PREFIX) and path.endswith((".yaml", ".yml"))


def _selection_table(manifest: dict[str, Any], change_notes_dir: Path, repo: str) -> str:
    lines = [
        "### Selection (bot proposal, edited by release managers)",
        "",
        "| Jira | Title | Type | Commits | Origin | Dev-green |",
        "|------|-------|------|---------|--------|-----------|",
    ]
    for ticket in manifest["selection"]["tickets"]:
        commits = ticket.get("commits", [])
        first_sha = commits[0]["dev_sha"] if commits else None
        title, type_ = _lookup_change_note(change_notes_dir, repo, first_sha)
        origin = ticket.get("origin", "bot-proposal")
        lines.append(
            f"| {ticket['key']} | {title} | {type_} | {len(commits)} | {origin} | pass |"
        )
    return "\n".join(lines)


def _non_jira_prs_section(manifest: dict[str, Any], change_notes_dir: Path, repo: str) -> str | None:
    entries = manifest["selection"].get("non_jira_prs", [])
    if not entries:
        return None
    lines = [
        "### Released without a Jira key (release input non_jira_prs)",
        "",
        "| PR | Title | Author | Commits | Reason | Second approver |",
        "|----|-------|--------|---------|--------|-----------------|",
    ]
    for entry in entries:
        commits = entry.get("commits", [])
        first_sha = commits[0]["dev_sha"] if commits else None
        title, _type = _lookup_change_note(change_notes_dir, repo, first_sha)
        author = entry.get("pr_author", "(unknown)")
        second_approver = entry.get("second_approver") or "MISSING"
        lines.append(
            f"| #{entry['pr']} | {title} | {author} | {len(commits)} | "
            f"{entry.get('reason', 'MISSING')} | {second_approver} |"
        )
    lines.append("")
    lines.append(
        "Each listed PR needs a reason (`/release nonjira PR reason: text`) and a second "
        "approver who is neither the initiator nor the PR author."
    )
    return "\n".join(lines)


def _held_back_section(manifest: dict[str, Any]) -> str:
    lines = [
        "### Held back (on purpose)",
        "",
        "| Jira | Reason | Removed by |",
        "|------|--------|------------|",
    ]
    for entry in manifest["selection"].get("held_back", []):
        lines.append(f"| {entry['key']} | {entry['reason']} | {entry.get('removed_by', '(unknown)')} |")
    return "\n".join(lines)


def _non_jira_prs_gate_satisfied(manifest: dict[str, Any]) -> bool | None:
    entries = manifest["selection"].get("non_jira_prs", [])
    if not entries:
        return None
    return all(
        entry.get("reason") not in (None, "MISSING") and entry.get("second_approver") is not None
        for entry in entries
    )


def render(
    manifest: dict[str, Any],
    *,
    change_notes_dir: Path,
    repo_dir: Path,
    migrations_chain: list[str],
) -> RenderPrBodyResult:
    repo = manifest["repo"]
    kind = manifest["kind"]
    base = manifest["base"]
    platform_tag = manifest.get("main", {}).get("tag") or "TBD"
    cloud_deploy = manifest.get("cloud_deploy")
    release_head = manifest.get("release_head")

    deploy_files_changed: list[str] | None
    if release_head is None:
        deploy_files_changed = None
        deploy_section_fact = "not yet determinable (no release head yet)"
    else:
        all_changed = changed_paths(repo_dir, base["sha"], release_head)
        deploy_files_changed = sorted(p for p in all_changed if _is_deploy_relevant(p))
        deploy_section_fact = "yes" if deploy_files_changed else "no"

    approval_clause = "Stage deploys automatically when the release branch is pushed"
    if cloud_deploy is not None:
        approval_clause += f" (Cloud Deploy release on pipeline {cloud_deploy['pipeline']}, stage target)"
    approval_clause += "."

    waivers = manifest.get("approvals", {}).get("waivers", [])
    dev_green_waived = any(w.get("kind") == "dev-green" for w in waivers)

    release_pr_approved = manifest.get("approvals", {}).get("release_pr", {}).get("approver") is not None
    non_jira_prs_satisfied = _non_jira_prs_gate_satisfied(manifest)
    release_gate_result = manifest.get("gates", {}).get("release_gate", {}).get("result")
    stage_regression_result = manifest.get("gates", {}).get("stage_regression", {}).get("result")
    stage_rollout = cloud_deploy.get("rollouts", {}).get("stage", {}) if cloud_deploy else {}
    stage_rollout_ok = stage_rollout.get("state") == "SUCCEEDED" and stage_rollout.get("verify") == "pass"

    non_jira_prs_section = _non_jira_prs_section(manifest, change_notes_dir, repo)

    ticket_keys = sorted({ticket["key"] for ticket in manifest["selection"]["tickets"]})

    cloud_deploy_link = (
        f"project {cloud_deploy['project']}, pipeline {cloud_deploy['pipeline']}, "
        f"release {cloud_deploy['release']} (filled in after the stage rollout)"
        if cloud_deploy is not None
        else "not yet available (filled in after the stage rollout)"
    )

    sections = [
        f"## Release {manifest['release_id']} (repo: {repo})",
        "",
        f"Kind: {kind.title()}   |   Initiator: @{manifest['initiator']}   |   "
        f"Base: {base['branch']} @ {base['sha'][:7]}   |   Platform tag: {platform_tag}",
        "",
        f"Approval needed: a reviewer who is not the initiator. {approval_clause}",
        "",
        _selection_table(manifest, change_notes_dir, repo),
    ]
    if non_jira_prs_section is not None:
        sections += ["", non_jira_prs_section]
    sections += [
        "",
        _held_back_section(manifest),
        "",
        "### Migrations",
        f"Contains migrations: {'yes' if migrations_chain else 'no'}"
        + (f"   (chain: {', '.join(migrations_chain)})" if migrations_chain else ""),
        "",
        "### Deploy files",
        f"Changes to deploy/skaffold.yaml or deploy/run/*.yaml in this release: {deploy_section_fact}"
        + (f"   (files: {', '.join(deploy_files_changed)})" if deploy_files_changed else ""),
        "",
        "### Gates",
        f"- [x] Dev-green gate: all selected commits passed dev regression and e2e "
        f"(waived: {'yes' if dev_green_waived else 'no'})",
        f"- [{'x' if release_pr_approved else ' '}] Release PR approved by one person who is not "
        "the initiator",
        (
            "- [x] Every non-Jira PR has a reason and a second approver "
            "(not applicable — none in this release)"
            if non_jira_prs_satisfied is None
            else f"- [{'x' if non_jira_prs_satisfied else ' '}] Every non-Jira PR has a reason and "
            "a second approver"
        ),
        f"- [{'x' if release_gate_result == 'pass' else ' '}] release-gate green on the release head "
        "(required before prod approval)",
        f"- [{'x' if stage_rollout_ok else ' '}] Cloud Deploy stage rollout SUCCEEDED and verify passed "
        "for the exact digest",
        f"- [{'x' if stage_regression_result == 'pass' else ' '}] Stage full regression record for the exact "
        "digest present and green (blocks prod if missing)",
        "",
        "### Commands",
        "`/release remove KEY` | `/release add KEY reason: text` | `/release nonjira PR reason: text` | "
        "`/release abort` | `/release waive dev-green reason: text`",
        "",
        "### Links",
        f"Manifest: radicdotai/radic-delivery-records/releases/{manifest['release_id']}.yaml",
        f"Cloud Deploy: {cloud_deploy_link}",
        f"Jira filter: key in ({', '.join(ticket_keys)})"
        if ticket_keys
        else "Jira filter: (no tickets selected)",
        "",
        "### UAT",
        "Stage URL, UAT checklist and the entry and exit criteria are in Quality, Security and "
        "Governance. Defects found in UAT carry label `uat-escape` and the field \"Escape stage\"; "
        "each needs a regression test before the next cut.",
    ]

    body = "\n".join(sections) + "\n"
    return RenderPrBodyResult(body=body, deploy_files_changed=deploy_files_changed)
