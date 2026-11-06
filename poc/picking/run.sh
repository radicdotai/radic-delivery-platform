#!/usr/bin/env bash
set -euo pipefail

SANDBOX=${1:?usage: run.sh <path-to-operations-console-cdpoc checkout>}
HERE=$(cd "$(dirname "$0")" && pwd)
ENGINE="uv run --project $HERE/../../engine radic-delivery"
REPO=radicdotai/operations-console-cdpoc
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

notes() {
  local dir=$1
  git -C "$dir" log --reverse --format='%H%x09%s' main..dev | while IFS=$'\t' read -r sha subject; do
    key=${subject%%:*}
    mig=--no-migration
    git -C "$dir" show --name-only --format= "$sha" | grep -q '^migrations/' && mig=--migration
    $ENGINE notes write --repo "$REPO" --sha "$sha" --type fix --audience internal --title "${subject#*: }" \
      --summary "PoC ticket" --jira-key "$key" $mig --out-dir "$dir/.notes" --format json >/dev/null
  done
}

scenario() {
  local name=$1 tickets=$2 rid=$3 dir="$WORK/$1"
  git clone -q "$SANDBOX" "$dir"
  git -C "$dir" checkout -q -B main origin/main && git -C "$dir" checkout -q -B dev origin/dev
  notes "$dir"
  echo "== $name: ready tickets $tickets"
  (cd "$dir" && $ENGINE release propose --repo "$REPO" --base dev --change-notes-dir .notes --tickets "$tickets" \
    --release-id "$rid" --initiator poc --out-dir .notes --format json) > "$dir/propose.json" || true
  jq -c '{proposed: [.manifest.selection.tickets[].key], held_back: [.manifest.selection.held_back[] | "\(.key): \(.reason)"]}' "$dir/propose.json"
  manifest=$(find "$dir/.notes" -name '*.json' -path '*release*' | head -1)
  set +e
  (cd "$dir" && $ENGINE release cut --manifest "$manifest" --release-id "$rid" --change-notes-dir .notes --format json) > "$dir/cut.json"
  echo "cut exit=$?"
  set -e
  jq -c '{ok, status: .manifest.status, issues}' "$dir/cut.json"
  if git -C "$dir" rev-parse -q --verify "release/$rid" >/dev/null; then
    git -C "$dir" checkout -q "release/$rid"
    echo "release branch: $(git -C "$dir" log --format=%s main..HEAD | tr '\n' '|')"
    echo "migration files: $(ls "$dir/migrations/versions" | tr '\n' ' ')"
    (cd "$dir" && $ENGINE migrations check --descriptor .radic/service.yml --migrations-dir migrations/versions \
      --checks migration_graph --format json) | jq -c '{migration_graph: .migration_graph}' || true
  fi
  echo
}

scenario safe-holdback "CDP-1,CDP-2,CDP-3,CDP-5" 2026.11.06-1
scenario unsafe-holdback "CDP-1,CDP-3,CDP-4,CDP-5" 2026.11.06-2
