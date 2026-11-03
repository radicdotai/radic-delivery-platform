# Quickstart: CI Tooling Completion

No live Jira/GitHub/GCP — real local test fixtures, real local JSON
files.

```bash
cd engine
uv sync

# =========================================================================
# tests inventory — a clean, fully-passing service
# =========================================================================
uv run radic-delivery tests inventory \
  --repo-dir tests/fixtures/sample-repos/python-sample \
  --format json
# {"launched": true, "suite": "unit", "total": 2, "passed": 2, "failed": 0,
#  "skipped": 0, "quarantined_active": 0, "quarantined_expired": 0,
#  "within_quarantine_share_cap": true, "detail": ""}

# A service with a deliberately skipped test
uv run radic-delivery tests inventory \
  --repo-dir tests/fixtures/sample-repos/python-sample-broken-skip \
  --format json
# {"launched": true, "suite": "unit", "total": 3, "passed": 2, "failed": 0,
#  "skipped": 1, ...}

# With a quarantine ledger naming one of this service's tests
cat > /tmp/quarantine.yml <<'YAML'
schema_version: 1
quarantine:
  - service: sample
    test_id: "tests/test_sample.py::test_add_again"
    reason: "flaky under parallel CI runners"
    jira_key: RAD-9001
    quarantined_since: "2026-10-30"
YAML
uv run radic-delivery tests inventory \
  --repo-dir tests/fixtures/sample-repos/python-sample-broken-skip \
  --quarantine-file /tmp/quarantine.yml --as-of 2026-11-03 \
  --format json
# "quarantined_active": 1, "quarantined_expired": 0 (2026-10-30 + 7 days > 2026-11-03)

uv run radic-delivery tests inventory \
  --repo-dir tests/fixtures/sample-repos/python-sample-broken-skip \
  --quarantine-file /tmp/quarantine.yml --as-of 2026-11-10 \
  --format json
# "quarantined_active": 0, "quarantined_expired": 1 (past the 7-day window)

# =========================================================================
# policy rulesets-diff
# =========================================================================
cd /path/to/radic-delivery-platform

# A live state that matches the committed rulesets/ exactly (drop the
# GitHub-assigned fields a committed file never has) — no drift
python3 -c "
import json
rulesets = []
for name in ['dev-trunk', 'main-prod-line', 'release-branches', 'product-tags', 'platform-tags']:
    body = json.load(open(f'rulesets/{name}.json'))
    rulesets.append({**body, 'id': 1000, 'node_id': 'RS_x', 'created_at': '2026-01-01T00:00:00Z'})
json.dump(rulesets, open('/tmp/live-no-drift.json', 'w'))
"
cd engine
uv run radic-delivery policy rulesets-diff \
  --repo radicdotai/web-bff --dir ../rulesets --live-file /tmp/live-no-drift.json \
  --format json
# {"ok": true, "unchanged": ["dev-trunk","main-prod-line","platform-tags","product-tags",
#  "release-branches"], "missing_from_live": [], "added_in_live": [], "changed": []}
# (rulesets-diff doesn't itself know which of the five rulesets are expected to apply
#  to which --repo — research.md D4 — so comparing against all five committed files
#  regardless of --repo is a deliberate simplification, not a gap)

# A live state missing one ruleset, with another changed and one extra
python3 -c "
import json
dev = json.load(open('../rulesets/dev-trunk.json'))
dev['rules'] = [r for r in dev['rules'] if r['type'] != 'non_fast_forward']
rulesets = [dev, {'name': 'unexpected-extra', 'target': 'branch', 'enforcement': 'active',
                   'conditions': {}, 'bypass_actors': [], 'rules': []}]
json.dump(rulesets, open('/tmp/live-with-drift.json', 'w'))
"
uv run radic-delivery policy rulesets-diff \
  --repo radicdotai/web-bff --dir ../rulesets --live-file /tmp/live-with-drift.json \
  --format json
# {"ok": false, "missing_from_live": ["main-prod-line","platform-tags","product-tags",
#  "release-branches"], "added_in_live": ["unexpected-extra"],
#  "changed": [{"name": "dev-trunk", "detail": "rules differ"}]}

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `tests inventory` — `0` whenever the descriptor's
unit-test command actually ran (regardless of pass/fail/skip/quarantine
facts); `2` if the descriptor itself fails validation; `4` if the test
command could not be launched at all. `policy rulesets-diff` — `0`
whenever both inputs were read and compared (drift or not); `2` if the
committed `--dir` has two files with the same ruleset `name`; `4` if
`--dir`/`--live-file` can't be read or `--live-file` isn't valid JSON.
