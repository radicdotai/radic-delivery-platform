"""Pure selection tests: candidates + explicit ready/dev-green/non-jira
inputs -> Selection (research.md D4)."""

from __future__ import annotations

from radic_delivery.release.result import Candidate
from radic_delivery.release.selector import select

_SHA_A = "1111111111111111111111111111111111111111"
_SHA_B = "2222222222222222222222222222222222222222"
_SHA_C = "3333333333333333333333333333333333333333"


# --- US1: grouping ready tickets ---------------------------------------------


def test_two_commits_for_the_same_ready_ticket_are_grouped_together() -> None:
    candidates = [
        Candidate(sha=_SHA_A, jira_key="RAD-1234", title="First part"),
        Candidate(sha=_SHA_B, jira_key="RAD-1234", title="Second part"),
    ]
    selection = select(candidates, ready_tickets={"RAD-1234"}, dev_green_failed=set(), non_jira_prs=set())

    assert len(selection.tickets) == 1
    assert selection.tickets[0].key == "RAD-1234"
    assert sorted(selection.tickets[0].commits) == sorted([_SHA_A, _SHA_B])
    assert selection.held_back == []


def test_two_different_ready_tickets_are_listed_separately() -> None:
    candidates = [
        Candidate(sha=_SHA_A, jira_key="RAD-1234"),
        Candidate(sha=_SHA_B, jira_key="RAD-5678"),
    ]
    selection = select(
        candidates, ready_tickets={"RAD-1234", "RAD-5678"}, dev_green_failed=set(), non_jira_prs=set()
    )

    keys = {t.key for t in selection.tickets}
    assert keys == {"RAD-1234", "RAD-5678"}
    assert all(len(t.commits) == 1 for t in selection.tickets)


# --- US2: held-back visibility (research.md D4) ------------------------------


def test_ticket_not_in_ready_tickets_is_held_back_as_not_ready_for_review() -> None:
    candidates = [Candidate(sha=_SHA_A, jira_key="RAD-9999")]
    selection = select(candidates, ready_tickets=set(), dev_green_failed=set(), non_jira_prs=set())

    assert selection.tickets == []
    assert len(selection.held_back) == 1
    assert selection.held_back[0].key == "RAD-9999"
    assert selection.held_back[0].reason == "not Ready for Review"


def test_ready_ticket_whose_commit_failed_dev_green_is_held_back_distinctly() -> None:
    candidates = [Candidate(sha=_SHA_A, jira_key="RAD-1234")]
    selection = select(
        candidates, ready_tickets={"RAD-1234"}, dev_green_failed={_SHA_A}, non_jira_prs=set()
    )

    assert selection.tickets == []
    assert len(selection.held_back) == 1
    assert selection.held_back[0].key == "RAD-1234"
    assert "dev-green" in selection.held_back[0].reason
    assert _SHA_A in selection.held_back[0].reason
    assert selection.held_back[0].reason != "not Ready for Review"


def test_ready_ticket_with_no_failing_commit_is_proposed_never_held_back() -> None:
    candidates = [Candidate(sha=_SHA_A, jira_key="RAD-1234")]
    selection = select(candidates, ready_tickets={"RAD-1234"}, dev_green_failed=set(), non_jira_prs=set())

    assert len(selection.tickets) == 1
    assert selection.held_back == []


# --- US3: ticket-less PR explicit opt-in -------------------------------------


def test_explicitly_listed_ticketless_pr_is_included_with_placeholder_fields() -> None:
    candidates = [Candidate(sha=_SHA_C, jira_key="None", pr_number=142)]
    selection = select(candidates, ready_tickets=set(), dev_green_failed=set(), non_jira_prs={142})

    assert selection.tickets == []
    assert selection.held_back == []
    assert len(selection.non_jira_prs) == 1
    assert selection.non_jira_prs[0].pr_number == 142
    assert selection.non_jira_prs[0].reason == "MISSING"
    assert selection.non_jira_prs[0].second_approver is None
    assert selection.non_jira_prs[0].commits == [_SHA_C]


def test_ticketless_pr_not_explicitly_listed_appears_nowhere() -> None:
    candidates = [Candidate(sha=_SHA_C, jira_key="None", pr_number=142)]
    selection = select(candidates, ready_tickets=set(), dev_green_failed=set(), non_jira_prs=set())

    assert selection.tickets == []
    assert selection.held_back == []
    assert selection.non_jira_prs == []


def test_explicitly_listed_pr_with_no_matching_candidate_is_reported_not_found() -> None:
    selection = select([], ready_tickets=set(), dev_green_failed=set(), non_jira_prs={999})

    assert selection.non_jira_prs == []
    assert selection.non_jira_prs_not_found == [999]
