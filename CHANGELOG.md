# Changelog

Grouped by capability area. Versions follow semver, with one version for the whole plugin.

## Unreleased

### Agency recruiting

- `intake` skill (`/fitmark:intake`), with Markdown spec output for now.
- Job spec schema and `validate_json.py`.
- Synthetic intake fixtures and golden specs.
- `intake` reads its templates from its own skill folder, keeps refused and flagged requests out of the client email, quotes only the client's own words, and adds nothing to the summary that the intake doesn't say.

### Foundation

- Marketplace and plugin manifests.
- Core evidence and fairness rules.
- CI: manifest, skill lint, fixture privacy and size budget checks.
- Contribution, security and skill guidelines.
- Fixture privacy scan no longer treats ISO dates as phone numbers.
- Contributor tooling in `.claude/`: hooks that run ruff and the plugin validator after edits and refuse workspace data in the repo, the `new-skill` and `fitmark-conventions` skills, the `skill-evaluator` agent, and plugin-dev enabled for the project.

### Workspace

- `scripts/workspace.py` finds the workspace and returns every path a skill uses, and refuses any path inside the plugin.
- Fitmark folder setting (`userConfig.workspace`, default `~/Fitmark`). A folder chosen at first use is remembered in the plugin data folder.
- Schemas for `job.yaml` and `fitmark.yaml`; workspace layout and quick-start references.
- Skill conventions: verb-named skills, no `commands/`, shared Start and Outputs blocks. Values reach scripts as JSON on stdin (`--args-stdin`), never on the command line.
