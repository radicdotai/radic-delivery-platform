# Phase 0 Research: Release Pipeline Completion

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| `release verify-promotion` CLI surface: `--image REF`; `--digest DIGEST`; `--release-head SHA`; `--cd-release NAME` — "Central port of verify-promotion.sh: ancestry, tree, tag; with --cd-release also checks that the digest of the Cloud Deploy release equals the stage-tested digest" | Reference 3, §6 CLI table |
| `release finalise` CLI surface: `--release-id ID`; `--prod-digest DIGEST` — "Fast-forward main (bot only), tag, finalise the manifest, after prod success" | Reference 3, §6 CLI table |
| `rollback plan` CLI surface: `--env ENV`; `--target-digest DIGEST` — "Resolve the previous release and digest and print the rollback plan"; worked example: `{"environment": "prod", "current_release": "r-...", "current_digest": "sha256:...", "target_release": "r-...", "target_digest": "sha256:...", "estimated_minutes": 6, "migrations_reverted": false}` | Reference 3, §6 CLI table and worked example |
| `main.tag` pattern `^v[0-9]+\.[0-9]+\.[0-9]+$`, `main.fast_forwarded_to`, `main.at`; manifest `status` enum includes `prod-deployed` (this feature's expected starting status for `finalise`) and `finalised` (its result) | Reference 3, §3 "Release manifest" (specs/008's corrected schema) |
| Principle II: "Build once; promote only by verified `sha256:` digest; no mutable-tag deploys" (the principle `verify-promotion` exists to enforce) | Constitution |

## Design decisions made for this plan

### D1 — `release verify-promotion`'s three checks, concretely defined

Reference 3's one-line description ("ancestry, tree, tag") doesn't spell
out what each check compares against, and its CLI table doesn't include
a `--manifest PATH` flag the way `propose`/`cut` do — but, like those two
commands, the table is not exhaustive (research.md precedent: specs/006's
D7, specs/007's D3, specs/008's D3). This feature reads the same release
manifest `propose`/`cut` already produce (`--manifest PATH`, new, flagged)
rather than inventing a second source of truth or requiring the caller to
re-supply facts the manifest already records:

- **Ancestry**: `--release-head` must be a real descendant of (or equal
  to) the manifest's own recorded `base.sha` — confirming the release
  branch's claimed head genuinely grew from the recorded starting point,
  nothing foreign merged in. Checked via `git merge-base --is-ancestor`.
