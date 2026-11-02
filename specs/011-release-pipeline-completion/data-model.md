# Phase 1 Data Model: Release Pipeline Completion

## Entity: PromotionVerification (internal, `release/result.py`)

- `ancestry_verified`: bool — `--release-head` descends from the
  manifest's `base.sha`
- `tree_verified`: bool — every manifest `(dev_sha, release_sha)` pair
  has identical tree objects
- `tag_verified`: bool — a git tag named `--expected-tag` exists in
  `--repo-dir` and resolves to the same commit as `--release-head`
  (research.md D1)
- `release_digest_equals_stage_digest`: `"not_available"` always
  (research.md D2) — not a bool, so it's never confusable with a real
  pass/fail
- `ok`: bool — `ancestry_verified and tree_verified and tag_verified`
  (the Cloud-Deploy fact never gates this, since it's never actually
  checked)
- `detail`: list of human-readable reasons for whichever checks failed

## Entity: FinaliseResult (internal, `release/result.py`)

- `ok`: bool
- `manifest`: the updated manifest dict on success, or the **unchanged**
  original manifest on failure (same discipline as specs/009's
  `CutResult`)
- `reason`: `None` on success, else one of `"release_id_mismatch"` |
  `"status_mismatch"` | `"digest_mismatch"` | `"not_fast_forward"` |
  `"git_error"`
- `detail`: human-readable detail
- `tag`: the tag name created, when `ok` is `True`

## Entity: Release Manifest fields this feature populates (extends specs/008/009's entity)

On a successful `finalise`:

- `status`: `"finalised"`
- `digests.prod`: `--prod-digest`, when not already recorded
- `main.fast_forwarded_to`: `release_head`
- `main.at`: the finalisation timestamp
- `main.tag`: the created tag name

## Entity: RollbackPlan (internal, `rollback/result.py`)

- `environment`: the `--env` value
- `current_release` / `current_digest`: as supplied
- `target_release` / `target_digest`: as supplied
- `estimated_minutes`: as supplied or the default (research.md D4)
- `migrations_reverted`: as supplied or the default
- `no_op`: bool — `True` when `current_release == target_release` (spec
  Edge Case: the plan is still produced, but states plainly that no
  actual change would occur)

## Relationship to prior features' entities

`verify-promotion` and `finalise` both read (and `finalise` rewrites)
specs/008/009's release manifest in place — no further schema change
needed. `rollback plan` has no entity relationship to any prior feature
at all; it is a pure, standalone computation.
