"""`policy rulesets-diff`: compare committed ruleset JSON against a
supplied stand-in for the live `gh api repos/<repo>/rulesets` response
(research.md D4-D5). Pure comparison — no I/O of its own; the CLI reads
files and passes parsed JSON in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_MEANINGFUL_FIELDS = ("target", "enforcement", "conditions", "bypass_actors", "rules")


class DuplicateRulesetNameError(ValueError):
    """Two committed ruleset files share the same `name` field."""


@dataclass(frozen=True)
class ChangedRuleset:
    name: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "detail": self.detail}


@dataclass(frozen=True)
class RulesetsDiffResult:
    repo: str
    unchanged: list[str] = field(default_factory=list)
    missing_from_live: list[str] = field(default_factory=list)
    added_in_live: list[str] = field(default_factory=list)
    changed: list[ChangedRuleset] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing_from_live or self.added_in_live or self.changed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "repo": self.repo,
            "unchanged": self.unchanged,
            "missing_from_live": self.missing_from_live,
            "added_in_live": self.added_in_live,
            "changed": [item.to_dict() for item in self.changed],
        }


def _project(ruleset: dict[str, Any]) -> dict[str, Any]:
    return {field_name: ruleset.get(field_name) for field_name in _MEANINGFUL_FIELDS}


def _by_name(rulesets: list[dict[str, Any]], *, source: str) -> dict[str, dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for ruleset in rulesets:
        name = ruleset["name"]
        if name in by_name:
            raise DuplicateRulesetNameError(
                f"{source} contains two rulesets named '{name}'."
            )
        by_name[name] = ruleset
    return by_name


def diff(repo: str, committed: list[dict[str, Any]], live: list[dict[str, Any]]) -> RulesetsDiffResult:
    committed_by_name = _by_name(committed, source="the committed ruleset directory")
    live_by_name = _by_name(live, source="the live ruleset file")

    unchanged: list[str] = []
    missing_from_live: list[str] = []
    changed: list[ChangedRuleset] = []

    for name, committed_ruleset in committed_by_name.items():
        live_ruleset = live_by_name.get(name)
        if live_ruleset is None:
            missing_from_live.append(name)
            continue
        committed_projection = _project(committed_ruleset)
        live_projection = _project(live_ruleset)
        if committed_projection == live_projection:
            unchanged.append(name)
            continue
        differing_fields = sorted(
            f for f in _MEANINGFUL_FIELDS if committed_projection[f] != live_projection[f]
        )
        changed.append(ChangedRuleset(name=name, detail=f"{', '.join(differing_fields)} differ"))

    added_in_live = sorted(set(live_by_name) - set(committed_by_name))

    return RulesetsDiffResult(
        repo=repo,
        unchanged=sorted(unchanged),
        missing_from_live=sorted(missing_from_live),
        added_in_live=added_in_live,
        changed=sorted(changed, key=lambda item: item.name),
    )
