# Phase 0 Research: Deploy YAML Lint

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| Cloud Run service YAML is `apiVersion: serving.knative.dev/v1, kind: Service`; placeholder `image: app`; autoscaling annotations; `serviceAccountName`, `containerConcurrency`, `timeoutSeconds`; container with `startupProbe`/`livenessProbe`; env vars including `secretKeyRef` | Reference 1: Service Descriptors and Templates (gathered during specs/001 research) |
| Deploy lint rules: every YAML needs `image: app`, no `traffic` key, a startup probe, no inline secret values | Reference 1 ("Lint rules (`radic-delivery deploy lint`)") |
| `cloud_deploy.deployables[].parity.allow` declares which keys are permitted to differ between environment YAML files | specs/001-engine-scaffold schema (`schemas/service.schema.json`) |
| `deploy lint` is one named subcommand of a larger `deploy` command group whose other subcommands call real Cloud Deploy | Reference 3: Schemas, Identity and Commands |

## Design decisions made for this plan

### D1 — The `traffic` key lives at `spec.traffic`, a sibling of `spec.template`

Cloud Run's fully-managed Knative Service CRD places traffic-splitting
configuration at the top level of `spec`, alongside (not inside)
`spec.template`. The rule checks for the literal presence of a `traffic`
key at that path — not a text search across the file — so a legitimate
mention of the word "traffic" elsewhere (a comment, an env var value)
never false-positives.

### D2 — Reuse `gitleaks` for the inline-secret rule; do not reinvent detection

specs/003 already integrated `gitleaks` (via `security/runner.py` and
`security/parsers.py::parse_gitleaks`) and confirmed it accepts a single
file path as `--source` (verified directly: `gitleaks detect --source
<file> --no-git --report-format json --report-path - --exit-code 0`
reports findings scoped to that one file). `deploy/linter.py` runs the same
invocation against each manifest file rather than writing a second,
parallel secret-detection implementation — one scanning mechanism, two
call sites, per Principle XI. Unlike specs/003, a finding here is an
unconditional lint failure, not an advisory report (spec FR-007: this is a
binary correctness check).

### D3 — Parity matching: a new, explicit convention (flagged, like prior features' new conventions)

The schema declares `parity.allow` as an array of strings (e.g.
`[secret_count]`, `[service_name]`, from specs/001's real fixtures) but the
architecture does not specify, field-by-field, which YAML difference each
string name corresponds to. This feature introduces an explicit, narrow
mapping rather than attempting a fully generic structural diff:

| `parity.allow` value | What it permits to differ |
|---|---|
| `service_name` | `metadata.name` may differ between environments |
| `secret_count` | The **set of env var names sourced via `secretKeyRef`** may differ in membership/count between environments (the values of `secretKeyRef`-sourced vars are never compared at all, in any case — see below) |

Everything else compared is **not** governed by `parity.allow` and must
match exactly across dev/stage/prod:
- `spec.template.spec.serviceAccountName`
- `spec.template.spec.containerConcurrency`, `timeoutSeconds`
- `spec.template.metadata.annotations` (autoscaling, Cloud SQL, VPC connector)
- the **set of env var names** that are *not* `secretKeyRef`-sourced (plain
  config vars) — their *values* are expected to differ per environment
  (different URLs, different flags) and are never compared; only their
  *names* must match across environments, since a config var present in
  prod but silently missing in dev is the real drift bug this check exists
  to catch
- `startupProbe`/`livenessProbe` path and port

**Rationale**: a fully generic "diff everything, allow anything whose path
loosely matches an allow-list string" design was considered and rejected —
it would be unverifiable against the two real `parity.allow` values
specs/001 already committed (`secret_count`, `service_name`) without
guessing at a path-matching heuristic. This explicit, small mapping is
instead directly checkable against those two real fixtures, and is no
harder to extend later (add a row) than a generic heuristic would have
been to get right.

**Update (same PR, post-review)**: this mapping is now also enforced at
the schema level, not just documented here. `schemas/service.schema.json`'s
`cloud_deploy.deployables[].parity.allow` items are constrained to an enum
of exactly `["service_name", "secret_count"]`, verified non-breaking
against every fixture in this repo (the only two values used anywhere).
This closes the "a typo is schema-valid but silently ignored by `deploy
lint`" gap: an unrecognized value now fails `descriptor validate` directly
(see `engine/tests/fixtures/broken/invalid-parity-allow.yml` and its
regression test in `test_descriptor_validate.py`). If a new allowance is
ever needed, both the schema enum and this table need a matching new row,
in lockstep. The mapping's *meaning* (what each value permits) is also
being proposed back to the architecture's own Confluence documentation
(Reference 1) for Tech Lead confirmation — this repo's schema enum and
`deploy/parity.py` are the enforced implementation of whatever that
authoritative source settles on.

### D4 — Cloud Run Jobs (`job_yaml`) are out of scope for this increment

Cloud Run Jobs use a structurally different manifest shape
(`apiVersion: run.googleapis.com/v1, kind: Job`, nesting containers one
level deeper under `spec.template.spec.template.spec`) that no research
pass for this platform has yet confirmed against a real example — and the
only descriptor with job deployables (`fastapi-backend`) already has every
one of them `enabled: false` pending a separate open item (OI-2, Cloud Run
Jobs under Cloud Deploy, from the architecture's own UNVERIFIED register).
This feature checks `service_yaml` only; a deployable with no `service_yaml`
(job-only) is reported as having nothing applicable to check, not as an
error and not silently skipped without mention — same honest-reporting
precedent as specs/003's "not_applicable" status.

## Open items carried forward (not resolved by this feature)

- D3's parity-matching table is a new convention awaiting platform-
  maintainer confirmation, same as prior flagged conventions.
- Cloud Run Jobs manifest linting is deferred until OI-2 is resolved and a
  real job manifest example exists to verify against.
