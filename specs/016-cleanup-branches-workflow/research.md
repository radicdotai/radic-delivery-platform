# Phase 0 Research: Cleanup Workflow (branches scope only)

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| `cleanup` reusable workflow contract: trigger "scheduled in delivery-platform (daily) and called by promote after prod success"; inputs `scope` (`research`\|`branches`\|`images`\|`all`), `retention_days`, `dry_run` (default true); outputs `deleted_count`, `kept_count`, `report_uri`; permissions `contents: write`, `id-token: write` | Reference 2, §3.11 |
| Behaviour: "Deletes expired research revisions, merged release branches, and untagged images older than retention... Never deletes a digest referenced by delivery-records, the previous prod digest, or anything with a human tag." | Reference 2, §3.11 |
| `main` is fast-forwarded to a release branch's tip only by `promote`'s finalise step, after prod success — a release branch is never merged via a GitHub PR merge | Reference 2, §3.7 (`promote`) |
| `release/git_history.py` already has `is_ancestor`, `commit_timestamp`, `delete_branch`, `current_branch` (specs/009, specs/011), reused here unchanged | `engine/src/radic_delivery/release/git_history.py` |

## Design decisions made for this plan

### D1 — Scope: `branches` only, `research`/`images`/`all` explicitly out of scope

Reference 2's `research` and `images` scopes both require live GCP calls
(deleting a Cloud Run tagged revision; deleting an untagged Artifact
Registry image) — this sandbox has neither Docker nor GCP credentials, the
same boundary already drawn for `build`/`deploy`/`promote`/`rollback`/
`research-deploy`. **Decision**: this feature implements `scope: branches`
only. `scope: all` is not implemented — passing it is refused cleanly
(`ExitCode.INVALID_INPUT`), not silently narrowed to `branches` alone,
since silently reinterpreting a caller's explicit `all` request as
"just branches" would misreport what actually happened.

### D2 — What "merged" means for a release branch

A release branch is never merged via a GitHub PR (Reference 2 §3.4: the
release bot creates it directly via `cherry-pick -x`); it becomes obsolete
the instant `main` is fast-forwarded past its tip by `promote`'s finalise
step (§3.7, already built as `release finalise`, specs/011). **Decision**:
"merged" = `is_ancestor(repo_dir, branch_tip, "main")` — the exact git
fact `release finalise`'s own fast-forward establishes, reusing
`git_history.py`'s existing `is_ancestor` primitive unchanged.

### D3 — Retention window default: a new, flagged convention

Reference 2 states explicit `retention_days` defaults for `images` (30)
and `research` (7), but not for `branches`. **Decision, flagged**: 14 days
for `branches` — the midpoint of the two stated defaults, long enough to
remain a useful reference point through a typical post-release incident
window (the spec's own stated rationale for retention existing at all),
short enough not to let merged branches accumulate for a month. A new,
explicit `--retention-days` input (default `14`) makes this overridable
without a code change if the real figure is later set authoritatively
elsewhere.

### D4 — Protected branches: `main`, `dev`, and whatever is currently checked out

Reference 2 names no explicit protected-branch list for this scope, but
FR-002 (spec) is unconditional: `main`/`dev` must never be deletion
candidates regardless of any other input, and neither should whatever
branch happens to be checked out when the command runs (deleting the
current branch is also simply impossible with `git branch -D`, but this
feature excludes it explicitly rather than relying on that side effect,
so the kept-reasons report stays accurate). **Decision**: hard-coded
exclusion list `{"main", "dev"}` plus the live result of
`current_branch(repo_dir)`, checked before any ancestry/age test — a
protected branch is never even evaluated, not merely "evaluated and
happens to fail."

### D5 — The engine command's scope: local delete only; the workflow pushes

`radic-delivery cleanup branches` deletes the local branch ref only
(`delete_branch`, specs/009's own primitive, reused unchanged) — it makes
no GitHub API or network call itself, the same "engine stays local-git-
only" discipline `release backport`/`release cut` already established.
**Decision**: `cleanup.yml` (named to match Reference 2's own central
workflow name exactly, the same convention every prior workflow file in
this platform follows — not `cleanup-branches.yml`, since this is the one
real `cleanup` workflow, just with only the `branches` scope implemented
so far) runs the engine command in its `branches` job, then for each
branch the result reports as deleted, runs a real
`git push origin --delete <branch>` step — since a purely local delete
inside an ephemeral CI runner accomplishes nothing on the real remote
(spec FR-006). The job refuses cleanly (a named, failing step) if
`inputs.scope` is anything other than `branches`, rather than silently
running the `branches` logic regardless of the requested scope (D1).

### D6 — Exit codes

`cleanup branches` always exits `ExitCode.OK` once every candidate branch
has been evaluated, whether any were actually deleted or not — "zero
branches deleted" is a plain, valid outcome (spec Edge Cases), never a
failure in itself; an unresolvable `--repo-dir` or git-environment problem
is `ExitCode.INFRA_ERROR`; `--scope all` (or any value other than
`branches`) is `ExitCode.INVALID_INPUT` (D1).

### D7 — Testing strategy

`cleanup branches` (US1) is tested against real local git fixtures,
mirroring `release backport`'s own test style (specs/015): a real `main`,
a real `release/**` branch fast-forwarded into it (merged, old and new
variants), a real unmerged `release/**` branch, and `main`/`dev`/the
checked-out branch deliberately shaped to also satisfy the merge/age
conditions (to prove D4's exclusion is unconditional, not incidental).
`cleanup.yml` (US2) is validated statically only (`actionlint`/
`zizmor`, zero findings), the same bar every prior reusable workflow in
this platform has been held to.
