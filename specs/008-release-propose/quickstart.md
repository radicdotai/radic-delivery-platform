# Quickstart: Release Selection and Draft Manifest

No live Jira, no live `delivery-records`, no live GCS — a real local git
repo, real local change-note records, real schema validation.

```bash
cd engine
uv sync

# --- Set up a tiny real git repo with two commits ---
REPO=/tmp/release-propose-demo/web-bff
rm -rf /tmp/release-propose-demo && mkdir -p "$REPO" && cd "$REPO"
git init -q -b dev
git commit -q --allow-empty -m "RAD-1234: fix the thing"
SHA_A=$(git rev-parse HEAD)
git commit -q --allow-empty -m "add http client bump (no ticket)"
SHA_B=$(git rev-parse HEAD)

# --- Write change-note records for both commits (specs/007) ---
cd /path/to/radic-delivery-platform/engine
NOTES_DIR=/tmp/release-propose-demo/notes
uv run radic-delivery notes write --repo radicdotai/web-bff --sha "$SHA_A" \
  --type fix --audience customer --title "Fix the thing" --summary "Fixes it." \
  --jira-key RAD-1234 --out-dir "$NOTES_DIR"
uv run radic-delivery notes write --repo radicdotai/web-bff --sha "$SHA_B" \
  --pr 142 --type chore --audience none --title "Bump HTTP client" \
  --summary "Dependency bump." --jira-key None --out-dir "$NOTES_DIR"

# --- Propose a release: RAD-1234 is ready, PR 142 is explicitly included ---
uv run radic-delivery release propose \
  --repo radicdotai/web-bff --base dev --repo-dir "$REPO" \
  --change-notes-dir "$NOTES_DIR" --tickets RAD-1234 --non-jira-prs 142 \
  --initiator alice \
  --dry-run --format json
# {"ok": true, "manifest": {"release_id": "<today>-1", "status": "proposed",
#  "selection": {"tickets": [{"key": "RAD-1234", "origin": "bot-proposal",
#  "commits": [{"dev_sha": "<SHA_A>"}]}], "held_back": [],
#  "non_jira_prs": [{"pr": 142, "reason": "MISSING", "second_approver": null,
#  "commits": [{"dev_sha": "<SHA_B>"}]}]}, ...}, "issues": []}

# --- The same repo, but RAD-1234 is NOT listed as ready ---
uv run radic-delivery release propose \
  --repo radicdotai/web-bff --base dev --repo-dir "$REPO" \
  --change-notes-dir "$NOTES_DIR" --initiator alice --dry-run --format json
# selection.tickets is empty; selection.held_back contains
# {"key": "RAD-1234", "reason": "not Ready for Review"}

# --- A commit explicitly marked dev-green-failed is held back for that reason ---
uv run radic-delivery release propose \
  --repo radicdotai/web-bff --base dev --repo-dir "$REPO" \
  --change-notes-dir "$NOTES_DIR" --tickets RAD-1234 \
  --dev-green-failed "$SHA_A" --initiator alice --dry-run --format json
# held_back: {"key": "RAD-1234", "reason": "dev-green check failed for commit <SHA_A>"}

# --- Without --dry-run, the manifest is also written locally ---
uv run radic-delivery release propose \
  --repo radicdotai/web-bff --base dev --repo-dir "$REPO" \
  --change-notes-dir "$NOTES_DIR" --tickets RAD-1234 --out-dir /tmp/release-propose-demo \
  --initiator alice --format json
cat /tmp/release-propose-demo/releases/*.json

# Quality gates for this feature itself
cd /path/to/radic-delivery-platform/engine
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `0` on a successfully produced proposal (whether
anything was proposed or everything was held back — an empty-but-valid
proposal is still success); `2` if a change-note record can't be parsed
or the constructed manifest fails schema validation; `4` if `--repo-dir`
isn't a git repository or `--base` doesn't resolve.
