"""Fixed exit-code contract every radic-delivery command must honour.

Per spec FR-015: calling workflows branch on exit code, never on parsed text.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    INVALID_INPUT = 2
    POLICY_FAILURE = 3
    INFRA_ERROR = 4


# Not one of the four real outcomes above: used only for commands this
# feature intentionally does not implement yet (spec FR-003 / Edge Cases).
NOT_IMPLEMENTED_EXIT_CODE = 64
