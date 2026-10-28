# Phase 0 Research: Central Security Scanning Workflow (report-only)

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| Reusable workflow name `security`, inputs `scope`/`image_ref`/`enforce`/`fail_on`, outputs `scan_result`/`sbom_uri`/`findings_critical`/`findings_high` | Reference 2: Workflow Contracts and Caller Templates |
| gitleaks (secrets), Hadolint (Dockerfile), Trivy (config/IaC + image) named as "second opinion" scanners alongside Snyk | Quality, Security and Governance |
| New scanning starts report-only for the first 1-2 weeks, blocking only turned on later per a documented schedule | Quality, Security and Governance |
| Severity policy treats a verified secret as the single most urgent category ("block, rotate immediately") | Quality, Security and Governance |
| Snyk Team-plan purchase is a pending, unresolved open item (OI-9) | Overview and Architecture, open item register |
| No `build` workflow or container image exists yet in this repo | specs/002-ci-gate-workflow (prior feature) |

## Design decisions made for this plan

### D1 — Tool output formats (verified against the real binaries, not documentation alone)

Each tool's actual JSON shape, confirmed by running it against a small
planted sample in this environment:

- **gitleaks** (`gitleaks detect --source <dir> --no-git --report-format
  json --report-path <file> --exit-code 0`): a JSON array; each element has
  `RuleID`, `Description`, `File`, `StartLine`, `Secret`, `Fingerprint`.
  **No severity field at all.** `--no-git` is required since these sample
  fixtures are not (and should not become) their own git repositories;
  `--exit-code 0` is required so gitleaks' own process exit code (which is
  1 when it finds anything) is never mistaken for "the tool failed to run."
- **hadolint** (`hadolint --format json <Dockerfile>`): a JSON array; each
  element has `code`, `file`, `level` (`error`/`warning`/`info`/`style`),
  `line`, `message`. Exits 1 when it finds anything — same "exit code is
  not a run-failure signal" caveat as gitleaks.
- **trivy** (`trivy config --format json <dir>`, stdout and stderr
  captured **separately** — merging them breaks JSON parsing, since trivy
  writes progress/log lines to stderr while the report goes to stdout):
  `Results[].Misconfigurations[]`, each with `ID`, `Title`, `Message`,
  `Severity` (`CRITICAL`/`HIGH`/`MEDIUM`/`LOW`/`UNKNOWN`),
  `CauseMetadata.StartLine`. Exits 0 even when misconfigurations are found.

### D2 — Severity mapping (a new convention this feature introduces)

The architecture names a 4-level severity scale (critical/high/medium/low)
for its *policy* but does not define, tool-by-tool, how each scanner's own
output maps onto it — this is because the real production stack (Snyk
primarily) has its own native severity field, whereas the "second opinion"
tools built here vary:

| Tool | Native signal | Mapping | Rationale |
|---|---|---|---|
| gitleaks | none (every finding is "a secret was found") | always `critical` | Matches the governance policy's own treatment of secrets as the single most urgent category — not an invented severity, a direct application of an existing policy statement |
| hadolint | `level`: error / warning / info / style | error→`high`, warning→`medium`, info→`low`, style→`low` | hadolint has no "critical" level; nothing it checks is secret-shaped, so `high` is its ceiling |
| trivy config | `Severity`: CRITICAL / HIGH / MEDIUM / LOW / UNKNOWN | direct lowercase mapping; `UNKNOWN`→`low` (conservative, since trivy itself could not classify it) | trivy's own scale already matches ours almost exactly |

This mapping is flagged here, the same way feature 001 and 002 flagged
their own new conventions, for a security owner to confirm before it is
relied on for the future blocking rollout.

### D3 — Scope-to-tool mapping

- `scope: source` → gitleaks only.
- `scope: iac` → hadolint + trivy config, and only when the Dockerfile
  named by the descriptor's `build.dockerfile` actually **exists on disk**
  in the service's repo. `build.dockerfile` is a *required* schema field
  with a default (feature 001) — every valid descriptor "declares" one, so
  descriptor presence alone can never express "this service has no
  Dockerfile." The applicability check (`tools.py`'s `_dockerfile_exists`)
  therefore does the one filesystem check this module needs: it looks for
  the named file relative to `repo_root`. This was discovered mid-build
  (not foreseen when the spec/data-model were first written) and corrected
  before implementation was considered done — `python-sample` (specs/002,
  no `Dockerfile` file) now correctly reports `iac` as `not_applicable`,
  and `python-sample-bad-dockerfile` (has one) reports it `checked`.
- `scope: all` → all three.
- `scope: image` → explicitly not implemented (FR-007); requesting it
  still returns a result (not an error), with `image_scan.status ==
  "not_available"`.

### D4 — Exit-code contract: always a report, FR-006 has no exceptions

Unlike `gate evaluate` (feature 002), `security scan`'s own process exit
code does **not** vary with findings at all, by design (FR-006). The only
non-`OK` exit this command can produce is `INVALID_INPUT`, and only when
the descriptor itself fails validation (reusing feature 001's validator,
same pattern as `gate evaluate`) — before any scanner runs. Once scanning
starts, the result is always reported and the command always exits `OK`,
regardless of how many critical findings it reports. This is the literal
meaning of "report-only": not "mostly report-only with one blocking
exception," but strictly only ever a report.

### D5 — Posting findings where a reviewer will see them

GitHub renders a workflow step's `$GITHUB_STEP_SUMMARY` as Markdown
directly on the job's summary page, linked from the pull request's checks
tab — visible without opening raw logs, satisfying FR-011/SC-003, and
requires no new GitHub permission beyond what every workflow already has.
A PR-comment-based alternative was considered and rejected for this
increment: it needs `pull-requests: write` permission and comment
deduplication logic neither strictly required by this spec nor justified
yet at this stage of the rollout.

## Open items carried forward (not resolved by this feature)

- The severity mapping in D2 is a new convention (like specs/002's
  skip-exception scope convention) — flagged for a security owner to
  confirm, not something this spec treats as settled fact.
- Image scanning and Snyk remain unimplemented, each visibly reported as
  such (FR-007, FR-008) — both wait on separate, already-tracked
  prerequisites (a `build` workflow; OI-9) that this feature does not
  resolve.
