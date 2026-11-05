"""PostToolUse: run `claude plugin validate .` after an edit to a plugin manifest or component."""

import fnmatch
import shutil
import subprocess
import sys

from _hooklib import block, edited_path, notify_once, read_payload, repo_root

PLUGIN_FILES = (
    ".claude-plugin/*",
    "skills/*/SKILL.md",
    "agents/*.md",
    "hooks/hooks.json",
    ".mcp.json",
)


def main():
    payload = read_payload()
    rel = edited_path(payload)
    if rel is None or not any(fnmatch.fnmatchcase(rel, pattern) for pattern in PLUGIN_FILES):
        return 0
    claude = shutil.which("claude")
    if claude is None:
        notify_once(payload, "validate", "Plugin validation hook skipped: `claude` is not on PATH.")
        return 0
    result = subprocess.run(
        [claude, "plugin", "validate", "."],
        cwd=repo_root(payload),
        capture_output=True,
        text=True,
        timeout=80,
    )
    if result.returncode != 0:
        output = result.stdout + result.stderr
        block(f"`claude plugin validate .` failed after editing {rel}:\n{output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
