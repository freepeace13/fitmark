# pr-reviewer memory

Committed to the repo and shared by everyone who runs the agent. Keep it short: one line per entry, linking to a topic file in this folder when an entry needs detail. No private data, diffs or code copied from the repo.

## Recurring issues

- The shared Start/Outputs blocks in `docs/SKILL_GUIDELINES.md` drift from what `workspace.py` actually accepts; check every new skill's commands, keys and events against the script. See [workspace-script.md](workspace-script.md).
- `workspace.py` was hardened over many commits (guard, locks, stdin args, encodings); edge-input fuzzing in PR #2 found only JSON errors. Spend review time on the docs-to-script contract and retry semantics, not re-auditing the guard.

## Owner decisions on findings

- PR #2 (2026-11-05): owner confirmed all 3 findings as drafted (Outputs block fits only intake; `candidate --create` retry leaves empty files; test helper `HOME` defaults to repo root). Posted as one COMMENT review.

## False positives to stop raising

- Empty reserved submittal/document files and gaps in spec version numbers are by design (documented in `references/workspace-layout.md`); only raise them when a normal retry produces them.
- `.claude/agents` and `.claude/agent-memory` in the plugin root are dev tooling; plugins load agents from `agents/`, so they don't ship as a plugin agent.

## Unwritten conventions

- System `python3` (3.9) has no pytest/ruff: make a venv in `mktemp -d`, install `requirements-dev.txt`, run `ruff check .` and `pytest` (about 50 s). `claude plugin validate .` is usually not run locally.
- Windows filename characters (`<>"|?*`) are not stripped by `readable()`; not raised while Windows support is unstated.
