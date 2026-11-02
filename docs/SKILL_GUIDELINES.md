# Skill guidelines

## Naming

- Skill folders are short verbs for the recruiter's current step (`intake`, `submittal`, `spec-diff`, `setup`, `status`). They sit flat under `skills/`, and each one gives a single `/fitmark:<name>` shortcut.
- There is no `commands/` folder and no `bin/` folder. Claude's web app and Cowork will not install a plugin with `bin/`.
- Skill descriptions must be specific enough that two skills never trigger on the same request.

## Every skill starts and ends the same way

Skills never choose a folder. `scripts/workspace.py` returns every path, and it refuses any path inside the plugin. Use these two blocks in every `SKILL.md`, adding only the skill's own `job` or `candidate` arguments.

````markdown
## Start
1. Read `${CLAUDE_PLUGIN_ROOT}/references/evidence-rules.md` and `${CLAUDE_PLUGIN_ROOT}/references/fairness-rules.md`.
2. Run this exactly as written, with nothing before or after `FITMARK_WORKSPACE` on the last line:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/workspace.py" resolve --plugin-root "${CLAUDE_PLUGIN_ROOT}" --plugin-data "${CLAUDE_PLUGIN_DATA}" --workspace-stdin <<'FITMARK_WORKSPACE'
${user_config.workspace}
FITMARK_WORKSPACE
```

   If it returns `no_workspace`, follow `${CLAUDE_PLUGIN_ROOT}/references/quick-start.md`, then continue.
3. Read the agency's rules from the `agency_dir` it returns. With no profile, use defaults.

## Outputs
Run `workspace.py job ... --create` and write each file to the path it returns. Never build a path yourself.
Then run `workspace.py record`. In your reply, show paths relative to the workspace.
````

Never put `${user_config.workspace}` on a command line. It is substituted as plain text, so a quote in the folder name would break the command or run part of it as code. The quoted heredoc above passes it through untouched. With no saved value it stays as literal text, which the script treats as unset.

Pass the same `--plugin-root` and `--plugin-data` values to every `workspace.py` command, and the `root` that `resolve` returned as `--workspace`. Put `root` in single quotes, writing any `'` inside it as `'\''`. For a candidate, `exists: true` means a folder with that name exists, not that it's the same person. Check with the recruiter, then use `--new` for someone else. If the script returns `ambiguous_candidate`, ask which person and pass their folder with `--slug`, keeping their real name in `--name`. If Python can't run, follow `references/workspace-layout.md` by hand and list "workspace check" under skipped checks.

## Data

- JSON is the source of truth; documents are renderings. Shared entities use the schemas in `schemas/`, so one skill's output is the next skill's input.
- Additive schema changes are a minor version. Breaking changes are a major version of the schema `$id`, with a migration note.

## Behavior (non-negotiable)

- No claim about a candidate without cited evidence.
- Never infer or output protected attributes.
- Human review before anything reaches a client or candidate: Fitmark drafts, people send.
- Contact-detail redaction is on by default in client-facing outputs.
- Every skill works without scripts and says which checks were skipped.

## Scripts

- Python 3.11+, standard library first. JSON in, JSON out. Non-zero exit with a JSON error object.
- Call scripts from skills through the plugin root, such as `${CLAUDE_PLUGIN_ROOT}/scripts/redact.py`.

## Versioning

- One semver version for the whole plugin, matching in `plugin.json` and `marketplace.json`.
- A new skill or command is a minor version. A schema or command breaking change is a major version.
- Git tags are `v<semver>`. `CHANGELOG.md` is grouped by capability area.
