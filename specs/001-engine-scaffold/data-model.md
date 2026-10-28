# Phase 1 Data Model: Engine Scaffold & Service Descriptor Validation

Source of truth: Confluence RAITSDA space, "Reference 1: Service Descriptors
and Templates" + "Reference 1b/1c". This document restates those fields as
the concrete shape `schemas/service.schema.json` must encode; it does not
redefine them.

## Entity: Service Descriptor (`.radic/service.yml`)

JSON Schema draft 2020-12, `$id` under `delivery-platform`'s repo URL,
`additionalProperties: false` at every object level unless noted.

Top-level required: `schema_version, service, repo, runtime, build,
environments, cloud_deploy, quality, release`.

- **`schema_version`**: const `1`.
- **`service`** (required `name, kind, owner`): `name` — pattern
  `^[a-z][a-z0-9_-]{1,40}$`; `kind` — enum `[api, bff, web, worker, console]`;
  `owner` — string (GitHub team/user); `channel` — enum `[stable, canary]`,
  default `stable`.
- **`repo`** (required `slug, trunk`): `slug` — pattern
  `^radicdotai/[A-Za-z0-9_.-]+$`; `trunk` — const `"dev"`; `prod_line` —
  const `"main"`; `release_branch_prefix` — const `"release/"`.
- **`runtime`** (required `template, version`): `template` — enum
  `[python-uv, node]`; `version` — string; `framework` — informational
  string; `package_manager` — enum `[uv, npm]`; `system_packages` — array,
  items enum `[ffmpeg, libcairo2]`; `services` — array, items enum `[redis,
  postgres, postgrest, firebase-auth-emulator]`.
- **`build`** (required `dockerfile, image`): `dockerfile` default
  `"Dockerfile"`; `context` default `"."`; `target` — string; `env_agnostic`
  — boolean, default `false`; `image` (required `registry, repository,
  name`): `registry` — pattern `^[a-z0-9-]+-docker\.pkg\.dev$`; `human_tags`
  — array, items enum `[dev-latest, stage-latest, prod-latest]`;
  `dockerignore_required` — boolean, default `true`.
- **`environments`** (required `dev, stage, prod`, each a
  `$defs/environment`): required `gcp_project, region, cloud_run_service,
  health, state`; `region` const `"us-central1"`; `health` (required `url,
  timeout_seconds, fail_on_timeout`): `mode` enum `[http, gcloud-ready]`
  default `http`; `timeout_seconds` max `900`; `fail_on_timeout` const
  `true`; `state` (required `bucket, prefix`); optional
  `deployer_service_account, datasets, buckets, pubsub_topics,
  github_environment` (enum `dev/stage/prod`).
- **`cloud_deploy`** (required `driver, skaffold_file, planes, deployables`):
  `driver` const `"cloud-deploy"`; `skaffold_file` default
  `"deploy/skaffold.yaml"`; `planes` (required `dev, release`): `dev` const
  `"radicai"`, `release` const `"radicai-production"`; `deployables`
  (minItems 1, required `name, kind, pipelines`): `kind` enum `[service, job,
  workerpool]`; `enabled` default `true`; `pipelines` (required `dev`): `dev`
  pattern `^[a-z][a-z0-9-]{1,60}-dev$`, `rel` pattern
  `^[a-z][a-z0-9-]{1,60}-rel$`; `service_yaml`/`job_yaml` → `$defs/envFiles`;
  `health`; `require_approval.prod` const `true`; `parity.allow` — array of
  key names allowed to differ between env YAMLs.
- **`quality`** (required `lint, typecheck, unit, coverage_floor,
  skip_budget, post_deploy`): `typecheck` (required `tool, blocking`):
  `blocking` const `true`; `unit` (required `runner`): enum `[pytest,
  vitest]`; `coverage_floor` — `oneOf` global-number form or
  statements/branches/functions/lines form, plus `ratchet` default `true`;
  `skip_budget` — integer, min/max `0`; `quarantine` (`max_days` const `7`,
  `max_percent_of_tests` const `2`); `post_deploy` (required `suites`):
  `exception_id` — pattern `^EXC-[0-9]{4}$`, required when `suites` is
  empty; `suites[]` (required `name, runner, target, environments`):
  `environments` items enum `[dev, stage]`.
- **`release`** (required `tag_scheme, promotion`): `tag_scheme` const
  `"semver"`; `promotion.verify` const `"ancestry+tree+tag"`; `jira_project`
  pattern `^[A-Z]{2,10}$`.
- **`secrets_inventory`** (optional): names/counts only, never values.

`$defs`: `envFiles` (dev/stage/prod path strings matching
`^deploy/[A-Za-z0-9/_.-]+\.yaml$`), `environment` (as above).

**Validation rules this feature must enforce** (beyond "matches the schema"):
a descriptor whose `quality.post_deploy.suites` is empty AND whose
`quality.post_deploy.exception_id` does not resolve to an active,
non-expired entry in `policy/exceptions.yml` is **invalid** — this is a
cross-document rule the JSON Schema alone cannot express and must be checked
in `descriptor/validator.py` after schema validation passes.

## Entity: Policy Exception (`policy/exceptions.yml`)

One file, top-level list of entries. Each entry required: `id` (pattern
`^EXC-[0-9]{4}$`, unique across the file), `scope` (the service/descriptor
field it waives, e.g. `quality.post_deploy`), `owner` (service name),
`approver`, `reason`, `jira_key`, `created`, `expires` (ISO date). An entry
whose `expires` is strictly before "now" is **expired**; `policy exceptions
check <id>` must report exactly one of: active / expired / not-found.

Seed content for this feature (from Implementation Pack task 6.1):

| id | owner | approver | notes |
|---|---|---|---|
| EXC-0001 | web-bff | Tech Lead | no `post_deploy` suite defined yet |
| EXC-0002 | image-studio | Tech Lead | no `post_deploy` suite defined yet |
| EXC-0003 | brand_research | Tech Lead | no `post_deploy` suite defined yet |

(Expiry value: see research.md's note on the 30-vs-60-day discrepancy —
implemented as 60 days from creation per the Implementation Pack, pending
Tech Lead confirmation.)

## Entities introduced as stable shapes only (no reader/writer in this feature)

These three get a schema file each so that later features (release-cut,
deploy, promote) can depend on a stable contract immediately; this feature
does not populate or consume them.

- **Release Manifest** (`release-manifest.schema.json`): required
  `schema_version, release_id, kind, status, repo, created_at, initiator,
  base, selection, approvals, digests, gates`; nested `cloud_deploy`,
  `main` (set only post-prod-success).
- **Change Note** (`change-note.schema.json`): required `repo, sha, type,
  audience, title, summary, jira_key`.
- **Test Result** (`test-result.schema.json`): required `schema_version,
  repo, environment, release_id, digest, commit, suite, runner, started_at,
  finished_at, result, counts, skip_budget, run_url, cloud_deploy`.
