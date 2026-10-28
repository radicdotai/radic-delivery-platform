# Quickstart: Engine Scaffold & Service Descriptor Validation

```bash
cd engine
uv sync

# Validate a real service fixture — expect success
uv run radic-delivery descriptor validate tests/fixtures/web-bff.yml

# Validate a deliberately broken fixture — expect a field-path-specific failure
uv run radic-delivery descriptor validate tests/fixtures/broken/missing-required-field.yml

# Show the fully resolved form of a descriptor (defaults applied)
uv run radic-delivery descriptor show tests/fixtures/image-studio.yml --format json

# Check a seeded policy exception
uv run radic-delivery policy exceptions check EXC-0002

# Confirm the full intended command surface is discoverable (stubs included)
uv run radic-delivery --help

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Exit code reference while testing manually: `0` success, `2` invalid
descriptor/exception input, `3` policy failure (e.g. expired exception),
`4` infra error (should not occur in this offline feature).
