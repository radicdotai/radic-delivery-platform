# Quickstart: Release Cut Workflow

No live Jira/GitHub/GCP — real local git, real local manifest/change-note
files. `.github/workflows/release-cut.yml` itself is validated statically
only (`actionlint`/`zizmor`) — this sandbox cannot execute it.

```bash
cd engine
uv sync

# =========================================================================
# release render-pr-body
# =========================================================================
REPO=/tmp/rpb-demo
rm -rf "$REPO" && mkdir -p "$REPO" && cd "$REPO"
git init -q -b main
git -c user.email=t@e.com -c user.name=T commit -q --allow-empty -m "initial"
BASE_SHA=$(git rev-parse HEAD)

mkdir -p change-notes/radicdotai/web-bff
cat > change-notes/radicdotai/web-bff/1111111111111111111111111111111111111111.json <<'JSON'
{
  "schema_version": 1, "repo": "radicdotai/web-bff", "sha": "1111111111111111111111111111111111111111",
  "type": "fix", "audience": "customer", "title": "Return a clear error when the upstream is unavailable",
  "summary": "...", "jira_key": "RAD-1234"
}
JSON

cat > /tmp/rpb-manifest.json <<JSON
{
  "schema_version": 1, "release_id": "2026.11.03-1", "kind": "release", "status": "proposed",
  "repo": "radicdotai/web-bff", "created_at": "2026-11-03T00:00:00Z", "initiator": "alice",
  "base": {"branch": "dev", "sha": "$BASE_SHA"},
  "selection": {
    "tickets": [{"key": "RAD-1234", "origin": "bot-proposal",
                 "commits": [{"dev_sha": "1111111111111111111111111111111111111111"}]}],
    "held_back": []
  }
}
JSON

cd /path/to/radic-delivery-platform/engine
uv run radic-delivery release render-pr-body \
  --manifest /tmp/rpb-manifest.json --change-notes-dir "$REPO" --repo-dir "$REPO" \
  --format text
# ## Release 2026.11.03-1 (repo: radicdotai/web-bff)
# ...
# | RAD-1234 | Return a clear error when the upstream is unavailable | fix | 1 | bot-proposal | pass |
# ...
# - [ ] Release PR approved by one person who is not the initiator
# ...

# Rendering twice produces byte-identical output
diff \
  <(uv run radic-delivery release render-pr-body --manifest /tmp/rpb-manifest.json --change-notes-dir "$REPO" --repo-dir "$REPO") \
  <(uv run radic-delivery release render-pr-body --manifest /tmp/rpb-manifest.json --change-notes-dir "$REPO" --repo-dir "$REPO")
echo "exit=$?"  # 0 — identical

# A manifest recording a real approval checks that gate item
python3 -c "
import json
m = json.load(open('/tmp/rpb-manifest.json'))
m['approvals'] = {'release_pr': {'number': 42, 'approver': 'bob'}}
json.dump(m, open('/tmp/rpb-manifest-approved.json', 'w'))
"
uv run radic-delivery release render-pr-body \
  --manifest /tmp/rpb-manifest-approved.json --change-notes-dir "$REPO" --repo-dir "$REPO" \
  --format text | grep "Release PR approved"
# - [x] Release PR approved by one person who is not the initiator

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/

# =========================================================================
# release-cut.yml — static validation only (no live execution)
# =========================================================================
cd /path/to/radic-delivery-platform
actionlint .github/workflows/release-cut.yml templates/callers/release.yml
uvx zizmor .github/workflows/release-cut.yml templates/callers/release.yml
```

Expected exit codes: `release render-pr-body` — always `0` on a readable
manifest (rendering never fails on an incomplete-but-valid manifest
state; it renders "not yet determinable"/"TBD" for whatever isn't
present yet), `2` if the manifest itself can't be read or is missing a
required top-level field (`release_id`/`kind`/`status`/`repo`/
`initiator`/`base`/`selection`).
