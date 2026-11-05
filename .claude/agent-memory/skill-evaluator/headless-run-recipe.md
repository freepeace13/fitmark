---
name: headless-run-recipe
description: claude -p flags, permission rules and isolation steps that worked (and failed) for running a Fitmark skill headless in a throwaway workspace
metadata:
  type: reference
---

Learned on the intake evaluations of 2026-11-06 (Claude Code 2.1.318); now also written into the agent definition. Re-check against `claude --help` if the version changed.

**Isolation**
- User settings can hold a saved `pluginConfigs.fitmark@fitmark.options.workspace` pointing at some other workspace, and an installed marketplace copy of fitmark. `workspace.py` prefers the folder setting over the cwd `fitmark.yaml` marker, so the run could write to that other folder. Use `--setting-sources project,local` (auth still works). Then `${user_config.workspace}` arrives unsubstituted, `is_set` treats it as unset, and resolve finds the workspace by `marker` (as intended).
- Under `--plugin-dir` the plugin source is `fitmark@inline`, plugin data `<config>/plugins/data/fitmark-inline`.
- `mktemp -d` gives `/var/folders/...`, which resolves to `/private/var/...`. Rules must cover both forms.
- Add `--no-session-persistence`. Snapshot `git status --porcelain` and `touch <run>/start-stamp` before the run, then `find <repo> -newer start-stamp` after.

**Permissions**
- In `-p` mode, Read outside cwd is denied, even for the plugin's own files. Add `--allowedTools "Read(//<repo>/**)" "Read(//<run>/**)" "Read(//private<run>/**)"` (leading `//` = absolute). Do not use `--add-dir` for the repo: with acceptEdits that permits writes there.
- Any Bash command containing `{` with a quote (every documented `workspace.py ... <<'FITMARK_ARGS'` JSON heredoc) is blocked by the built-in "brace with quote character (expansion obfuscation)" check. A matching `Bash(python3 ...:*)` allow rule does NOT override it.
- A PreToolUse hook passed via `--settings <file>` that returns `permissionDecision: "allow"` for an exact-regex match of the documented heredoc form does get through. Keep the regex strict (fullmatch, quoted delimiter, one-line JSON body).
- Self-test the hook by building payloads with Python `json.dumps`, not `echo` (zsh `echo` turns `\n` into a real newline, which gives invalid JSON). Test the documented form, an appended `\ntouch ...` and a `;` injection.
- The fixture in `<run>/` is outside cwd, so the skill's "save a dated copy" `cp` is denied. The model then rewrites the file with Write, which is harmless.
- The model often rewrites the documented command (different delimiter, unquoted paths, `$PWD`, `cd` first), so a strict hook misses those calls. It then falls back to writing a `.json` args file and `--args-stdin < file`, which the prefix rule allows.

See [[intake-skill-findings]].
