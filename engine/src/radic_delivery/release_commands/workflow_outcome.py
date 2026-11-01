"""CommandCheckResult -> WorkflowOutcome (data-model.md, research.md D2/D3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from radic_delivery.release_commands.result import CommandCheckResult, Form

WorkflowCommand = Literal["remove", "add", "nonjira", "abort", "waive", "none"]
WorkflowOutcomeValue = Literal["applied", "rejected", "ignored"]


@dataclass(frozen=True)
class WorkflowOutcome:
    command: WorkflowCommand
    outcome: WorkflowOutcomeValue
    reply_body: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "outcome": self.outcome,
            "reply_body": self.reply_body,
        }


# research.md D2: research_close has no slot in the architecture's `command`
# enum (remove|add|nonjira|abort|waive|none) — it maps to "none" regardless
# of whether it was accepted or refused, since "none" already means "no
# release-train command" and research_close isn't one.
_FORM_TO_COMMAND: dict[Form, WorkflowCommand] = {
    "release_remove": "remove",
    "release_add": "add",
    "release_nonjira": "nonjira",
    "release_abort": "abort",
    "release_waive_dev_green": "waive",
    "research_close": "none",
}

_FORM_LABEL: dict[Form, str] = {
    "release_remove": "release remove",
    "release_add": "release add",
    "release_nonjira": "release nonjira",
    "release_abort": "release abort",
    "release_waive_dev_green": "release waive dev-green",
    "research_close": "research close",
}


def _command_for(form: Form | None) -> WorkflowCommand:
    if form is None:
        return "none"
    return _FORM_TO_COMMAND[form]


def _accepted_reply(form: Form, args: dict[str, str]) -> str:
    label = _FORM_LABEL[form]
    if args:
        details = ", ".join(f"{key}={value}" for key, value in args.items())
        return f"Applied `{label}` ({details})."
    return f"Applied `{label}`."


def map_outcome(result: CommandCheckResult) -> WorkflowOutcome:
    """Total function: every CommandCheckResult maps to exactly one
    WorkflowOutcome (research.md D2's mapping table)."""
    if result.classification == "not_a_command":
        return WorkflowOutcome(command="none", outcome="ignored", reply_body=None)

    if result.classification == "malformed":
        return WorkflowOutcome(
            command="none",
            outcome="rejected",
            reply_body=f"Command not recognized: {result.detail}",
        )

    assert result.form is not None  # unauthorized/accepted always carry a form
    command = _command_for(result.form)

    if result.classification == "unauthorized":
        return WorkflowOutcome(
            command=command,
            outcome="rejected",
            reply_body=f"Refused `{_FORM_LABEL[result.form]}`: {result.detail}",
        )

    return WorkflowOutcome(
        command=command,
        outcome="applied",
        reply_body=_accepted_reply(result.form, result.args),
    )
