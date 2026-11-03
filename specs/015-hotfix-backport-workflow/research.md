# Phase 0 Research: Hotfix Backport Workflow

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| `hotfix-backport` reusable workflow contract: trigger `workflow_run` of `prod` completed successfully, for a branch ending `-hf`; input `hotfix_branch` (`release/<id>-hf`); outputs `pr_number`, `picked_commits` (JSON list), `conflicts` (bool); secrets `DELIVERY_BOT_APP_ID`/`DELIVERY_BOT_PRIVATE_KEY`; permissions `contents: write`, `pull-requests: write` | Reference 2, §3.8 |
| Behaviour: "Opens a PR from the hotfix commits into `dev` using `cherry-pick -x`, after prod success only. Not into the release branch. Conflicts open the PR as draft with a conflict note and notify the owner." | Reference 2, §3.8 |
| The release-manifest schema already records, per selected commit, both `dev_sha` and `release_sha` (the latter populated by `release cut`, specs/009) — the real, already-cherry-picked content the hotfix actually ran in prod | `schemas/release-manifest.schema.json` (specs/008, corrected) |
| `release/git_history.py` already has real `cherry_pick`/`abort_cherry_pick`/`create_branch_from`/`commit_timestamp` primitives (specs/009), reused here unchanged | `engine/src/radic_delivery/release/git_history.py` |

## Design decisions made for this plan

### D1 — Conflict handling: continue past a conflicting commit, never abort the whole backport

`release cut` (specs/009) aborts the *entire* operation on its first
cherry-pick conflict — appropriate there, since a release branch with a
missing commit would be silently wrong. A backport is different: Reference
2's own behaviour description ("conflicts open the PR as draft with a
conflict note") only makes sense if the PR still gets opened with
whatever *did* land — implying every other commit still lands, and only
the conflicting one is skipped and named (spec FR-002, FR-003).
**Decision**: for each commit (in the release's own chronological order,
reusing `commit_timestamp` exactly as `release cut` already does), attempt
`cherry_pick`; on `"conflict"`, call `abort_cherry_pick` for that one
commit only and continue to the next, recording it as conflicted — never
deleting the branch, never stopping. The branch always exists at the end,
carrying every commit that applied cleanly.

### D2 — `release backport`'s inputs and the commits it picks

The manifest already records `release_sha` per selected commit — the
actual commit that ran in prod — so this feature cherry-picks *that*
value (`git cherry-pick -x <release_sha>`), not `dev_sha` (the original,
pre-cherry-pick commit on `dev`), matching Reference 2's own "the hotfix
commits" wording (the thing that succeeded in prod, not the thing that
was originally proposed). **Decision**: `release backport --manifest
PATH --repo-dir PATH --into dev` (new, flagged `--into`, default `dev`,
since Reference 2 only ever names `dev` as the target but doesn't show a
flag for it — matching the same "new explicit input, flagged" precedent
as every comparable gap this project has filled). Commits from both
`selection.tickets[].commits[]` and `selection.non_jira_prs[].commits[]`
are included, same as `release cut`'s own `_selected_shas` logic.

### D3 — The backport branch name: a new, flagged convention

Reference 2 names no specific branch for the backport PR's head.
**Decision, flagged**: `backport/<release_id>` (the manifest's own
`release_id`, which already carries the `-hf` suffix for a hotfix) — the
same naming-convention style as `release/<id>` itself. A branch of that
name already existing is refused cleanly (the same `GitHistoryError`
`create_branch_from` already raises on a name collision — no new check
needed, spec Edge Case).

### D4 — Exit codes

`release backport` always exits `ExitCode.OK` once the backport branch is
created, regardless of whether any individual commit conflicted —
conflicts are a reported *fact* for the caller to act on (the same way
`rollback plan`'s `no_op` or `tests inventory`'s quarantine counts are
facts, never failures in themselves); a git-environment problem (the
branch name already exists, `--into` doesn't resolve) is
`ExitCode.INFRA_ERROR`.

### D5 — `hotfix-backport.yml`: a single job, gated defensively on the triggering workflow_run

Reference 2 places the real `workflow_run` trigger (and its
`conclusion`/`head_branch` gate) on the *caller* (`hotfix.yml`), not on
the reusable workflow itself — but no `templates/callers/hotfix.yml`
exists in this repo yet (out of scope for this feature; see spec
Assumptions), so there is nothing to attach that gate to. **Decision,
flagged**: `hotfix-backport.yml` re-checks the gate itself, defensively
(Principle III) — a new input beyond Reference 2's own `hotfix_branch`,
`conclusion` (the caller's own `github.event.workflow_run.conclusion`,
passed through explicitly rather than defaulted inside this workflow,
since a `workflow_call` input's `default:` must be a static literal, not
a live expression). The job's own `if:` requires `conclusion ==
'success'` and `hotfix_branch` ending `-hf` (spec FR-004, Acceptance
Scenario 3) before any git operation runs. It checks out the calling
service repo, runs `release backport`, pushes the resulting branch (the
engine itself never pushes, the same split `release-cut.yml` already
established), and opens the PR into `dev` (never the hotfix/release
branch, FR-005) — as a draft naming every
conflicted commit in its body when `conflicts` is `true`, a normal PR
otherwise (FR-006).

### D6 — Testing strategy

`release backport` (US1) is tested against real local git fixtures,
mirroring `release cut`'s own test style exactly (specs/009): a real
`dev` branch, a real hotfix release branch with real cherry-picked
commits recorded in the manifest's `release_sha` fields, and a
deliberately conflicting commit for the partial-conflict scenario.
`hotfix-backport.yml` (US2) is validated statically only
(`actionlint`/`zizmor`, zero findings — verified directly, the same bar
`release-cut.yml` (specs/014) already achieved and improved on relative
to this platform's earlier workflows).
