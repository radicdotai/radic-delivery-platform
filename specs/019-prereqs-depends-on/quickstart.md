# Quickstart: Prereqs and Depends-On Tracking and Enforcement

Validates the feature end-to-end — no GCP, Docker, or live Jira/GitHub
call anywhere.

## Prerequisites

```bash
cd engine && uv sync
```

## Scenario 1 — parsing

```python
from radic_delivery.notes.pr_body_fields import parse_depends_on, parse_prereqs

body = """Jira: RAD-12

Prereqs:
- [x] feature flag `widgets_v2` created in prod
- [ ] Secret Manager value WIDGETS_API_KEY set

Depends-on: RAD-11, RAD-11, RAD-10
"""

parse_prereqs(body)
# -> [{"item": "feature flag `widgets_v2` created in prod", "done": True},
#     {"item": "Secret Manager value WIDGETS_API_KEY set", "done": False}]

parse_depends_on(body)
# -> ["RAD-11", "RAD-10"]  (de-duplicated, order preserved)

parse_prereqs("Jira: RAD-1\nNo prereqs here.\n")   # -> []
parse_depends_on("Jira: RAD-1\nNo deps here.\n")   # -> []
```

## Scenario 2 — `notes write` computes prereqs/depends_on from a PR body

```bash
echo 'Prereqs:
- [x] flag created
Depends-on: RAD-11' > /tmp/pr-body.txt

uv run --project "$ENGINE_PROJECT" radic-delivery notes write \
  --repo radicdotai/web-bff --sha "$(printf '%040d' 1)" \
  --type feature --audience internal --title "Add widgets v2" \
  --summary "Adds widgets v2 behind a flag." --jira-key RAD-12 \
  --repo-dir . --base HEAD~1 --head HEAD \
  --pr-body-file /tmp/pr-body.txt \
  --format json
# Expected: record.prereqs == [{"item": "flag created", "done": true}]
#           record.depends_on == ["RAD-11"]
```

## Scenario 3 — `release cut` refuses on an unmet dependency

```python
# RAD-12's change-note declares depends_on: ["RAD-11"]; RAD-11 is neither
# in this release's selection nor in known_prod_tickets.
result = cut(manifest, ..., known_prod_tickets=None)
# Expected: result.ok is False, result.reason == "unmet_dependency",
# detail names "RAD-12" and "RAD-11"; no release/<id> branch created.

# RAD-11 already selected in the same release:
result = cut(manifest_with_rad11_selected, ...)
# Expected: result.ok is True

# RAD-11 supplied as already in prod:
result = cut(manifest, ..., known_prod_tickets=["RAD-11"])
# Expected: result.ok is True
```

## Scenario 4 — release PR body shows Prereqs/Depends-on

```python
result = render(manifest, change_notes_dir=notes_dir, repo_dir=repo, migrations_chain=[])
# result.body contains a "### Prereqs and dependencies" section with a row
# like "| RAD-12 | 1 / 2 | RAD-11 |" and a Gates checklist line for it.
```

## Scenario 5 — release gate enforces both

```bash
uv run --project "$ENGINE_PROJECT" radic-delivery gate evaluate \
  --descriptor .radic/service.yml --mode release-gate \
  --manifest /tmp/manifest.json --change-notes-dir /tmp/notes \
  --known-prod-tickets RAD-11 \
  --format json
# Expected: "prereqs" and "depends_on" checks both present; "fail" naming
# the specific ticket/item when incomplete, "pass" when fully complete.
```

## Final validation

```bash
cd engine
uv run pytest -q
uv run ruff check .
uv run mypy src/
```
