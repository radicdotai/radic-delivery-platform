# Quickstart: Release Branch Creation and Cherry-Pick

No live Jira, no live GitHub, no live GCP — a real local git repo, a real
local manifest file, real `git cherry-pick`.

```bash
cd engine
uv sync

# --- Set up a repo with a production line and a diverging dev commit ---
REPO=/tmp/release-cut-demo
rm -rf "$REPO" && mkdir -p "$REPO" && cd "$REPO"
git init -q -b main
git commit -q --allow-empty -m "initial"
git checkout -q -b dev
echo "the fix" > fix.txt && git add fix.txt
git commit -q -m "RAD-1234: fix the thing"
SHA_A=$(git rev-parse HEAD)
git checkout -q main

# --- Write a change-note record for that commit (specs/007) ---
cd /path/to/radic-delivery-platform/engine
NOTES_DIR=/tmp/release-cut-demo-notes
uv run radic-delivery notes write --repo radicdotai/web-bff --sha "$SHA_A" \
  --type fix --audience customer --title "Fix the thing" --summary "Fixes it." \
  --jira-key RAD-1234 --out-dir "$NOTES_DIR"

# --- Hand-write a minimal, already-"proposed" manifest selecting that commit ---
cat > /tmp/release-cut-demo.json <<JSON
{
  "schema_version": 1, "release_id": "2026.11.03-1", "kind": "release",
  "status": "proposed", "repo": "radicdotai/web-bff",
  "created_at": "2026-11-03T00:00:00Z", "initiator": "alice",
  "base": {"branch": "dev", "sha": "$SHA_A"},
  "selection": {
    "tickets": [{"key": "RAD-1234", "origin": "bot-proposal", "commits": [{"dev_sha": "$SHA_A"}]}],
    "held_back": [], "non_jira_prs": []
  }
}
JSON

# --- Cut it for real ---
uv run radic-delivery release cut \
  --manifest /tmp/release-cut-demo.json --release-id 2026.11.03-1 \
  --repo-dir "$REPO" --change-notes-dir "$NOTES_DIR" --format json
# {"ok": true, "manifest": {"status": "cut", "release_branch": "release/2026.11.03-1",
#  "release_head": "<new sha>", "selection": {"tickets": [{"key": "RAD-1234",
#  "commits": [{"dev_sha": "<SHA_A>", "release_sha": "<new sha>", "cherry_pick_x": true}]}], ...}}}
cat /tmp/release-cut-demo.json   # updated in place

# --- A missing change-note record stops the cut before anything is touched ---
rm "$NOTES_DIR"/change-notes/radicdotai/web-bff/"$SHA_A".json
# (re-run against a fresh copy of the "proposed" manifest)
uv run radic-delivery release cut \
  --manifest /tmp/release-cut-demo.json --release-id 2026.11.03-1 \
  --repo-dir "$REPO" --change-notes-dir "$NOTES_DIR" --format json
# exit 2; {"ok": false, "reason": "missing_change_note", "failed_sha": "<SHA_A>", ...}

# --- A cherry-pick conflict aborts cleanly, leaving nothing behind ---
# (craft a repo where main and the selected commit both touch the same line
#  differently — see test_release_cut.py for the exact fixture)
# uv run radic-delivery release cut ... --format json
# exit 4; {"ok": false, "reason": "cherry_pick_conflict", "failed_sha": "<conflicting sha>", ...}
# `git branch --list "release/*"` shows nothing — no partial branch remains

# --- Preview without touching anything ---
uv run radic-delivery release cut \
  --manifest /tmp/release-cut-demo.json --release-id 2026.11.03-1 \
  --repo-dir "$REPO" --change-notes-dir "$NOTES_DIR" --dry-run --format json
# manifest on disk is unchanged; no branch created

# Quality gates for this feature itself
cd /path/to/radic-delivery-platform/engine
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `0` on a successful cut (or a clean `--dry-run`);
`2` if the manifest doesn't match `--release-id`/`--hotfix`, isn't in the
`proposed` status, or a selected commit is missing its change-note
record; `4` on a cherry-pick conflict or an unusable `--repo-dir`.
