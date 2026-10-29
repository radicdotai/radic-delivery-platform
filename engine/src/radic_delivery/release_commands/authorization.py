"""ParsedCommand + caller-supplied identity -> CommandCheckResult.

Team membership and Tech Lead identity are explicit inputs, never looked
up here (research.md D1). `release_waive_dev_green` is checked against the
Tech Lead alone, superseding the general release-managers rule entirely —
not an additional requirement on top of it (spec FR-009: "restricted to
the Tech Lead alone").
"""

from __future__ import annotations

from radic_delivery.release_commands.result import CommandCheckResult, ParsedCommand


def authorize(
    parsed: ParsedCommand,
    author: str,
    release_managers: list[str],
    tech_lead: str,
) -> CommandCheckResult:
    if parsed.status == "not_a_command":
        return CommandCheckResult(classification="not_a_command")

    if parsed.status == "malformed":
        return CommandCheckResult(classification="malformed", detail=parsed.detail)

    assert parsed.form is not None  # status == "recognized" always sets form

    if parsed.form == "release_waive_dev_green":
        if author != tech_lead:
            return CommandCheckResult(
                classification="unauthorized",
                form=parsed.form,
                args=parsed.args,
                detail=(
                    "this command is restricted to the Tech Lead, "
                    "regardless of release-managers membership."
                ),
            )
    elif author not in release_managers:
        return CommandCheckResult(
            classification="unauthorized",
            form=parsed.form,
            args=parsed.args,
            detail="author is not on the release-managers team.",
        )

    return CommandCheckResult(classification="accepted", form=parsed.form, args=parsed.args)
