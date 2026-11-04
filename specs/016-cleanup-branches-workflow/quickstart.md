# Quickstart: Cleanup Workflow (branches scope only)

## Prerequisites

```bash
cd engine && uv sync
```

## Demo: `radic-delivery cleanup branches`

```bash
rm -rf /tmp/cleanup-demo && mkdir /tmp/cleanup-demo && cd /tmp/cleanup-demo
git init -q -b main
git config user.email demo@radic.ai && git config user.name demo

echo a > f.txt && git add f.txt && git commit -q -m "initial"

# A release branch, later fast-forwarded into main (= "merged"), aged
# past the retention window by backdating its commit (an explicit ISO
# date — not every git build's --date parses relative strings like
# "30 days ago").
git checkout -q -b release/2026.09.01-1
echo b > f.txt && git commit -q -am "release commit"
GIT_COMMITTER_DATE="2026-10-05T00:00:00" git commit -q --amend --no-edit \
  --date="2026-10-05T00:00:00"
git checkout -q main
git merge -q --ff-only release/2026.09.01-1   # main now past the release branch's tip

# A second release branch, merged but recent (inside the retention window).
git checkout -q -b release/2026.11.01-1
echo c > f.txt && git commit -q -am "recent release commit"
git checkout -q main
git merge -q --ff-only release/2026.11.01-1

# A third release branch, never merged into main.
git checkout -q -b release/2026.11.04-1
echo d > f.txt && git commit -q -am "unmerged release commit"
git checkout -q main

# Dry run (the default) — reports what would happen, deletes nothing.
uv run --project /path/to/engine radic-delivery cleanup branches \
  --repo-dir /tmp/cleanup-demo --retention-days 14 --format json
```

Expected (dry run): `deleted: ["release/2026.09.01-1"]` (named exactly as
it would be in a real run, per spec Acceptance Scenario 5 — dry-run only
suppresses the actual `git branch -D`, never the reporting); `kept` lists
`release/2026.11.01-1` as `too_recent` and `release/2026.11.04-1` as
`not_yet_merged`; `dry_run: true`. Confirm with `git -C /tmp/cleanup-demo
branch` that `release/2026.09.01-1` still exists after the dry run.

```bash
# Real run.
uv run --project /path/to/engine radic-delivery cleanup branches \
  --repo-dir /tmp/cleanup-demo --retention-days 14 --no-dry-run --format json
git -C /tmp/cleanup-demo branch   # confirm release/2026.09.01-1 is gone; main, the other two remain
```

Expected (real run): `deleted: ["release/2026.09.01-1"]`; `kept` lists the
other two with the same reasons as above; `dry_run: false`.

## Validating `.github/workflows/cleanup.yml`

```bash
actionlint .github/workflows/cleanup.yml
uvx zizmor .github/workflows/cleanup.yml
```

Expect zero error/warning findings from both.
