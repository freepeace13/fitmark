"""Shared helpers for the project's Claude Code hooks. Standard library only, Python 3.9+."""

import json
import os
import sys
import tempfile


def read_payload():
    return json.load(sys.stdin)


def repo_root(payload):
    return os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")


def edited_path(payload):
    """The repo-relative path the tool call writes, with / separators, or None if outside."""
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not path:
        return None
    root = repo_root(payload)
    target = os.path.realpath(os.path.join(payload.get("cwd") or root, path))
    rel = os.path.relpath(target, root)
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return None
    return rel.replace(os.sep, "/")


def emit(obj):
    print(json.dumps(obj))


def block(reason):
    """PostToolUse: send the reason back to Claude so it fixes the file."""
    emit({"decision": "block", "reason": reason})


def notify_once(payload, key, message):
    """Show a message to the user once per session, so a missing tool isn't silent or noisy."""
    session = payload.get("session_id", "none")
    marker = os.path.join(tempfile.gettempdir(), f"fitmark-hook-{key}-{session}")
    if os.path.exists(marker):
        return
    open(marker, "w").close()
    emit({"systemMessage": message})
