# engine

The `radic-delivery` CLI: the single supported code path for inspecting and
validating this platform's service descriptors and policy exceptions, for
evaluating a service's CI quality gate, for scanning a service for security
findings, for linting a service's Cloud Deploy manifests, for parsing
and authorizing release-PR slash commands, for capturing change-note
records and checking release-note completeness, for selecting a
release's ready tickets into a draft manifest, for cutting the real
release branch from it, and for capturing test-result records. See
`specs/001-engine-scaffold/`, `specs/002-ci-gate-workflow/`,
`specs/003-security-scanning/`, `specs/004-deploy-yaml-lint/`,
`specs/005-release-command-parser/`,
`specs/006-release-commands-workflow/`,
`specs/007-change-note-capture/`, `specs/008-release-propose/`,
`specs/009-release-cut/`, `specs/010-test-result-capture/`, and
`specs/011-release-pipeline-completion/` for the full specification,
plan, and design rationale behind this package.

## Command surface

```text
radic-delivery descriptor validate <path>              # implemented (--schema PATH not yet supported)
radic-delivery descriptor show <path>                   # implemented (--env, --query not yet supported)
radic-delivery policy exceptions check <id>              # implemented (signature differs from Reference 3's
                                                           # --repo/--file/--today — takes <id> + --as-of instead)
radic-delivery gate evaluate --mode ci-gate <...>         # implemented (executes tools directly; Reference 3
                                                           # describes computing from pre-existing job results —
                                                           # --results-dir not yet supported)
radic-delivery gate evaluate --mode release-gate <...>    # not implemented yet (reports as such)
radic-delivery security scan --scope source|iac|all <...> # implemented (report-only — never blocks; not in
                                                           # Reference 3's own CLI table, built from Reference 2's
                                                           # workflow contract instead)
radic-delivery deploy lint <...>                          # implemented (binary — fails on a bad manifest;
                                                           # --deploy-dir PATH not yet supported)
radic-delivery release command <...>                      # implemented (parses + authorizes a PR comment)
radic-delivery notes write <...>                          # implemented (builds + validates a change-note record)
radic-delivery notes check --pr-body-file <...>           # implemented (warns, or blocks with --require-jira-key)
radic-delivery release propose <...>                      # implemented (reads local change-notes/, real git
                                                           # reachability; readiness/dev-green are explicit input,
                                                           # never a live Jira/test-results call — see below)
radic-delivery release cut <...>                          # implemented (real git branch + cherry-pick -x,
                                                           # chronological order, clean conflict rollback)
radic-delivery records put-test-result <...>              # implemented (validates the zero-skip-budget and
                                                           # stage-completeness rules; stores locally)
radic-delivery release verify-promotion <...>              # implemented (real ancestry/tree/tag checks against
                                                           # a release manifest; Cloud-Deploy-digest fact always
                                                           # "not_available" — --expected-tag is new, flagged)
radic-delivery release finalise <...>                      # implemented (real fast-forward + semver tag; refuses
                                                           # on any status/digest/fast-forward mismatch)
radic-delivery rollback plan <...>                         # implemented (pure computation; fully explicit input,
                                                           # no auto-lookup of "the previous release")

radic-delivery policy rulesets-diff                       # not implemented yet (no stub registered — not yet
                                                           # discoverable via --help at all)
radic-delivery tests inventory                            # not implemented yet
radic-delivery deploy release|promote|approve|rollback|status|drift   # not implemented yet (calls real Cloud Deploy)
radic-delivery migrations check                           # not implemented yet
```

14 of the 23 commands Confluence RAITSDA Reference 3 (Schemas, Identity
and Commands, §6) specifies are implemented; 9 remain. Four of those
fourteen have a narrower option surface than Reference 3 describes (noted
above) — each gap was a deliberate scope decision recorded in that
feature's own `research.md`/spec Assumptions, not an oversight, but none
has been revisited since. `security scan` exists outside Reference 3's
own CLI table entirely (built from Reference 2's workflow contract in
specs/003) and isn't a stand-in for anything that table lists.

