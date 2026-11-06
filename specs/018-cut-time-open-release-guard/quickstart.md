# Quickstart: Cut-Time Open-Release Guard

Validates the feature end-to-end against a real local git repository —
no GCP, Docker, or live Jira/GitHub/delivery-records call anywhere.

## Prerequisites

```bash
cd engine && uv sync
```

## Scenario 1 — refused: same repo, another release still open

```python
from radic_delivery.release.cut import cut

other_open = {
    "release_id": "2026.11.01-1",
    "repo": "radicdotai/web-bff",
    "status": "stage-verified",
}

result = cut(
    manifest,  # a real, "proposed"-status manifest for radicdotai/web-bff
    repo_dir=repo_dir,
    change_notes_dir=notes_dir,
    release_id="2026.11.03-1",
    hotfix=False,
    dry_run=False,
    other_manifests=[other_open],
)
# Expected: result.ok is False
#           result.reason == "release_already_open"
#           result.detail names "2026.11.01-1" and "stage-verified"
#           no release/2026.11.03-1 branch was created
```

## Scenario 2 — proceeds: the other manifest is already closed

```python
other_closed = {**other_open, "status": "finalised"}
result = cut(manifest, ..., other_manifests=[other_closed])
# Expected: result.ok is True — identical to omitting other_manifests entirely
```

## Scenario 3 — proceeds: the other manifest is for a different repo

```python
other_different_repo = {**other_open, "repo": "radicdotai/frontend-v2"}
result = cut(manifest, ..., other_manifests=[other_different_repo])
# Expected: result.ok is True
```

## Scenario 4 — proceeds: no other manifests supplied (regression check)

```python
result = cut(manifest, ..., other_manifests=None)
# Expected: byte-for-byte identical to this platform's existing,
# already-merged release-cut behavior (every test in test_release_cut.py
# written before this feature continues to pass unmodified).
```

## Scenario 5 — CLI end-to-end

```bash
echo '{"release_id": "2026.11.01-1", "repo": "radicdotai/web-bff", "status": "stage-verified"}' \
  > /tmp/other-manifest.json

uv run --project "$ENGINE_PROJECT" radic-delivery release cut \
  --manifest /tmp/proposed-manifest.json \
  --release-id 2026.11.03-1 \
  --repo-dir "$REPO_DIR" --change-notes-dir "$NOTES_DIR" \
  --other-manifests /tmp/other-manifest.json \
  --format json
# Expected: exit code is INVALID_INPUT (matching every existing non-
# cherry_pick_conflict refusal reason's exit code); the JSON payload's
# "reason" field is "release_already_open".
```

## Final validation

```bash
cd engine
uv run pytest -q
uv run ruff check .
uv run mypy src/
```
