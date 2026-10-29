# Quickstart: Release Slash-Command Parser and Authorization Check

No fixtures, no external tools — pure text in, structured result out.

```bash
cd engine
uv sync

# A valid, authorized command (stdin)
echo "/release remove RAD-123" | uv run radic-delivery release command \
  --author alice --release-managers alice,bob --tech-lead bob --format json

# An ordinary comment — classified as not_a_command, not an error
echo "looks good to me!" | uv run radic-delivery release command \
  --author alice --release-managers alice,bob --tech-lead bob --format text

# A malformed attempt — recognized leading shape, missing reason
echo "/release add RAD-123" | uv run radic-delivery release command \
  --author alice --release-managers alice,bob --tech-lead bob --format text

# An unauthorized author
echo "/release remove RAD-123" | uv run radic-delivery release command \
  --author eve --release-managers alice,bob --tech-lead bob --format text

# The Tech-Lead-only command from a release manager who isn't the Tech Lead
echo "/release waive dev-green reason: ci is flaky today" | \
  uv run radic-delivery release command \
  --author alice --release-managers alice,bob --tech-lead bob --format text

# From a file instead of stdin
printf '/research close\n' > /tmp/comment.txt
uv run radic-delivery release command --comment-file /tmp/comment.txt \
  --author alice --release-managers alice,bob --tech-lead bob

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `0` for `not_a_command` and `accepted`, `2` for
`malformed`, `3` for `unauthorized`.
