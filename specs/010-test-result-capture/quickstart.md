# Quickstart: Test-Result Record Capture

No live Jira/GitHub/GCP — real local file read/write, real schema
validation.

```bash
cd engine
uv sync

# --- A complete, valid stage-environment record ---
cat > /tmp/result-stage.json <<JSON
{
  "schema_version": 1,
  "repo": "radicdotai/frontend-v2",
  "environment": "stage",
  "release_id": "2026.11.03-1",
  "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000001",
  "commit": "1111111111111111111111111111111111111111",
  "suite": "e2e-full-stage",
  "runner": "playwright",
  "scope": "full",
  "started_at": "2026-11-03T09:12:04Z",
  "finished_at": "2026-11-03T09:38:51Z",
  "result": "pass",
  "counts": {"total": 14, "passed": 14, "failed": 0, "skipped": 0, "quarantined": 0},
  "skip_budget": {"allowed": 0, "exceptions": []},
  "run_url": "https://github.com/radicdotai/frontend-v2/actions/runs/1",
  "cloud_deploy": {
    "pipeline": "frontend-rel", "target": "frontend-stage", "release": "r-2026-11-03-1-1111111",
    "rollout": "frontend-rel-r-2026-11-03-1-1111111-to-frontend-stage-0001",
    "rollout_state": "SUCCEEDED", "verify": "pass"
  }
}
JSON
uv run radic-delivery records put-test-result \
  --file /tmp/result-stage.json --release-id 2026.11.03-1 --out-dir /tmp/records-demo --format json
# {"ok": true, "result": "pass",
#  "local_path": "/tmp/records-demo/releases/2026.11.03-1/test-results/stage-frontend-v2-e2e-full-stage.json",
#  "upload_status": "not_available", "issues": []}

# --- A dev-environment record with no release_id at all — still accepted ---
cat > /tmp/result-dev.json <<JSON
{
  "schema_version": 1, "repo": "radicdotai/web-bff", "environment": "dev", "release_id": null,
  "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000002",
  "commit": "2222222222222222222222222222222222222222", "suite": "unit", "runner": "pytest",
  "scope": "regression", "started_at": "2026-11-03T09:00:00Z", "finished_at": "2026-11-03T09:01:00Z",
  "result": "pass", "counts": {"total": 5, "passed": 5, "failed": 0, "skipped": 0, "quarantined": 0},
  "skip_budget": {"allowed": 0, "exceptions": []}, "run_url": "https://example/run/2",
  "cloud_deploy": {
    "pipeline": "web-bff-dev", "release": "d-2222222-418",
    "rollout": "web-bff-dev-to-web-bff-dev-0001", "rollout_state": "SUCCEEDED", "verify": "pass"
  }
}
JSON
uv run radic-delivery records put-test-result \
  --file /tmp/result-dev.json --out-dir /tmp/records-demo --format json
# local_path under .../releases/dev/test-results/dev-web-bff-unit.json

# --- A run that skipped a test but claims an overall pass — rejected ---
python3 -c "
import json
r = json.load(open('/tmp/result-dev.json'))
r['counts']['skipped'] = 1
json.dump(r, open('/tmp/result-skip-bad.json', 'w'))
"
uv run radic-delivery records put-test-result --file /tmp/result-skip-bad.json --out-dir /tmp/records-demo --format json
# exit 2; {"ok": false, "issues": [...]}; nothing written

# --- A stage record missing scope: "full" — rejected ---
python3 -c "
import json
r = json.load(open('/tmp/result-stage.json'))
del r['scope']
json.dump(r, open('/tmp/result-stage-bad.json', 'w'))
"
uv run radic-delivery records put-test-result --file /tmp/result-stage-bad.json --release-id 2026.11.03-1 --out-dir /tmp/records-demo --format json
# exit 2; rejected, naming the missing scope requirement

# --- --release-id mismatch — rejected, nothing stored ---
uv run radic-delivery records put-test-result --file /tmp/result-stage.json --release-id 2099.01.01-9 --out-dir /tmp/records-demo --format json
# exit 2; {"ok": false, "issues": [{"path": "(root)", "message": "..."}]}

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `0` on acceptance; `2` on any validation failure
(schema violation, skip-budget rule, stage-completeness rule, or a
`--release-id` mismatch) — nothing is ever stored in that case.
