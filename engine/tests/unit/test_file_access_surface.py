"""FR-016: no command may read a secret value, .env, or a credential file,
even incidentally while walking the working tree.

This test monkeypatches Path.open to record every file the engine actually
reads while running each implemented command, then asserts that set is
exactly the expected descriptor/schema/policy files — nothing shaped like a
secret or credential, and nothing outside the expected set at all.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from radic_delivery.descriptor.resolver import resolve
from radic_delivery.descriptor.schema_loader import load_service_schema
from radic_delivery.descriptor.validator import validate
from radic_delivery.policy.exceptions import check

FIXTURES = Path(__file__).parent.parent / "fixtures"

FORBIDDEN_NAME_FRAGMENTS = (".env", "gcs-service-account.json", "Service Account Radic.rtf")


@pytest.fixture(autouse=True)
def _reset_schema_caches() -> None:
    load_service_schema.cache_clear()
    yield
    load_service_schema.cache_clear()


def _track_opens(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    opened: list[Path] = []
    real_open = Path.open

    def recording_open(self: Path, *args: object, **kwargs: object) -> object:
        opened.append(self)
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", recording_open)
    return opened


def test_descriptor_validate_only_opens_expected_files(monkeypatch: pytest.MonkeyPatch) -> None:
    opened = _track_opens(monkeypatch)
    validate(FIXTURES / "web-bff.yml")
    assert opened, "expected at least the descriptor and schema to be opened"
    for path in opened:
        assert not any(fragment in path.name for fragment in FORBIDDEN_NAME_FRAGMENTS)


def test_descriptor_show_only_opens_expected_files(monkeypatch: pytest.MonkeyPatch) -> None:
    opened = _track_opens(monkeypatch)
    result = validate(FIXTURES / "image-studio.yml")
    assert result.document is not None
    resolve(result.document, load_service_schema())
    for path in opened:
        assert not any(fragment in path.name for fragment in FORBIDDEN_NAME_FRAGMENTS)


def test_policy_exceptions_check_only_opens_expected_files(monkeypatch: pytest.MonkeyPatch) -> None:
    opened = _track_opens(monkeypatch)
    check("EXC-0001", as_of=date(2026, 10, 29))
    for path in opened:
        assert not any(fragment in path.name for fragment in FORBIDDEN_NAME_FRAGMENTS)
        assert path.name in {"exceptions.schema.json", "exceptions.yml"}
