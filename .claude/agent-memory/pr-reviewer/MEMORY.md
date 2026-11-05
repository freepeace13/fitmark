# pr-reviewer memory

Committed to the repo and shared by everyone who runs the agent. Keep it short: one line per entry, linking to a topic file in this folder when an entry needs detail. No private data, diffs or code copied from the repo.

## Recurring issues

- The shared Start/Outputs blocks in `docs/SKILL_GUIDELINES.md` drift from what `workspace.py` actually accepts; check every new skill's commands, keys and events against the script. See [workspace-script.md](workspace-script.md).
- `workspace.py` was hardened over many commits (guard, locks, stdin args, encodings); edge-input fuzzing in PR #2 found only JSON errors. Spend review time on the docs-to-script contract and retry semantics, not re-auditing the guard.
- Retry/reuse logic tends to key on "saved" (non-empty file) when the real end of a run is "recorded"; test partial writes (one of two outputs written) and names freed by deleting empty reserved files. See [workspace-script.md](workspace-script.md).

## Owner decisions on findings

- PR #2 (2026-11-05): owner confirmed all 3 findings as drafted (Outputs block fits only intake; `candidate --create` retry leaves empty files; test helper `HOME` defaults to repo root). Posted as one COMMENT review.
- PR #2 round 2 (2026-11-05, head 9ad0306): rounds 1 #1 and #3 fixed, #2 partly. Drafted 4 new minors (partial-save retry leaves an empty file; `.runs.json` can give two refs the same paths after empties are deleted; submittal Outputs steps reserve before the `exists` check; intake step says write to every `outputs` path, incl. `job_yaml`). Owner confirmed all 4; posted as one COMMENT review, then fixed.

## False positives to stop raising

- Empty reserved submittal/document files and gaps in spec version numbers are by design (documented in `references/workspace-layout.md`); only raise them when a normal retry produces them.
- `.claude/agents` and `.claude/agent-memory` in the plugin root are dev tooling; plugins load agents from `agents/`, so they don't ship as a plugin agent.

## Unwritten conventions

- System `python3` (3.9) has no pytest/ruff: make a venv in `mktemp -d`, install `requirements-dev.txt`, run `ruff check .` and `pytest` (50-75 s). `claude plugin validate .` is usually not run locally.
- CI runs `ruff check` but not `ruff format --check`; format drift in tests is not a finding.
- Windows filename characters (`<>"|?*`) are not stripped by `readable()`; not raised while Windows support is unstated.
