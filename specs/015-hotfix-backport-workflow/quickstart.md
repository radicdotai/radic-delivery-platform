# Quickstart: Hotfix Backport Workflow

No live Jira/GitHub/GCP — real local git only.
`.github/workflows/hotfix-backport.yml` is validated statically only
(`actionlint`/`zizmor`) — this sandbox cannot execute it.

```bash
cd engine
uv sync

# =========================================================================
# release backport — clean case
# =========================================================================
REPO=/tmp/backport-demo
rm -rf "$REPO" && mkdir -p "$REPO" && cd "$REPO"
git init -q -b main
git -c user.email=t@e.com -c user.name=T commit -q --allow-empty -m "initial"

# simulate a hotfix already cut and merged to its own release branch
git checkout -q -b "release/2026.11.03-1-hf"
echo "fix" > fix.txt && git add fix.txt
git -c user.email=t@e.com -c user.name=T commit -q -m "RAD-1234 hotfix"
RELEASE_SHA=$(git rev-parse HEAD)
git checkout -q main

cat > /tmp/backport-manifest.json <<JSON
{
  "schema_version": 1, "release_id": "2026.11.03-1-hf", "kind": "hotfix", "status": "prod-deployed",
  "repo": "radicdotai/web-bff", "created_at": "2026-11-03T00:00:00Z", "initiator": "alice",
  "base": {"branch": "main", "sha": "$(git rev-parse HEAD)"},
  "release_branch": "release/2026.11.03-1-hf", "release_head": "$RELEASE_SHA",
  "selection": {
    "tickets": [{"key": "RAD-1234", "origin": "bot-proposal",
                 "commits": [{"dev_sha": "$RELEASE_SHA", "release_sha": "$RELEASE_SHA", "cherry_pick_x": true}]}],
    "held_back": []
  }
}
JSON

cd /path/to/radic-delivery-platform/engine
uv run radic-delivery release backport \
  --manifest /tmp/backport-manifest.json --repo-dir "$REPO" --into main --format json
# {"branch": "backport/2026.11.03-1-hf", "picked_commits": ["<RELEASE_SHA>"],
#  "conflicted_commits": [], "conflicts": false}
cd "$REPO" && git log --oneline backport/2026.11.03-1-hf | head -3
cd /path/to/radic-delivery-platform/engine

# =========================================================================
# release backport — one conflicting commit
# =========================================================================
REPO2=/tmp/backport-demo-conflict
rm -rf "$REPO2" && mkdir -p "$REPO2" && cd "$REPO2"
git init -q -b main
git -c user.email=t@e.com -c user.name=T commit -q --allow-empty -m "initial"
echo "original" > shared.txt && git add shared.txt
git -c user.email=t@e.com -c user.name=T commit -q -m "add shared file"

git checkout -q -b "release/2026.11.04-1-hf"
echo "hotfix version" > shared.txt && git add shared.txt
git -c user.email=t@e.com -c user.name=T commit -q -m "RAD-5555 conflicting hotfix"
CONFLICT_SHA=$(git rev-parse HEAD)
git checkout -q main
echo "main diverged" > shared.txt && git add shared.txt
git -c user.email=t@e.com -c user.name=T commit -q -m "unrelated main change"

cat > /tmp/backport-manifest-conflict.json <<JSON
{
  "schema_version": 1, "release_id": "2026.11.04-1-hf", "kind": "hotfix", "status": "prod-deployed",
  "repo": "radicdotai/web-bff", "created_at": "2026-11-04T00:00:00Z", "initiator": "alice",
  "base": {"branch": "main", "sha": "$(git rev-parse HEAD)"},
  "release_branch": "release/2026.11.04-1-hf", "release_head": "$CONFLICT_SHA",
  "selection": {
    "tickets": [{"key": "RAD-5555", "origin": "bot-proposal",
                 "commits": [{"dev_sha": "$CONFLICT_SHA", "release_sha": "$CONFLICT_SHA", "cherry_pick_x": true}]}],
    "held_back": []
  }
}
JSON

cd /path/to/radic-delivery-platform/engine
uv run radic-delivery release backport \
  --manifest /tmp/backport-manifest-conflict.json --repo-dir "$REPO2" --into main --format json
# {"branch": "backport/2026.11.04-1-hf", "picked_commits": [],
#  "conflicted_commits": ["<CONFLICT_SHA>"], "conflicts": true}
# exit 0 — the branch still exists, the conflict is named, never a crash

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/

# =========================================================================
# hotfix-backport.yml — static validation only (no live execution)
# =========================================================================
cd /path/to/radic-delivery-platform
actionlint .github/workflows/hotfix-backport.yml
uvx zizmor .github/workflows/hotfix-backport.yml
```

Expected exit codes: `release backport` — always `0` once the branch is
created, regardless of per-commit conflicts (`conflicts: true/false` in
the JSON output carries that fact); `4` if `--into` doesn't resolve or
the backport branch name already exists.
