"""Pure selection: candidates + explicit ready/dev-green/non-jira inputs
-> Selection (research.md D4).

Candidates are expected to already be filtered to those reachable from
`--base` (release/git_history.py) and matching the requested repo
(release/candidates.py) before reaching this function.
"""

from __future__ import annotations

from collections import defaultdict

from radic_delivery.release.result import Candidate, HeldBackTicket, NonJiraPr, ProposedTicket, Selection

_NOT_READY_REASON = "not Ready for Review"


def select(
    candidates: list[Candidate],
    ready_tickets: set[str],
    dev_green_failed: set[str],
    non_jira_prs: set[int],
) -> Selection:
    tickets_by_key: dict[str, list[Candidate]] = defaultdict(list)
    ticketless_by_pr: dict[int, list[Candidate]] = defaultdict(list)

    for candidate in candidates:
        if candidate.jira_key == "None":
            if candidate.pr_number is not None:
                ticketless_by_pr[candidate.pr_number].append(candidate)
        else:
            tickets_by_key[candidate.jira_key].append(candidate)

    proposed: list[ProposedTicket] = []
    held_back: list[HeldBackTicket] = []
    for key, members in tickets_by_key.items():
        shas = [member.sha for member in members]
        failing = [sha for sha in shas if sha in dev_green_failed]
        if key not in ready_tickets:
            held_back.append(HeldBackTicket(key=key, reason=_NOT_READY_REASON))
        elif failing:
            held_back.append(
                HeldBackTicket(
                    key=key,
                    reason=f"dev-green check failed for commit {failing[0]}",
                )
            )
        else:
            proposed.append(ProposedTicket(key=key, title=members[0].title, commits=shas))

    included_non_jira: list[NonJiraPr] = []
    not_found: list[int] = []
    for pr_number in sorted(non_jira_prs):
        pr_candidates = ticketless_by_pr.get(pr_number)
        if not pr_candidates:
            not_found.append(pr_number)
            continue
        included_non_jira.append(
            NonJiraPr(pr_number=pr_number, commits=[candidate.sha for candidate in pr_candidates])
        )

    return Selection(
        tickets=proposed,
        held_back=held_back,
        non_jira_prs=included_non_jira,
        non_jira_prs_not_found=not_found,
    )
