#!/usr/bin/env bash
set -euo pipefail

OUT=$(dirname "$0")/baseline.txt
snapshot() {
  for project in radicai radicai-production; do
    gcloud run services list --project="$project" --format='value(metadata.name,metadata.labels."cloud.googleapis.com/location")' \
      | grep -v cdpoc | sort | while read -r name region; do
        image=$(gcloud run services describe "$name" --project="$project" --region="$region" \
          --format='value(spec.template.spec.containers[0].image,status.latestReadyRevisionName)')
        iam=$(gcloud run services get-iam-policy "$name" --project="$project" --region="$region" --format=json \
          | jq -c '[.bindings[]? | {role, members: (.members | sort)}] | sort_by(.role)' | shasum | cut -c1-12)
        printf '%s\t%s\t%s\tiam=%s\n' "$project" "$name" "$image" "$iam"
      done
  done
}

if [[ "${1:-}" == --compare ]]; then
  diff "$OUT" <(snapshot) && echo "real services unchanged"
else
  snapshot > "$OUT"
  echo "wrote $(wc -l < "$OUT") services to $OUT"
fi
