# Quickstart: Quality Gate Completion

No live Jira/GitHub/GCP/database — real local fixtures, real local JSON
and YAML files.

```bash
cd engine
uv sync

# =========================================================================
# gate evaluate --mode release-gate
# =========================================================================
REPO=tests/fixtures/sample-repos/python-sample
RESULTS=/tmp/release-gate-results
mkdir -p "$RESULTS/releases/2026.11.03-1/test-results"
DIGEST="sha256:0000000000000000000000000000000000000000000000000000000000000003"

cat > "$RESULTS/releases/2026.11.03-1/test-results/stage-sample-e2e-full-stage.json" <<JSON
{
  "schema_version": 1, "repo": "radicdotai/sample", "environment": "stage",
  "release_id": "2026.11.03-1", "digest": "$DIGEST", "commit": "$(printf '1%.0s' {1..40})",
  "suite": "e2e-full-stage", "runner": "playwright", "scope": "full",
  "started_at": "2026-11-03T00:00:00Z", "finished_at": "2026-11-03T00:10:00Z",
  "result": "pass", "counts": {"total": 10, "passed": 10, "failed": 0, "skipped": 0, "quarantined": 0},
  "skip_budget": {"allowed": 0, "exceptions": []},
  "run_url": "https://github.com/radicdotai/sample/actions/runs/1",
  "cloud_deploy": {"pipeline": "sample-rel", "release": "r-2026-11-03-1-1111111",
                    "rollout": "sample-rel-r-2026-11-03-1-1111111-to-sample-stage-0001",
                    "rollout_state": "SUCCEEDED", "verify": "pass"}
}
JSON

uv run radic-delivery gate evaluate --mode release-gate \
  --descriptor "$REPO/.radic/service.yml" --results-dir "$RESULTS" --digest "$DIGEST" \
  --format json
# {"mode": "release-gate", "overall": "pass",
#  "checks": [..., {"name": "stage_regression", "status": "pass", "detail": "..."}], ...}

# A different digest than any stored record — the record is missing
uv run radic-delivery gate evaluate --mode release-gate \
  --descriptor "$REPO/.radic/service.yml" --results-dir "$RESULTS" \
  --digest "sha256:0000000000000000000000000000000000000000000000000000000000000099" \
  --format json
# {"mode": "release-gate", "overall": "fail",
#  "checks": [..., {"name": "stage_regression", "status": "fail",
#  "detail": "no stage test-result record found for digest sha256:...99"}], ...}
# exit 3

# =========================================================================
# migrations check — needs a descriptor with migrations.enabled: true
# (python-sample above has no migrations block at all — enabled: false).
# tests/fixtures/migrations/descriptor.yml is a real, fully-valid
# descriptor (based on fastapi-backend's own real migrations config) with
# frozen_check_workflow_files added for this feature's own fixtures.
# =========================================================================
DESCRIPTOR=tests/fixtures/migrations/descriptor.yml

# --- migration_graph ---
uv run radic-delivery migrations check \
  --descriptor "$DESCRIPTOR" \
  --migrations-dir tests/fixtures/migrations/sound \
  --checks migration_graph --format json
# {"enabled": true, "migration_graph": {"sound": true, "root": "0001_initial.py", ...}, "ok": true}

uv run radic-delivery migrations check \
  --descriptor "$DESCRIPTOR" \
  --migrations-dir tests/fixtures/migrations/forked \
  --checks migration_graph --format json
# {"migration_graph": {"sound": false, "forks": [{"down_revision": "0001", "files": [...]}], ...}}
# exit 3

uv run radic-delivery migrations check \
  --descriptor "$DESCRIPTOR" \
  --migrations-dir tests/fixtures/migrations/cyclical \
  --checks migration_graph --format json
# {"migration_graph": {"sound": false, "cycles": [[...]], ...}}
# exit 3

# --- migrations_frozen ---
uv run radic-delivery migrations check \
  --descriptor "$DESCRIPTOR" --repo-dir . \
  --checks migrations_frozen --format json
# {"migrations_frozen": {"ok": true, "checks": [{"file": "...", "status": "intact", ...}]}}

sed 's/deploy-dev-intact.yml/deploy-dev-altered.yml/' "$DESCRIPTOR" > /tmp/migrations-descriptor-altered.yml
uv run radic-delivery migrations check \
  --descriptor /tmp/migrations-descriptor-altered.yml --repo-dir . \
  --checks migrations_frozen --format json
# {"migrations_frozen": {"ok": false, "checks": [{"status": "altered", ...}]}}
# exit 3

# A check requiring a live database connection is reported, never faked
uv run radic-delivery migrations check \
  --descriptor "$DESCRIPTOR" --repo-dir . \
  --checks alembic_check --format json
# {"alembic_check": "not_available", "ok": true}

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `gate evaluate --mode release-gate` — `0` on a full
pass, `3` if any check (including `stage_regression`) fails, `2` on an
invalid descriptor. `migrations check` — `0` when every actually-run
check passes (a requested-but-`not_available` check never fails it on its
own), `3` if `migrations_frozen` or `migration_graph` finds a real
problem, `2` on an invalid descriptor.
