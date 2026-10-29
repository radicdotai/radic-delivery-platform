# Phase 0 Research: Release Slash-Command Parser and Authorization Check

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| Exactly six command forms; grammar `command = ws* "/" noun ws+ verb [ws+ args] ws* EOL`; `noun = release\|research`; `verb = remove\|add\|nonjira\|abort\|waive\|close` | Reference 3: Schemas, Identity and Commands |
| One command per comment; only the first line is read; verb matched case-insensitively | Reference 3 |
| Author must be in team `release-managers`; `waive dev-green` restricted to the Tech Lead alone | Reference 3 |
| Each comment id processed once | Reference 3 (explicitly deferred here — see spec Assumptions) |

## Design decisions made for this plan

### D1 — Team membership and Tech Lead identity are caller-supplied, not looked up

Consistent with every prior feature's split (`gate evaluate` doesn't install
a service's toolchain; `security scan` doesn't install its own scanners;
`deploy lint` doesn't fetch the descriptor from anywhere but disk): this
feature takes `--release-managers` (a list of usernames) and `--tech-lead`
(one username) as explicit CLI input. The real `release-commands` reusable
workflow (a later feature) is responsible for resolving these from GitHub's
actual team API before calling this command. This keeps the parser testable
with zero network access and zero GitHub API dependency.

### D2 — Per-form regex, not a single generic tokenizer

The six forms are not a free cross-product of noun×verb — `research` only
ever pairs with `close`, and `release waive` only ever takes the literal
`dev-green`, never a variable. Rather than writing one generic tokenizer
that then validates the combination, `grammar.py` matches the stripped
first line against six fixed, individually-authored regular expressions
(one per form), using Python's scoped inline-flag groups (`(?i:...)`,
available since Python 3.6, so no version constraint beyond this project's
Python 3.11 baseline) to make only the verb token case-insensitive while
every other literal
(`/release`, `/research`, `reason:`, `dev-green`) stays case-sensitive —
the architecture states case-insensitivity for the verb specifically, not
for the whole command, so this is deliberately narrower than a blanket
`re.IGNORECASE`.

**Rationale**: six small, independently readable patterns are easier to
verify against the six worked examples in Reference 3 than one generic
parser with branching validation logic, and a wrong pattern for one form
can never accidentally affect another.

### D3 — Classification order: "looks like an attempt" before "which form"

A first line is checked for NOT_A_COMMAND first (does it start with
`/release` or `/research` followed by whitespace or end-of-line at all?);
only if it clears that bar are the per-form regexes tried. This directly
implements spec User Story 2 (an ordinary comment is quietly not a
command) as a cheap, early, and clearly separate decision from "which of
the six forms did they mean" (User Story 3's malformed-command path) —
`/release` with no recognizable verb at all is MALFORMED (an attempt was
clearly made), while a comment that never starts with `/release` or
`/research` is NOT_A_COMMAND (no attempt was made).

### D4 — Comment body is read from stdin or a file, never a raw CLI argument

A PR comment's body is untrusted, attacker-reachable text (literally
anyone who can comment on a PR controls it) and can contain arbitrary
characters, including shell metacharacters and newlines. Interpolating
`${{ github.event.comment.body }}` directly into a shell `run:` step's
argument list is a well-known GitHub Actions script-injection
vulnerability class. This feature's CLI deliberately offers no
`--comment-body <text>` flag at all — only `--comment-file <path>` or
stdin — so that whenever the real `release-commands` reusable workflow is
built (a later feature, out of scope here), the natural, only-available
way to supply the comment body is via a file or piped stdin (for example,
written from a `github-script` step or an `env:`-block-indirected heredoc),
never via direct shell interpolation. This is a proactive design decision
for a workflow this feature does not build, recorded here so a future
implementer does not reach for the unsafe pattern by default.

## Open items carried forward (not resolved by this feature)

- "Each comment id processed once" needs persistent state (e.g. a label,
  or a record in `delivery-records`) that this feature does not introduce
  — flagged in spec.md's Assumptions, same treatment as prior features'
  deferred capabilities.
- The real `release-commands` reusable workflow (team-membership lookup,
  posting a reaction/reply, acting on an accepted command) is a later
  feature, same precedent as specs/004 wiring deploy lint into `ci.yml`
  only after the command worked standalone.
