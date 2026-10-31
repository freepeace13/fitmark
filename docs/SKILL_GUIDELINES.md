# Skill guidelines

## Naming

- Skill folders are kebab-case and name the job (`intake-to-job-spec`, not `helper`). They sit flat under `skills/`.
- Commands are short verbs (`intake`, `submittal`, `setup`), invoked as `/fitmark:<command>`.
- Skill descriptions must be specific enough that two skills never trigger on the same request.

## Every skill starts the same way

1. Read `references/evidence-rules.md` and `references/fairness-rules.md`.
2. Load the effective agency profile. With no profile, use defaults and mention once that `/fitmark:setup` can tailor outputs.

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
