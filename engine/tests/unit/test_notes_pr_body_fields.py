"""Pure PR-body text -> Prereqs/Depends-on parsing tests (spec.md
Acceptance Scenarios 1-3, Edge Cases)."""

from __future__ import annotations

from radic_delivery.notes.pr_body_fields import parse_depends_on, parse_prereqs


def test_prereqs_checklist_parses_ticked_and_unticked_items_in_order() -> None:
    body = (
        "Jira: RAD-12\n\n"
        "Prereqs:\n"
        "- [x] feature flag widgets_v2 created in prod\n"
        "- [ ] Secret Manager value WIDGETS_API_KEY set\n"
    )
    assert parse_prereqs(body) == [
        {"item": "feature flag widgets_v2 created in prod", "done": True},
        {"item": "Secret Manager value WIDGETS_API_KEY set", "done": False},
    ]


def test_depends_on_trailer_deduplicates_and_preserves_order() -> None:
    body = "Jira: RAD-12\nDepends-on: RAD-11, RAD-11, RAD-10\n"
    assert parse_depends_on(body) == ["RAD-11", "RAD-10"]


def test_neither_marker_present_parses_both_to_empty_lists() -> None:
    body = "Jira: RAD-1\nJust a plain PR body.\n"
    assert parse_prereqs(body) == []
    assert parse_depends_on(body) == []


def test_prereqs_item_with_whitespace_only_text_is_skipped() -> None:
    body = "Prereqs:\n- [x]   \n- [ ] a real item\n"
    assert parse_prereqs(body) == [{"item": "a real item", "done": False}]


def test_prereqs_and_depends_on_can_both_be_present() -> None:
    body = "Prereqs:\n- [x] one thing\n\nDepends-on: RAD-5\n"
    assert parse_prereqs(body) == [{"item": "one thing", "done": True}]
    assert parse_depends_on(body) == ["RAD-5"]


def test_depends_on_label_is_case_insensitive() -> None:
    assert parse_depends_on("depends-on: rad-9\n") == ["RAD-9"]
