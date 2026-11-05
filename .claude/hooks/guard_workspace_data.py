"""PreToolUse: refuse file writes to workspace data inside the repo.

/agency/, /clients/ and /fitmark.yaml hold real agency and candidate data. .gitignore keeps them
out of commits; this keeps Claude from creating them in the repo in the first place.
"""

import sys

from _hooklib import edited_path, emit, read_payload

PROTECTED_DIRS = {"agency", "clients"}
PROTECTED_FILES = {"fitmark.yaml"}


def main():
    payload = read_payload()
    rel = edited_path(payload)
    if rel is None:
        return 0
    first = rel.split("/", 1)[0].lower()
    if first in PROTECTED_DIRS or rel.lower() in PROTECTED_FILES:
        reason = (
            f"Refused: {rel} is workspace data (agency/, clients/ or fitmark.yaml at the repo "
            "root), which never belongs in the Fitmark repo. Get paths from scripts/workspace.py, "
            "which returns a workspace outside the plugin, and put test data in a temporary folder."
        )
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
