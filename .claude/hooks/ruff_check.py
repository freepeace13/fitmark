"""PostToolUse: run ruff on an edited Python file and send any findings back to Claude."""

import importlib.util
import os
import shutil
import subprocess
import sys

from _hooklib import block, edited_path, notify_once, read_payload, repo_root


def ruff_command(root):
    venv_ruff = os.path.join(root, ".venv", "bin", "ruff")
    if os.access(venv_ruff, os.X_OK):
        return [venv_ruff]
    if shutil.which("ruff"):
        return ["ruff"]
    if importlib.util.find_spec("ruff"):
        return [sys.executable, "-m", "ruff"]
    return None


def main():
    payload = read_payload()
    rel = edited_path(payload)
    if rel is None or not rel.endswith(".py"):
        return 0
    root = repo_root(payload)
    command = ruff_command(root)
    if command is None:
        notify_once(payload, "ruff", "ruff hook skipped: ruff isn't installed. Run `make install`.")
        return 0
    result = subprocess.run(
        [*command, "check", "--force-exclude", "--output-format", "concise", rel],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = result.stdout + result.stderr
        block(f"ruff check failed for {rel}. Fix these before moving on:\n{output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
