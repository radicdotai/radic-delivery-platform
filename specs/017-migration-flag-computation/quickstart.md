# Quickstart: Migration Flag Computation

Validates the feature end-to-end against a real local git repository —
no GCP, Docker, or live Jira/GitHub call anywhere.

## Prerequisites

```bash
cd engine && uv sync
```

## Setup: a real throwaway git repo

```bash
WORKDIR=$(mktemp -d) && cd "$WORKDIR"
git init -q && git config user.email t@t.com && git config user.name t
mkdir -p migrations/versions migrations/legacy
echo "root" > README.md && git add -A && git commit -q -m "init"
BASE=$(git rev-parse HEAD)
```

## Scenario 1 — no migration added → `none`

```bash
echo "unrelated change" >> README.md && git commit -qam "unrelated"
HEAD=$(git rev-parse HEAD)
uv run --project "$ENGINE_PROJECT" python -c "
from pathlib import Path
from radic_delivery.notes.migration_flag import compute
print(compute(Path('.'), '$BASE', '$HEAD'))
"
# Expected: none
```

**Note**: `git checkout -b <branch> "$BASE"` can prune the empty
`migrations/versions/`/`migrations/legacy/` directories created in Setup
once they've been populated-then-abandoned on a sibling branch (git
doesn't track empty directories, and cleans one up on checkout once it
has nothing left tracked in it). Each scenario below runs `mkdir -p`
immediately before writing, rather than relying on the directory still
being there from Setup.

## Scenario 2 — expand-phase migration added → `expand`

```bash
git checkout -q -b expand "$BASE"
mkdir -p migrations/versions
cat > migrations/versions/0001_expand.py <<'EOF'
revision = "0001"
down_revision = None
EOF
git add -A && git commit -q -m "add expand migration"
HEAD=$(git rev-parse HEAD)
# compute(repo_dir, BASE, HEAD) -> "expand"
```

## Scenario 3 — contract-phase migration added → `contract`

```bash
git checkout -q -b contract "$BASE"
mkdir -p migrations/versions
cat > migrations/versions/0002_contract.py <<'EOF'
# phase: contract
revision = "0002"
down_revision = "0001"
EOF
git add -A && git commit -q -m "add contract migration"
HEAD=$(git rev-parse HEAD)
# compute(repo_dir, BASE, HEAD) -> "contract"
```

## Scenario 4 — legacy directory excluded

```bash
git checkout -q -b legacy "$BASE"
mkdir -p migrations/legacy
cat > migrations/legacy/0099_old.py <<'EOF'
# phase: contract
revision = "0099"
EOF
git add -A && git commit -q -m "add legacy-dir file"
HEAD=$(git rev-parse HEAD)
# compute(repo_dir, BASE, HEAD) -> "none" (the legacy file is excluded entirely)
```

## Scenario 5 — mixed PR, expand + contract → `contract` wins

```bash
git checkout -q -b mixed "$BASE"
mkdir -p migrations/versions
cat > migrations/versions/0001_expand.py <<'EOF'
revision = "0001"
down_revision = None
EOF
cat > migrations/versions/0002_contract.py <<'EOF'
# phase: contract
revision = "0002"
down_revision = "0001"
EOF
git add -A && git commit -q -m "mixed migration PR"
HEAD=$(git rev-parse HEAD)
# compute(repo_dir, BASE, HEAD) -> "contract"
```

## Scenario 6 — `phase_header_required=False` always yields `expand`

```bash
# Reuse the "contract" branch's commit from Scenario 3.
# compute(repo_dir, BASE, HEAD, phase_header_required=False) -> "expand"
# (detection is never attempted in this mode, even though the file
#  literally carries the marker)
```

## Scenario 7 — `notes write` CLI: migration is computed, not supplied

```bash
uv run --project "$ENGINE_PROJECT" radic-delivery notes write \
  --repo radicdotai/fastapi-backend --sha "$(printf '%040d' 1)" \
  --type feature --audience internal --title "Add widgets table" \
  --summary "Adds the widgets table (expand phase)." --jira-key RAD-1 \
  --repo-dir . --base "$BASE" --head "$HEAD" \
  --format json
# Expected: record.migration == "expand" (or "contract"/"none" per the
# branch checked out), computed — never a --migration flag to pass.
```

## Scenario 8 — `notes check` CLI: PR-body mismatch fails closed

```bash
echo "Jira: RAD-1
Migrations: none" > /tmp/pr-body.txt

uv run --project "$ENGINE_PROJECT" radic-delivery notes check \
  --pr-body-file /tmp/pr-body.txt \
  --repo-dir . --base "$BASE" --head "$HEAD" \
  --format json
# Expected (on the "contract"/"expand" branches): the migration check
# reports passed: false, naming the mismatch between the declared "none"
# and the real computed value. Omitting --repo-dir/--base/--head entirely
# skips the migration check and preserves today's Jira-only behavior.
```

## Final validation

```bash
cd engine
uv run pytest -q
uv run ruff check .
uv run mypy src/
uv run python -c "import json, jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('../schemas/change-note.schema.json')))"
```
