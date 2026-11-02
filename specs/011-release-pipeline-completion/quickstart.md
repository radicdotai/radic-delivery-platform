# Quickstart: Release Pipeline Completion

No live Jira/GitHub/GCP — real local git repos, real local manifest
files, one pure computation.

```bash
cd engine
uv sync

# =========================================================================
# release verify-promotion
# =========================================================================
REPO=/tmp/vp-demo
rm -rf "$REPO" && mkdir -p "$REPO" && cd "$REPO"
git init -q -b main
git commit -q --allow-empty -m "initial"
BASE_SHA=$(git rev-parse HEAD)
git checkout -q -b "release/2026.11.03-1"
echo "fix" > fix.txt && git add fix.txt
git -c user.email=t@e.com -c user.name=T commit -q -m "RAD-1234 cherry-pick"
RELEASE_HEAD=$(git rev-parse HEAD)
git tag build-2026.11.03-1 "$RELEASE_HEAD"
git checkout -q main

cat > /tmp/vp-manifest.json <<JSON
{
  "schema_version": 1, "release_id": "2026.11.03-1", "kind": "release", "status": "stage-deployed",
  "repo": "radicdotai/web-bff", "created_at": "2026-11-03T00:00:00Z", "initiator": "alice",
  "base": {"branch": "dev", "sha": "$BASE_SHA"},
  "selection": {"tickets": [], "held_back": [], "non_jira_prs": []}
}
JSON

cd /path/to/radic-delivery-platform/engine
uv run radic-delivery release verify-promotion \
  --manifest /tmp/vp-manifest.json --repo-dir "$REPO" \
  --release-head "$RELEASE_HEAD" --expected-tag build-2026.11.03-1 \
  --image us-central1-docker.pkg.dev/radicai/radic-web-bff/web-bff \
  --digest sha256:0000000000000000000000000000000000000000000000000000000000000001 \
  --format json
# {"ok": true, "ancestry_verified": true, "tree_verified": true, "tag_verified": true,
#  "release_digest_equals_stage_digest": "not_available", "detail": []}

# A missing/wrong expected tag fails the tag check specifically
uv run radic-delivery release verify-promotion \
  --manifest /tmp/vp-manifest.json --repo-dir "$REPO" --release-head "$RELEASE_HEAD" \
  --expected-tag no-such-tag \
  --image us-central1-docker.pkg.dev/radicai/radic-web-bff/web-bff \
  --digest sha256:0000000000000000000000000000000000000000000000000000000000000001 \
  --format json
# exit 3; "tag_verified": false

# =========================================================================
# release finalise
# =========================================================================
cat > /tmp/finalise-manifest.json <<JSON
{
  "schema_version": 1, "release_id": "2026.11.03-1", "kind": "release", "status": "prod-deployed",
  "repo": "radicdotai/web-bff", "created_at": "2026-11-03T00:00:00Z", "initiator": "alice",
  "base": {"branch": "dev", "sha": "$BASE_SHA"}, "release_branch": "release/2026.11.03-1",
  "release_head": "$RELEASE_HEAD",
  "selection": {"tickets": [], "held_back": [], "non_jira_prs": []}
}
JSON
uv run radic-delivery release finalise \
  --manifest /tmp/finalise-manifest.json --release-id 2026.11.03-1 \
  --prod-digest sha256:0000000000000000000000000000000000000000000000000000000000000001 \
  --repo-dir "$REPO" --format json
# {"ok": true, "tag": "v1.0.0", "manifest": {"status": "finalised",
#  "main": {"fast_forwarded_to": "<RELEASE_HEAD>", "at": "...", "tag": "v1.0.0"}, ...}}
cd "$REPO" && git log --oneline -1 main && git tag --list
cd /path/to/radic-delivery-platform/engine

# Finalising again is refused — already finalised
uv run radic-delivery release finalise \
  --manifest /tmp/finalise-manifest.json --release-id 2026.11.03-1 \
  --prod-digest sha256:0000000000000000000000000000000000000000000000000000000000000001 \
  --repo-dir "$REPO" --format json
# exit 2; {"ok": false, "reason": "status_mismatch", ...}

# =========================================================================
# rollback plan
# =========================================================================
uv run radic-delivery rollback plan \
  --env prod --current-release r-2026-11-03-1-4444444 \
  --current-digest sha256:0000000000000000000000000000000000000000000000000000000000000003 \
  --target-release r-2026-10-20-1-aaaaaaa \
  --target-digest sha256:0000000000000000000000000000000000000000000000000000000000000004 \
  --estimated-minutes 6 --format json
# {"environment": "prod", "current_release": "r-2026-11-03-1-4444444", ...,
#  "estimated_minutes": 6, "migrations_reverted": false, "no_op": false}

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `release verify-promotion` — `0` if all three real
checks pass, `3` if any fails, `4` on an unusable `--repo-dir`/commit.
`release finalise` — `0` on success, `2` on a manifest/status/digest
mismatch, `4` if `main` isn't actually a fast-forward ancestor of
`release_head`. `rollback plan` — always `0`.
