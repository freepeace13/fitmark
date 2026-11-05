#!/usr/bin/env python3
"""Generate a test report skeleton with exact environment, input, output and trace details."""

import argparse
import datetime
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TRACE_FILE = "run.jsonl"
MAX_ARGUMENT_CHARS = 160
LANGUAGES = {".json": "json", ".md": "markdown", ".py": "python", ".yaml": "yaml", ".yml": "yaml"}


def command_output(*command, empty="unavailable"):
    try:
        done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return done.stdout.strip() or empty


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def fenced(text, language="text"):
    longest = max((len(run) for run in re.findall(r"`{3,}", text)), default=2)
    fence = "`" * (longest + 1)
    return f"{fence}{language}\n{text.rstrip()}\n{fence}"


def file_section(path, heading="###"):
    size = path.stat().st_size
    if size == 0:
        return f"{heading} `{path.name}`\n\n{fenced('(empty, 0 bytes)')}"
    text = path.read_text(errors="replace")
    return f"{heading} `{path.name}`\n\n{fenced(text, LANGUAGES.get(path.suffix, 'text'))}"


def environment():
    clean = "dirty" if command_output("git", "status", "--short", empty="") else "clean"
    rows = [
        ("Date", datetime.date.today().isoformat()),
        ("OS", platform.platform()),
        ("System Python", platform.python_version()),
        ("Claude Code", command_output("claude", "--version")),
        ("Branch", command_output("git", "branch", "--show-current")),
        ("Commit", command_output("git", "rev-parse", "--short", "HEAD")),
        ("Working tree", clean),
    ]
    lines = ["| Item | Value |", "| --- | --- |"]
    return "\n".join(lines + [f"| {name} | {cell(value)} |" for name, value in rows])


def tool_result_errors(event):
    content = event.get("message", {}).get("content")
    if not isinstance(content, list):
        return []
    return [
        item.get("tool_use_id")
        for item in content
        if isinstance(item, dict) and item.get("type") == "tool_result" and item.get("is_error")
    ]


def read_trace(path):
    init, result, calls, failed = {}, {}, [], set()
    for line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            init = event
        elif kind == "result":
            result = event
        elif kind == "user":
            failed.update(tool_result_errors(event))
        elif kind == "assistant":
            content = event.get("message", {}).get("content", [])
            calls += [item for item in content if item.get("type") == "tool_use"]
    return init, result, calls, failed


def trace_section(run_dir):
    path = run_dir / TRACE_FILE
    if not path.is_file():
        return f"No `{TRACE_FILE}` in this run, so no tool trace is available."
    init, result, calls, failed = read_trace(path)
    fitmark_skills = [skill for skill in init.get("skills", []) if "fitmark" in skill]
    summary = [
        ("Model", init.get("model", "unknown")),
        ("Permission mode", init.get("permissionMode", "unknown")),
        ("Fitmark skills", ", ".join(fitmark_skills) or "none"),
        ("Outcome", result.get("subtype", "unknown")),
        ("Turns", result.get("num_turns", "unknown")),
        ("Duration (ms)", result.get("duration_ms", "unknown")),
        ("Permission denials", len(result.get("permission_denials", []))),
    ]
    table = ["| Item | Value |", "| --- | --- |"]
    table += [f"| {name} | {cell(value)} |" for name, value in summary]
    trace = ["| # | Tool | Input | Status |", "| --- | --- | --- | --- |"]
    for number, call in enumerate(calls, 1):
        argument = json.dumps(call.get("input", {}))[:MAX_ARGUMENT_CHARS]
        status = "error or denied" if call.get("id") in failed else "ok"
        trace.append(f"| {number} | {call.get('name')} | `{cell(argument)}` | {status} |")
    reply = result.get("result")
    final = f"\n\n#### Final reply\n\n{fenced(reply, 'markdown')}" if reply else ""
    return "\n".join(table) + "\n\n" + "\n".join(trace) + final


def run_section(name, run_dir):
    files = sorted(
        path for path in run_dir.iterdir() if path.is_file() and path.name != TRACE_FILE
    )
    outputs = "\n\n".join(file_section(path, "####") for path in files) or "No output files."
    return f"## Run: {name}\n\n### Tool trace\n\n{trace_section(run_dir)}\n\n### Files\n\n{outputs}"


def build(title, inputs, runs):
    inputs_text = "\n\n".join(file_section(path) for path in inputs) or "None."
    runs_text = "\n\n".join(run_section(name, folder) for name, folder in runs)
    return f"""# Test report: {title}

TODO: the verdict and the main reason, in one sentence.

## Test results

| Test | Result | Evidence |
| --- | --- | --- |
| TODO | TODO | TODO |

## Problems found

| # | Severity | Problem | Evidence | Fix |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO |

## Not covered

TODO: what these runs did not exercise, run counts, and changes made after a run.

## Environment

{environment()}

## Inputs

{inputs_text}

{runs_text}
"""


def fail(message):
    print(json.dumps({"error": message}))
    return 2


def parse_run(value):
    name, separator, folder = value.partition("=")
    return (name, Path(folder)) if separator and name else None


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def report_path(folder, stem, force):
    output = folder / f"{stem}.md"
    number = 2
    while output.exists() and not force:
        output = folder / f"{stem}-{number}.md"
        number += 1
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--input", action="append", default=[], type=Path)
    parser.add_argument("--run", action="append", default=[], help="NAME=FOLDER")
    parser.add_argument("--force", action="store_true", help="overwrite an existing report")
    args = parser.parse_args(argv)

    runs = [parse_run(value) for value in args.run]
    if None in runs:
        return fail("--run must be NAME=FOLDER")
    missing = [str(p) for p in args.input if not p.is_file()]
    missing += [str(folder) for _, folder in runs if not folder.is_dir()]
    if missing:
        return fail(f"not found: {', '.join(missing)}")

    stem = f"{datetime.date.today().isoformat()}-{slug(args.title)}"
    output = report_path(ROOT / "test-reports", stem, args.force)
    output.parent.mkdir(exist_ok=True)
    output.write_text(build(args.title, args.input, runs))
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
