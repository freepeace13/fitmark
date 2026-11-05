---
name: fitmark-conventions
description: Use when changing anything in the Fitmark plugin repo, such as skills, scripts/workspace.py, schemas, fixtures, manifests, tests or docs, before writing the change.
user-invocable: false
---

# Fitmark conventions

The rules live in the repo and they change, so read the source for the area you're touching before you write. This table names the rules that are easiest to break.

| Touching | Read first | Easy to break |
| --- | --- | --- |
| `skills/*/SKILL.md` | `docs/SKILL_GUIDELINES.md`, `references/evidence-rules.md`, `references/fairness-rules.md` | Start and Outputs blocks copied exactly. Values reach `workspace.py` only as JSON on stdin. `${user_config.workspace}` appears only in its own prose line. Paths come from the script, never built by hand. No two descriptions trigger on the same request. |
| `scripts/` | "Scripts" in the guidelines, `docs/specs/workspace.md` | Python 3.9 and the standard library first. JSON in and out, with a non-zero exit and a JSON error object on failure. Refuse any path inside the plugin root or plugin data folder. |
| `schemas/` | "Data" in the guidelines | Draft 2020-12. A breaking change bumps the `$id` major version and needs a migration note. |
| `fixtures/`, `tests/` | "Fixtures" in `docs/CONTRIBUTING.md` | Synthetic only: emails at `example.com`, `example.org` or `example.net`, and no phone numbers or real CVs. |
| `.claude-plugin/` | `tests/test_repo.py` | Only the two manifests, with matching versions, a `CHANGELOG.md` entry and the right semver bump. |

Always:

- No `commands/` or `bin/` folder.
- Nothing at `/agency/`, `/clients/` or `/fitmark.yaml` in the repo.
- Spec status boxes record what has been verified, not what is planned.
- Run `make check` before calling a change done, and say if it couldn't run.
