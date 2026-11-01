# Quickstart: Release-Commands Reusable Workflow

No fixtures, no live GitHub App — this sandbox has no GitHub App
credentials or webhook delivery, so the end-to-end comment-to-reply loop
cannot run here (research.md D1). What *is* runnable end-to-end: the pure
`command`/`outcome`/reply-text mapping (via the existing CLI, additive
fields) and structural validation of the new/changed workflow YAML.

```bash
cd engine
uv sync

# Accepted command — note the three new additive fields alongside
# feature 005's existing classification/form/args/detail.
echo "/release remove RAD-123" | uv run radic-delivery release command \
  --author alice --release-managers alice,bob --tech-lead bob --format json
# {..., "workflow_command": "remove", "workflow_outcome": "applied", "reply_body": "..."}

# research_close — the flagged gap (research.md D2): workflow_command is
# "none" even though it was accepted, because the architecture's command
# enum has no slot for it; workflow_outcome still correctly says "applied".
echo "/research close" | uv run radic-delivery release command \
  --author alice --release-managers alice,bob --tech-lead bob --format json
# {..., "form": "research_close", "workflow_command": "none", "workflow_outcome": "applied", ...}

# not_a_command — reply_body is null; nothing would be posted.
echo "looks good to me!" | uv run radic-delivery release command \
  --author alice --release-managers alice,bob --tech-lead bob --format json
# {..., "classification": "not_a_command", "workflow_command": "none",
#  "workflow_outcome": "ignored", "reply_body": null}

# malformed — command is "none" (no form was ever recognized).
echo "/release add RAD-123" | uv run radic-delivery release command \
  --author alice --release-managers alice,bob --tech-lead bob --format json
# {..., "classification": "malformed", "workflow_command": "none", "workflow_outcome": "rejected", ...}

# unauthorized — command still names the attempted form.
echo "/release remove RAD-123" | uv run radic-delivery release command \
  --author eve --release-managers alice,bob --tech-lead bob --format json
# {..., "classification": "unauthorized", "workflow_command": "remove", "workflow_outcome": "rejected", ...}

# Quality gates for the engine change
uv run pytest -q
uv run ruff check .
uv run mypy src/

# Structural validation of the new/changed GitHub Actions YAML (run from repo root)
cd ..
actionlint .github/workflows/release-commands.yml .github/workflows/engine-ci.yml
uvx zizmor .github/workflows/release-commands.yml actions/post-release-command-reply/action.yml templates/callers/release.yml
```

Expected: every `actionlint`/`zizmor` invocation above exits clean — in
particular, `zizmor` must report no script-injection finding against the
new composite action or workflow, since the comment body and the reply
text are only ever passed as typed inputs/file contents, never
interpolated into a `run:` shell string (research.md D1/D5).
