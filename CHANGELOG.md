# Changelog

Grouped by capability area. Versions follow semver, with one version for the whole plugin.

## Unreleased

### Foundation

- Marketplace and plugin manifests.
- Core evidence and fairness rules.
- CI: manifest, skill lint, fixture privacy and size budget checks.
- Contribution, security and skill guidelines.

### Workspace

- `scripts/workspace.py` finds the workspace and returns every path a skill uses, and refuses any path inside the plugin.
- Fitmark folder setting (`userConfig.workspace`, default `~/Fitmark`).
- Schemas for `job.yaml` and `fitmark.yaml`; workspace layout and quick-start references.
- Skill conventions: verb-named skills, no `commands/`, shared Start and Outputs blocks.
