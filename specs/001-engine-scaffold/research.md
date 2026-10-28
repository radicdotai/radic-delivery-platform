# Phase 0 Research: Engine Scaffold & Service Descriptor Validation

All material decisions for this feature are already settled by the approved
architecture (Confluence space RAITSDA); this phase records *where* each
decision came from and the small number of implementation-level choices the
architecture left to this plan.

## Decisions taken directly from the approved architecture (no alternatives considered)

| Decision | Source |
|---|---|
| CLI name `radic-delivery`, package manager `uv`, CLI framework `typer` | Implementation Pack, task 6.1 |
| Exit code contract: 0 ok / 2 invalid input / 3 policy failure / 4 infra error | Reference 3: Schemas, Identity and Commands |
| Descriptor path `.radic/service.yml`; schema path `schemas/service.schema.json`, JSON Schema draft 2020-12, `additionalProperties: false` throughout | Reference 1: Service Descriptors and Templates |
| Required top-level descriptor fields, enums, and per-environment structure | Reference 1/1b/1c |
| `quality.skip_budget` fixed at 0; `quality.post_deploy.exception_id` required when `suites` is empty | Reference 1; Quality, Security and Governance |
| Three seeded exceptions: EXC-0001 (web-bff), EXC-0002 (image-studio), EXC-0003 (brand_research), approver "Tech Lead" | Implementation Pack, task 6.1 |
| Single exceptions file `policy/exceptions.yml`, no per-repo file | Quality, Security and Governance |
| Four schema files total (service + 3 record schemas) seeded in this feature | Implementation Pack, task 6.1 |

## Implementation-level choices made for this plan (not specified by the architecture)

- **`jsonschema` (Python library) for schema validation**: the architecture
  specifies the schema *format* (JSON Schema draft 2020-12) but not a
  validation library. `jsonschema` is the standard, actively maintained
  implementation for Python and needs no alternative evaluated.
- **A small hand-written schema-walker for `descriptor show`'s default-
  resolution**: the architecture specifies that defaults must be applied and
  shown, not how. `jsonschema` validates but does not apply defaults, so
  `descriptor/resolver.py` walks the schema alongside the document and fills
  in each `default` the author omitted (resolving `$ref` and picking the
  matching `oneOf` branch, e.g. for `coverage_floor`'s two shapes). A
  dependency like `pydantic` was considered and rejected as unnecessary extra
  surface for what the walk needs; this is an internal implementation detail,
  not a constitution concern (Principle XII governs the *path to GCP*, not
  every internal library choice).
- **Fixture data for the 7 service descriptors**: field values not given
  verbatim by the Confluence pages (marked `TODO-VERIFY` there against an
  open item, e.g. OI-1, OI-2, OI-8, OI-11) are filled with the same
  `TODO-VERIFY` marker convention the architecture itself already uses,
  rather than inventing a plausible-looking value. This keeps fixtures
  truthful to the current state of the open-item register instead of
  silently resolving open items that are explicitly still open.

## Open item carried forward (not resolved by this feature)

- The 30-day vs. 60-day exception-expiry discrepancy noted in spec.md's
  Assumptions is implemented as written in the Implementation Pack (60 days
  for these three seed exceptions) but is flagged for the Tech Lead to
  resolve at the source-documentation level. This plan does not invent a
  third number.