- **Tree**: for every commit pair the manifest records (`dev_sha`,
  `release_sha`), the two commits' trees must be identical — confirming
  every cherry-pick preserved content exactly, with no tampering after
  the cut. Checked via comparing `<commit>^{tree}` for each pair
  (`git rev-parse` + equality, no `git diff-tree` needed since an exact
  tree-object match is a stronger and simpler guarantee than a diff being
  empty). If the manifest records zero commits (an empty release,
  specs/008's Edge Case), this check trivially passes.
- **Tag**: a real git tag — spec Acceptance Scenario 3 ("the expected tag
  is missing or points at the wrong commit") is explicit that this is a
  tag-existence-and-position check, not a string-shape check. Reference
  3's CLI table has no flag naming which tag is expected (it only shows
  `--image`/`--digest`/`--release-head`/`--cd-release`), so, following the
  same "new explicit input, flagged" precedent as this feature's own
  `--manifest` addition, this check takes one further new required input:
  `--expected-tag NAME`. The check passes when a git tag `NAME` exists in
  `--repo-dir` and resolves to the exact same commit as `--release-head`;
  it fails if the tag doesn't exist at all, or exists but resolves
  anywhere else. (In the real pipeline this would be a tag written at
  build time, before promotion — a capability this platform hasn't built
  yet; this feature takes the expected tag's name as given, the same
  external-dependency boundary D2 and D4 both draw elsewhere.)
  `--image`/`--digest` (Reference 3's own CLI flags) are accepted only as
  inputs to the `--cd-release` digest comparison (D2) — like `--cd-release`
  itself, they are inert whenever that comparison doesn't run (which, per
  D2, is always in this feature); they play no part in the tag check
  itself.

This — one new required flag, `--expected-tag` — is a smaller, more
narrowly-scoped flagged convention than the first draft of this decision
(which had repurposed `--image`/`--digest` into a digest-pinning string
check); recorded here for confirmation, not asserted as self-evidently
correct.

### D2 — The Cloud-Deploy-digest fact: always `not_available`, `--cd-release` accepted but inert

Even when `--cd-release` is supplied, this feature cannot make the live
`gcloud deploy releases describe` call the real check needs — there is no
fallback-to-manifest/rollout-YAML path this sandbox can exercise for real
either. **Decision**: `release_digest_equals_stage_digest` is always
reported `not_available` in this feature's output, regardless of whether
`--cd-release` was given; the flag is accepted (for contract
compatibility and future wiring) but never changes this feature's
behaviour — the same "accept the input, don't fake the result" honesty
already established for specs/003's Snyk/image-scanning and specs/008's
`--bucket`.

### D3 — `release finalise`: starting status, fast-forward safety, and tag version

- **Starting status**: refuses unless the manifest's `status` is
  `"prod-deployed"` (spec FR-003) — the status a real prod deploy+gate
  would set, a capability this platform has not built yet (spec
  Assumptions); this feature only consumes that status as given, the
  same way specs/009's `cut` only consumes a `proposed` manifest as given.
- **Fast-forward safety**: before touching `main` at all, confirm `main`'s
  current tip is an ancestor of the manifest's `release_head` (`git
  merge-base --is-ancestor`); if not, refuse (spec FR-005) rather than
  attempt anything destructive. The actual move is `git checkout main &&
  git merge --ff-only <release_head>` — `--ff-only` is git's own,
  independent enforcement of the exact same guarantee, so this feature's
  own pre-check and git's own refusal both have to agree before anything
  changes (defense in depth, not redundant).
- **Tag version**: Reference 3 names the tag's pattern but not how its
  version number is chosen. **Decision**, flagged: list existing
  `v<major>.<minor>.<patch>` tags reachable from `main` (`git tag --list
  'v*'`, a real, local, fully-available operation — no live registry or
  release-history call needed), take the highest, and bump its **patch**
  component by default; a caller-supplied `--tag NAME` (new, optional)
  overrides this entirely, and an optional `--bump major|minor|patch`
  (new, default `patch`) controls the automatic case. When no prior tag
  exists at all, the first tag is `v1.0.0`.
- **Digest cross-check**: when the manifest already records
  `digests.prod`, `--prod-digest` must match it exactly (refused
  otherwise, the same consistency discipline as `cut`'s `--release-id`
  check); when the manifest doesn't yet record it, `--prod-digest` is
  recorded into `digests.prod` as part of this finalisation — the first
  and only time this feature itself writes that field.

### D4 — `rollback plan`: fully explicit input, zero I/O

Reference 3's own worked example output includes `current_release`/
`current_digest` alongside `target_release`/`target_digest`, confirming
the table's `--env`/`--target-digest` pair is abbreviated (same precedent
as D1). **Decision**: `--env ENV`, `--current-release NAME`,
`--current-digest DIGEST`, `--target-release NAME`, `--target-digest
DIGEST` are all required, explicit inputs (spec FR-006 — this platform
cannot resolve "the previous release" or "the current release" without a
live call to `delivery-records`, the same external-dependency boundary
specs/008 already drew for ticket readiness). `--estimated-minutes` (
optional, default `5` — a placeholder constant, since no historical
rollback-duration data source exists in this sandbox either, flagged
the same way) and `--migrations-reverted`/`--no-migrations-reverted`
(optional boolean, default `false`) complete the plan's fields. This
command touches no git repository and makes no file I/O at all — the
simplest of the three, a pure function from explicit input to a reported
plan.

### D5 — Exit codes

`verify-promotion`: any of the three checks failing is
`ExitCode.POLICY_FAILURE` — this is a safety gate, and a failing fact
means "not safe to promote," the same classification `gate evaluate`
already gives a failed quality check; an unusable `--repo-dir` or an
unresolvable commit is `ExitCode.INFRA_ERROR`, matching specs/008/009's
own git-environment-error precedent. A full pass is `ExitCode.OK`.

`finalise`: a manifest/release-id/digest mismatch or wrong starting
status is `ExitCode.INVALID_INPUT` (the same classification `cut` gives
its own manifest-consistency checks); `main` not being a fast-forward
ancestor of `release_head`, or any other git-environment problem, is
`ExitCode.INFRA_ERROR`. A successful finalisation is `ExitCode.OK`.

`rollback plan` always exits `ExitCode.OK` — it is a pure computation
with no real failure mode beyond the CLI's own required-option
enforcement (which happens before this feature's own code runs at all).

### D6 — Testing strategy

Like specs/009, `verify-promotion` and `finalise` have no external-
dependency boundary beyond the pieces already flagged above (D2's
Cloud-Deploy check, D3's "who sets `prod-deployed`" deferral) — every git
behaviour is exercised against a real local git repository, including
each of the three failure modes for `verify-promotion` and both refusal
paths for `finalise`. `rollback plan` needs no fixture at all: it is
tested the same way specs/008's pure `selector.py` was, with inline
input/output assertions.
