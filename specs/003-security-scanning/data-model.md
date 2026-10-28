# Phase 1 Data Model: Central Security Scanning Workflow (report-only)

## Entity: ToolInvocation (internal, `security/tools.py`)

Reuses the same shape as `gate/commands.py`'s `ToolInvocation` (check_name,
argv) — not persisted, a pure value from scope/descriptor selection
(research.md D3).

## Entity: Finding

One per detected issue, regardless of which tool produced it:

- `tool`: `gitleaks` | `hadolint` | `trivy-config`
- `severity`: `critical` | `high` | `medium` | `low` (research.md D2's mapping)
- `rule_id`: the tool's own identifier (gitleaks `RuleID`, hadolint `code`,
  trivy `ID`)
- `file`: path of the finding
- `line`: int or `None` when the tool doesn't report one
- `description`: human-readable message (tool's own `Description`/
  `message`/`Message`, never the raw secret value for gitleaks findings —
  see Security note below)

**Security note**: a gitleaks `Finding`'s `description` MUST NOT include
the `Secret` field's actual value — only `RuleID`/`Description`/location.
Printing a real secret into a PR-visible report would be exactly the
exposure this feature exists to catch, not cause.

## Entity: ScopeResult

One per requested scope (`source`, `iac`; `image` is always present and
always `not_available`):

- `scope`: `source` | `iac` | `image`
- `status`: `checked` | `not_applicable` (FR-004/FR-009 — e.g. `iac`
  requested but the descriptor declares no Dockerfile) | `not_executable`
  (FR-010 — the tool itself could not run) | `not_available` (`image` only,
  FR-007)
- `findings`: `list[Finding]` (empty when `status` is anything but `checked`)

## Entity: SecurityScanResult — the feature's primary output

- `scopes`: `list[ScopeResult]`
- `counts`: `{"critical": int, "high": int, "medium": int, "low": int}` —
  aggregated across every `ScopeResult` with `status == "checked"`
  (FR-005, SC-004's "100% of scan reports state image/Snyk unavailable" is
  satisfied structurally: `image` is always present in `scopes`, `snyk` is
  always present in `snyk_status` below)
- `snyk_status`: `{"status": "not_available"}` always, in this feature
  (FR-008)
- `scan_result`: `"completed"` always (research.md D4 — this field name
  matches the architecture's own named `ci`... no, `security` workflow
  output `scan_result`; its value never varies with findings, by design)

This is the JSON shape `radic-delivery security scan --format json` emits,
and the shape `.github/workflows/security.yml` reads back to populate its
own `scan_result`, `findings_critical`, `findings_high` outputs and the
job-summary report (`sbom_uri` is passed through as a fixed `not_available`
marker, since SBOM generation is out of scope for this feature same as it
was out of scope for `gate evaluate`'s `deploy_lint`/`test_inventory_uri`).

## Relationship to prior features' entities

- `SecurityScanResult` is computed from a **Service Descriptor** (feature
  001) that must already pass `descriptor validate` — `security scan`
  reuses that validator directly, exactly as `gate evaluate` (feature 002)
  does, rather than re-implementing any part of it.
- Unlike `GateResult` (feature 002), `SecurityScanResult` has no concept of
  overall pass/fail — by design (FR-006, research.md D4), there is nothing
  in this entity for a caller to branch a blocking decision on yet.
