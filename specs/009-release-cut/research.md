# Phase 0 Research: Release Branch Creation and Cherry-Pick

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| `release cut` CLI surface: `--release-id ID`; `--manifest PATH`; `--hotfix` — "Create release/ID from the prod line and cherry-pick -x the selection" | Reference 3: Schemas, Identity and Commands, §6 CLI table |
| Manifest fields this feature populates: `release_branch` (pattern `^release/`), `release_head`, each commit's `release_sha`/`cherry_pick_x: true`, `status` moving `proposed` → `cut` | Reference 3, §3 "Release manifest" (specs/008's corrected schema) |
| "A commit with no change-note record stops the cut: re-run dev CD for that sha, fix the PR body, cut again" | Release and Operations Runbook |
| "`cherry-pick -x`" (not a plain cherry-pick) — every cherry-picked commit records its original SHA in the resulting commit message | Reference 3, §3 (the `cherry_pick_x` field name itself) |

## Design decisions made for this plan

### D1 — Extending `git_history.py` with real branch/cherry-pick operations

Specs/008 already established this module as "real git subprocess calls,
fixed and parameterised, never a caller-supplied command string"
(Principle VII). This feature adds exactly the operations needed and no
more:

- `commit_timestamp(repo_dir, sha) -> int` (`git show -s --format=%ct`) —
  used to compute the strict chronological cherry-pick order (FR-005);
  this is what makes the order a property of the commits themselves, not
  something this feature or its caller chooses.
- `current_branch(repo_dir) -> str` — recorded before any mutation, so a
  failure path can restore exactly where the repository was.
- `create_branch_from(repo_dir, branch_name, base_ref)` — `git checkout
  -b <branch_name> <base_ref>`, always called with `base_ref="main"`
  (FR-004 — never a caller-suppliable ref).
- `cherry_pick(repo_dir, sha) -> CherryPickOutcome` (`ok` or `conflict`) —
  `git cherry-pick -x <sha>`; a non-zero exit with conflict markers
  present is distinguished from any other git failure (e.g. the sha not
  existing at all, which is an input error, not a conflict).
- `abort_cherry_pick(repo_dir)` / `checkout(repo_dir, ref)` /
  `delete_branch(repo_dir, branch_name)` — the exact three-step rollback
  (`git cherry-pick --abort`, return to the original ref, delete the
  attempted branch) that makes FR-006's "no partially-created branch or
  other repository change behind" true in practice, not just in
  intention.

### D2 — Validating the manifest before touching anything (FR-001, FR-002)

Three checks, in order, each a hard refusal naming the specific mismatch,
before any git operation or file write:

1. `manifest["release_id"] == release_id` (the caller's `--release-id`).
2. `(manifest["kind"] == "hotfix") == hotfix` (the caller's `--hotfix`
   flag) — a release manifest cut as a hotfix, or vice versa, is refused
   rather than silently cut under the wrong kind.
3. `manifest["status"] == "proposed"` — refusing to re-cut an
   already-cut (or aborted, or further along) manifest, naming its actual
   status (spec Edge Case).

### D3 — Re-verifying change-note records locally (FR-003)

Every `dev_sha` across `selection.tickets[].commits[]` and
`selection.non_jira_prs[].commits[]` must have a matching local
change-note record at `<change_notes_dir>/change-notes/<repo>/<sha>.json`
— the exact same local layout specs/007/008 already established, checked
directly (a file-existence + schema-shape check), not via specs/008's
full `load_candidates` (which also filters by git reachability, a concern
already resolved at `propose` time — re-running that filter here would
be redundant work, not a new check).

### D4 — Cherry-pick order: strict chronological, across the whole selection

FR-005 requires "the order those commits actually occurred," not grouped
by ticket. Every selected commit, from both `selection.tickets[]` and
`selection.non_jira_prs[]`, is collected into one flat list, each
annotated with its `commit_timestamp` (D1), and cherry-picked in
ascending timestamp order — a ticket's own commits stay relatively
ordered since they are each individually timestamped, and interleave
correctly with another ticket's or a non-Jira PR's commits that happened
in between on `dev`.

### D5 — Conflict and rollback: tested for real, not asserted

Unlike every feature from specs/005 onward, this feature has no
external-dependency boundary to draw — git is fully available and fully
real in this sandbox. The conflict-abort path (FR-006, User Story 2) is
exercised with a real fixture: a repository where `main` and a
cherry-picked commit both modify the same line differently, producing a
genuine `git cherry-pick` conflict, confirmed by actually attempting the
cherry-pick and observing the real failure — never simulated or asserted
without running real git.

### D6 — `--dry-run` cannot promise "no conflict will occur" (spec Edge Case)

Unlike specs/008's `--dry-run` (which computes the *entire* real output
with no side effect, since selection is pure computation), this
feature's `--dry-run` validates the manifest (D2), re-verifies change-note
records (D3), and resolves the exact cherry-pick order (D4) — but does
not attempt the cherry-picks themselves, since doing so *is* the
repository mutation this flag exists to avoid. This is stated explicitly
in the command's own help text and this spec's Edge Cases, not left as an
implicit limitation someone discovers by surprise: a clean `--dry-run`
is a strong signal, not a guarantee, that the real cut will also succeed.

### D7 — Exit codes, following established precedent

A manifest/status mismatch or a missing change-note record (D2, D3) is
`ExitCode.INVALID_INPUT` — the input this feature was given (the
manifest, or the caller's `--release-id`/`--hotfix`) doesn't hold up,
the same classification `descriptor validate`/`notes write` already give
a structurally-invalid input. A cherry-pick conflict, or `--repo-dir`
not being a usable git repository, is `ExitCode.INFRA_ERROR` — a fact
about the state of the repository itself, the same classification
specs/008's `release propose` already gives an invalid `--repo-dir`/
`--base`. A successful cut is `ExitCode.OK`.
