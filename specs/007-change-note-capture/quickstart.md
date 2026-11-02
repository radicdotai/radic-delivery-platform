# Quickstart: Change-Note Record Capture and Release-Note Gate

No live GitHub/GCS dependency — a local write, real schema validation,
real text parsing.

```bash
cd engine
uv sync

# A complete, valid change-note record
uv run radic-delivery notes write \
  --repo radicdotai/web-bff --sha 2222222222222222222222222222222222222222 \
  --pr 123 --type fix --audience customer \
  --title "Return a clear error when the upstream is unavailable" \
  --summary "The BFF now answers 503 with a retry hint instead of a generic 500." \
  --jira-key RAD-1234 --author example-user \
  --out-dir /tmp/notes-demo --format json
# {"ok": true, "local_path": "/tmp/notes-demo/change-notes/radicdotai/web-bff/2222....json",
#  "upload_status": "not_available", ...}

# The explicit "no Jira ticket" escape hatch
uv run radic-delivery notes write \
  --repo radicdotai/web-bff --sha 8888888888888888888888888888888888888888 \
  --pr 142 --type chore --audience none \
  --title "Bump the HTTP client library" --summary "Routine dependency bump." \
  --jira-key None --out-dir /tmp/notes-demo --format json
# {"ok": true, ...} — "None" is accepted, not rejected

# An invalid record (bad type)
uv run radic-delivery notes write \
  --repo radicdotai/web-bff --sha 2222222222222222222222222222222222222222 \
  --type not-a-real-type --audience customer --title x --summary x --jira-key RAD-1 \
  --out-dir /tmp/notes-demo --format json
# exit 2; {"ok": false, "issues": [{"path": "type", "message": "..."}]}

# A PR body with a Jira reference — passes
printf 'Kind: fix\nJira: RAD-1234\n\nFixes the thing.\n' > /tmp/pr-body-with-key.txt
uv run radic-delivery notes check --pr-body-file /tmp/pr-body-with-key.txt --format json
# {"classification": "has_jira_key", "jira_key": "RAD-1234", "passed": true, ...}

# A PR body with the explicit opt-out — passes
printf 'Kind: chore\nJira: None\n\nDependency bump.\n' > /tmp/pr-body-none.txt
uv run radic-delivery notes check --pr-body-file /tmp/pr-body-none.txt --format json
# {"classification": "explicit_none", "passed": true, ...}

# A PR body with neither — warns (not blocking by default)
printf 'Just a quick fix, no ticket.\n' > /tmp/pr-body-incomplete.txt
uv run radic-delivery notes check --pr-body-file /tmp/pr-body-incomplete.txt --format json
# exit 0; {"classification": "incomplete", "passed": true, "blocking": false, "detail": "..."}

# The same incomplete body, now blocking
uv run radic-delivery notes check --pr-body-file /tmp/pr-body-incomplete.txt --require-jira-key --format json
# exit 3; {"classification": "incomplete", "passed": false, "blocking": true, "detail": "..."}

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `notes write` — `0` success, `2` invalid record.
`notes check` — `0` whenever not blocking, or when complete; `3` only when
`--require-jira-key` is set and the body is incomplete.
