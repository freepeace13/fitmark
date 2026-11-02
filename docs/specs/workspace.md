# Workspace

Acceptance criteria for the workspace layer. Status boxes reflect what has been verified, not what is planned.

## scripts/workspace.py

- [x] `init`, `resolve`, `job`, `candidate`, `record` and `status` return JSON, using the standard library only.
- [x] Refuses any path inside the plugin root or plugin data folder, including through symlinks and a marker found inside the plugin.
- [x] Finds the workspace from the folder setting, then from a `fitmark.yaml` in the current folder or above, and otherwise returns `no_workspace` with a suggested path.
- [x] Spec versions and submittals never overwrite an earlier file.
- [x] `job.yaml` and `fitmark.yaml` match their schemas and parse as YAML.

## Plugin integration

- [x] Under `--plugin-dir`, a skill receives a saved folder setting, and an unsaved one resolves to `no_workspace`.
- [ ] After a marketplace install, Claude Code asks for the folder and a skill receives the answer.
- [ ] A real skill run makes zero write attempts outside the workspace (arrives with the first skill).
- [ ] The quick start completes a task with no setup (arrives with the first skill).
- [ ] A v2 intake lists affected submittals with no files supplied (arrives with the intake skill).
- [ ] The layout and folder setting behave as designed in the Claude app.

## Not yet built

`load_profile.py --workspace`, the SessionStart dependency hook, and the `setup`, `intake`, `submittal`, `spec-diff` and `status` skills.