Of this platform's 12 reusable GitHub Actions workflows (Reference 2:
Workflow Contracts), 3 are built — `ci`, `security`, `release-commands`
(`.github/workflows/`) — and 9 remain: `build`, `release-cut`, `deploy`,
`promote`, `hotfix-backport`, `rollback`, `research-deploy`, `cleanup`,
`infra`.

`gate evaluate --mode ci-gate` runs the service's own descriptor-declared
lint/type-check/unit-test tools (assumed already installed — installing a
service's own toolchain is the calling workflow's job, not this command's),
and reports one pass/fail Gate Result covering: lint, type-check, unit
tests, the descriptor's coverage floor, and the zero-skip-budget rule
(skips must be covered by an active, unexpired exception in
`policy/exceptions.yml` with `scope: quality.unit.skip`). It never calls
`gcloud` or any GCP API. See `specs/002-ci-gate-workflow/data-model.md` for
the full `GateResult` shape.

`security scan` runs `gitleaks` (hardcoded secrets), `hadolint`
(Dockerfile lint), and `trivy` in config-scanning mode (Dockerfile/IaC
misconfiguration — only when a Dockerfile actually exists on disk at the
descriptor's declared path), and reports every finding, severity-classified,
in one `SecurityScanResult`. This is the report-only rollout phase: **a
finding, at any severity, never fails this command** — the only way it
exits non-zero is the descriptor itself failing validation, before any scan
runs. Container-image scanning and Snyk are always reported as
`not_available`, never silently omitted — see
`specs/003-security-scanning/data-model.md` for the full result shape.

`deploy lint` reads a descriptor's declared Cloud Run service YAML files for
dev/stage/prod and checks each against five rules: the required placeholder
image reference (`image: app`), no `traffic` key, a startup probe present,
no inline secret (reusing `security scan`'s `gitleaks` integration rather
than a second detection method), and the three environment files matching
exactly except for the specific keys the descriptor's own
`cloud_deploy.deployables[].parity.allow` permits to differ. Unlike
`security scan`, this is a **binary correctness check, not an advisory
report**: a bad manifest fails the command (exit `2`), the same as an
invalid descriptor — Cloud Deploy applies these files exactly as committed,
so there is no report-only phase for them. Only `deploy lint` is
implemented; every other `deploy` subcommand calls real Cloud Deploy and
remains unimplemented. See `specs/004-deploy-yaml-lint/data-model.md` for
the full `DeployLintResult` shape.

`release command` classifies a PR comment's **first line only** into exactly
one of four outcomes: `not_a_command` (the overwhelming majority of PR
comments — not an error), `malformed` (looks like one of the six fixed
forms but fails to match it, e.g. a missing `reason:`), `unauthorized` (a
syntactically valid command from an author who isn't on the
`--release-managers` list, or isn't the `--tech-lead` for the
Tech-Lead-only `release waive dev-green` form), or `accepted` (with the
matched form name and its extracted arguments). Team membership and the
Tech Lead identity are explicit inputs — this command never looks them up
itself, same as `gate evaluate` doesn't install a service's own toolchain.
The comment body is read only from `--comment-file` or stdin, never from a
CLI text argument, so a calling workflow is never tempted to interpolate an
untrusted PR comment body into a shell command. See `specs/005-release-
command-parser/data-model.md` for the full `CommandCheckResult` shape.

`release command`'s JSON output also carries three additive fields —
`workflow_command` (`remove`/`add`/`nonjira`/`abort`/`waive`/`none`),
`workflow_outcome` (`applied`/`rejected`/`ignored`), and `reply_body`
(the exact PR-reply text, or `null` for `not_a_command`) — computed by
`release_commands/workflow_outcome.py::map_outcome` and consumed directly
by the `release-commands` reusable workflow
(`.github/workflows/release-commands.yml`), which wires this command into
a real `issue_comment` trigger and posts the reply. `research_close` and
`malformed` both report `workflow_command: "none"`, since the
architecture's `command` output has no slot for either — see
`specs/006-release-commands-workflow/data-model.md` for the full mapping
table and `research.md` for why.

`notes write` builds a change-note record from fully-explicit CLI inputs
(never fetching a PR's title/body/author from GitHub itself — that
remains the calling workflow's job), validates it against
`schemas/change-note.schema.json`, and writes it to a local path. The real
`gs://radicai-release-records/...` upload is not implemented; the result
always reports `upload_status: "not_available"`, never silently omitted or
faked as successful. `jira_key` accepts either a real ticket key or the
literal `"None"` for a change shipped without one — this schema
accommodation, and the full tightened schema, are new in this feature (the
schema existed since feature 001 but was an intentionally loose
placeholder until now). See `specs/007-change-note-capture/data-model.md`
for the full record shape.

`notes check` reads a PR body from a file (never a raw CLI text argument)
and classifies it as `has_jira_key`, `explicit_none` (the PR body states
`Jira: None`), or `incomplete` (neither). Without `--require-jira-key` an
incomplete body is reported but never fails the command (exit `0`); with
it, an incomplete body fails (exit `3`) — the same report-only-before-
blocking rollout discipline this platform already applies to its CI gate
and security scan. See `specs/007-change-note-capture/research.md` D2 for
the exact `Jira: KEY`/`Jira: None` text convention recognized.

`release propose` reads already-written change-note records from a local
directory (the same layout `notes write --out-dir` produces), filters
them to commits actually reachable from `--base` in a real local git
checkout (`--repo-dir`), groups the rest by Jira ticket, and splits them
into a proposed selection and a held-back list — then validates the
result against a now-corrected `schemas/release-manifest.schema.json` and
reports it as a draft (`status: "proposed"`) manifest. A candidate ticket
not explicitly listed in `--tickets` is held back as `"not Ready for
Review"` by default (fail-closed); a ticket whose commit is explicitly
listed in `--dev-green-failed` is held back for that reason instead —
neither Jira readiness nor the dev-green regression check is ever queried
live by this command, the single largest external-dependency boundary
this platform has drawn so far (see
`specs/008-release-propose/research.md` D4). `--non-jira-prs` explicitly
opts in pull requests merged without a Jira key; an unlisted one never
appears anywhere, listed-but-not-found ones are reported distinctly.
Without `--dry-run`, the manifest is also written locally under
`<out-dir>/releases/<release_id>.json` — never to the real
`radicdotai/delivery-records` repository, which this feature does not
touch. See `specs/008-release-propose/data-model.md` for the full
manifest shape and `research.md` D1 for the schema corrections this
feature made (the architecture's own release-manifest schema, as
written, could not validate any manifest a fresh proposal could actually
produce).

`release cut` reads an existing draft (`status: "proposed"`) manifest,
refuses to proceed if `--release-id`/`--hotfix` don't match it or its
status isn't `"proposed"`, re-verifies every selected commit still has a
local change-note record, then — for real, against a real local git
checkout — creates `release/<release-id>` from the fixed production line
(`main`, never a caller-suppliable ref) and cherry-picks (`git cherry-pick
-x`) every selected commit onto it in the commits' own chronological
order (never an arbitrary or caller-specified order). Any cherry-pick
conflict aborts the whole operation — the attempted branch is removed and
the repository is restored to exactly where it was, the manifest is left
unchanged, and the specific failing commit is named. On success, the
manifest is updated in place: `release_branch`, `release_head`, each
commit's `release_sha`/`cherry_pick_x`, and `status: "cut"`. `--dry-run`
validates and resolves everything (including the pending commit order)
without creating a branch or changing the manifest — though it cannot
guarantee a conflict-free real cut, since detecting a conflict means
actually attempting the cherry-pick. This is the first feature with no
external-dependency boundary at all: every behaviour, including the
conflict-abort path, is exercised against a real local git repository.
See `specs/009-release-cut/research.md` for the exact rollback steps and
exit-code mapping.

`records put-test-result` reads a complete test-result record from a file,
validates it against a now-corrected `schemas/test-result.schema.json`
(the third and last of feature 001's intentionally loose placeholder
schemas, after change-note and release-manifest, to be corrected and
given its first real consumer), and — on success — stores it locally,
mirroring the real `releases/<id>/test-results/<environment>-<repo>-
<suite>.json` key structure exactly (a release-less dev record is stored
under a fixed `dev` segment instead). Two rules are enforced at the
schema level, never silently bypassed: a record reporting one or more
skipped tests can never claim an overall pass (this platform's zero-skip-
budget principle, expressed for a record a future release-gate feature
will read), and a stage-environment record must carry a real release
identifier and declare itself as the full test scope. When both
`--release-id` and the record's own `release_id` are present, they must
match exactly. The real `radicdotai/delivery-records` upload is not
implemented; the result always reports `upload_status: "not_available"`.
See `specs/010-test-result-capture/data-model.md` for the full record
shape and `research.md` D1 for the schema corrections this feature made.

`release verify-promotion` reads a release manifest and independently
reports three real, local git facts, never combined into a single
pass/fail: **ancestry** (`--release-head` is a genuine descendant of the
manifest's `base.sha`), **tree** (every manifest commit pair's trees are
identical, confirming no tampering after the cut), and **tag** (a real
git tag named `--expected-tag` — a new, flagged input, since Reference
3's CLI table doesn't name one — exists and points at `--release-head`).
`release_digest_equals_stage_digest` is always reported `not_available`;
the live Cloud Deploy call it needs is out of scope, and `--image`/
`--digest`/`--cd-release` are accepted only for that comparison's
contract compatibility. See `specs/011-release-pipeline-completion/
research.md` D1/D2 for the full reasoning behind the tag check's design.

`release finalise` refuses unless the manifest's `status` is
`"prod-deployed"` and (when already recorded) `digests.prod` matches
`--prod-digest` exactly, then — only after both its own
`git merge-base --is-ancestor` pre-check and `git merge --ff-only`'s own
independent refusal agree a clean fast-forward is possible — moves the
real local `main` to the release head, creates a real
`v<major>.<minor>.<patch>` tag (auto-bumping the highest existing tag's
patch component by default; `--tag`/`--bump` override this), and updates
the manifest to `status: "finalised"` with `main.fast_forwarded_to`/
`main.at`/`main.tag` populated. A second finalisation of the same
manifest is always refused, naming its actual status; nothing is ever
partially applied. See `specs/011-release-pipeline-completion/
research.md` D3.

`rollback plan` is a pure computation over fully explicit input
(`--env`, `--current-release`/`--current-digest`, `--target-release`/
`--target-digest`, optional `--estimated-minutes`/
`--migrations-reverted`) — no git, no file I/O, always exits `0`.
Resolving "the previous release" or "the current release" automatically
is out of scope; identical current and target releases still produce a
plan, marked `no_op: true` rather than an error.

Every "not implemented yet" command exits with a distinct code (64) that is
never one of the four real outcomes below, so a caller can tell "this isn't
built yet" apart from "this failed."

## Exit code contract

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | invalid input (a descriptor or exception id failed validation) |
| 3 | policy failure (e.g. an expired policy exception) |
| 4 | infrastructure/environment error |
| 64 | the command is not implemented yet |

Every implemented command supports `--format json` and `--format text`,
reporting identical facts in both.

## Adding a new descriptor fixture

Real service descriptor fixtures live in `tests/fixtures/<service-name>.yml`
and are asserted valid in `tests/unit/test_descriptor_validate.py`'s
`REAL_SERVICE_FIXTURES` list. Deliberately invalid fixtures exercising a
specific failure mode live in `tests/fixtures/broken/`. To add a new one:

1. Add the YAML file under the appropriate directory.
2. If it is a real service's descriptor, add its filename to
   `REAL_SERVICE_FIXTURES` in `test_descriptor_validate.py`.
3. If it is a deliberately broken fixture, add a test asserting which
   specific `ValidationIssue.category` and field path it must produce.

## Development

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run mypy src/
```
