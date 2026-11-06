# Phase 0 Research: Cut-Time Open-Release Guard

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| "Guard: the cut refuses when this service already has an open release (status before finalised, aborted or failed) or an open release PR." | Confluence RAITSDA Reference 2 §3.4 |
| "a per-service stage concurrency group with cancel-in-progress: false, the stage Environment restricted to release/*, and a cut-time refusal of a second open release per service" | Confluence RAITSDA Runbook, review comment C11 (literal inline-comment reply, page owner) |
| `release-manifest.schema.json`'s `status` enum: `proposed, approved, cut, stage-deployed, stage-verified, prod-deployed, finalised, aborted, failed` — "open" is any status before the last three | `schemas/release-manifest.schema.json` |
| `cut()`'s existing early-guard sequence (`release_id_mismatch`, `hotfix_mismatch`, `status_mismatch`, `missing_change_note`), each refusing before any branch operation via a shared `_refused()` helper | `engine/src/radic_delivery/release/cut.py` (specs/009/014) |

## Design decisions made for this plan

### D1 — `other_manifests`: an explicit, optional input, never a live lookup

Confluence's own wording ("the cut refuses when this service already has
an open release") implies the cut must know about every other manifest
for its service — but discovering that set in reality means querying
`delivery-records`, a live system this sandbox cannot call. This exactly
mirrors a boundary this platform has already drawn more than once (most
directly, `rollback plan`'s `--current-release`/`--previous-release`
explicit inputs, specs/011).

**Decision**: `cut()` gains `other_manifests: list[dict[str, Any]] |
None = None`. The calling workflow (not built in this feature — a future
`release-cut.yml` concern) is responsible for supplying the real set,
however it discovers it. When omitted or empty, the new guard has nothing
to check and the function's behavior is byte-for-byte identical to
before this feature — a genuine backward-compatible addition, not a
behavior change gated by a flag.

### D2 — Filtering: same repo, different release id, still open

Per FR-002 through FR-005, three conditions must all hold for an other
manifest to block the cut:

1. `other["repo"] == manifest["repo"]` (FR-004 — a different repo never
   blocks, regardless of status).
2. `other["release_id"] != release_id` (FR-005 — a manifest cannot block
   itself; this also protects against a caller accidentally including
   the very manifest being cut in its own `other_manifests` list).
3. `other["status"] not in {"finalised", "aborted", "failed"}` (the
   "still open" test, Reference 2's own wording, Edge Case 1).

**Decision**: a small, pure filter function (or inline comprehension) in
`cut.py` applies all three; the refusal names the *first* qualifying
match's `release_id` and `status` (spec Edge Case 2 — which one is named
when several qualify is not load-bearing, since any one is sufficient
grounds for refusal).

### D3 — New `CutReason`: `"release_already_open"`

`CutReason` (`result.py`) is a closed `Literal` the CLI and callers
already pattern-match on. **Decision**: add `"release_already_open"` as a
new member, alongside the existing five. The refusal detail names the
blocking release explicitly, e.g. `"service already has an open release
2026.11.01-1 (status: stage-verified)."` — matching the existing
`_refused()` helper's detail-string convention exactly (every existing
`CutReason` already carries a specific, named detail, never a generic
message).

### D4 — Guard position: alongside the existing early guards

**Decision**: the new check is inserted in `cut()` immediately after the
existing `missing_change_note` guard and before `ordered_shas`/branch
creation — the same "every guard runs before any git write" discipline
`cut()` already follows for its other four guards. This guarantees FR-003
(no branch created) for free, by construction, not by a separate check.

### D5 — CLI surface: `--other-manifests`, comma-separated paths

This codebase has an established convention for multi-value CLI inputs:
comma-separated strings (`--linked-prs`, `--non-jira-prs`,
`--migrations-chain`), never a repeated-flag list. **Decision**: a new
`--other-manifests` option on `release cut`, comma-separated file paths,
each loaded with `json.loads(path.read_text())` (matching the existing
`manifest_path` loading exactly) before being passed to `cut()` as the
`other_manifests` list. Omitted, it defaults to `None` — no behavior
change (D1).

### D6 — Testing strategy

Real, unmocked local git fixtures, extending `test_release_cut.py`'s own
existing fixture style exactly (a real repo, a real `main`, a real
proposed manifest) — a new "other manifest, same repo, open status"
fixture proves the refusal and the absence of a created branch; "other
manifest, closed status" and "other manifest, different repo" fixtures
prove the cut proceeds identically to today in both cases; an
empty/omitted `other_manifests` regression test on the *existing* test
suite proves zero behavior change for every caller that doesn't use this
feature. No GCP, Docker, or live Jira/GitHub/delivery-records call
anywhere.
