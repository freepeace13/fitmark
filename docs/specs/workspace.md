# Workspace

Acceptance criteria for the workspace layer. Status boxes reflect what has been verified, not what is planned.

## scripts/workspace.py

- [x] `init`, `resolve`, `job`, `candidate`, `record` and `status` return JSON, using the standard library only.
- [x] Refuses any path inside the plugin root or plugin data folder, including through a symlink at the root, at any job, candidate or output path, a difference in letter case, and a marker found inside the plugin.
- [x] Finds the workspace from the folder setting, then a `fitmark.yaml` in the current folder or above, then the folder remembered from `init` in the plugin data folder, and with no setting the default folder. Otherwise returns `no_workspace` with a suggested path.
- [x] Names that differ by a meaningful symbol (`C++`, `C#`, `.NET`) or a non-Latin mark get separate folders, `spec_id` values can't clash, and adding a client rule leaves existing jobs in place and findable.
- [x] A person's case file can't silently receive another person's work: a shared name must be addressed with `--slug`, retrying `--new` with the same `--ref` doesn't create another person, parallel `--new` runs never share a folder, and `record` never credits the wrong person.
- [x] Spec versions and submittals never overwrite an earlier file.
- [x] `job.yaml` and `fitmark.yaml` match their schemas and parse as YAML.
- [x] `job --create` claims the next version folder under the job lock. Parallel runs get different versions, a retry with the same `ref` keeps its version, and a partly written version is never reused.
- [x] Script-written files get normal permissions for a shared folder, and a replaced file keeps its mode.
- [x] Lint targets Python 3.9, and CI runs on 3.9 and 3.11.
- [x] A bad `job.yaml` blocks only its own job, and `status` reports it.
- [x] Every failure is a JSON error, and an empty `spec.json` or submittal doesn't count as saved.
- [x] Client `match` lists are read in every YAML form: one name, flow or block, multi-line, with comments.
- [x] Parallel runs lose no recorded submittal and never share a candidate output path, and a `candidate --create` retry with the same `ref` reuses its reserved paths instead of leaving empty files.
- [x] Option values, including the folder setting, reach the script as JSON on stdin, so text with quotes or `$(...)` can't run a command when written as documented. Skills rely on Claude escaping the JSON; this is tested with a correctly written block, not in a real skill run.
- [x] Files are UTF-8 under any locale, and a failed write leaves no temp file.

## Plugin integration

- [x] Under `--plugin-dir`, a skill receives a saved folder setting, and an unsaved one resolves to `no_workspace`.
- [ ] After a marketplace install, Claude Code asks for the folder and a skill receives the answer.
- [ ] A real skill run makes zero write attempts outside the workspace (arrives with the first skill).
- [ ] The quick start completes a task with no setup (arrives with the first skill).
- [ ] A v2 intake lists affected submittals with no files supplied (arrives with the intake skill).
- [ ] The layout and folder setting behave as designed in the Claude app.

## Not yet built

`load_profile.py --workspace`, the SessionStart dependency hook, and the `setup`, `intake`, `submittal`, `spec-diff` and `status` skills.
