---
name: new-skill
description: Scaffold a new Fitmark plugin skill in skills/<verb>/, with its spec criteria, CHANGELOG entry, version decision and checks. Run as /new-skill <verb>.
disable-model-invocation: true
argument-hint: <verb> [spec area]
---

# New Fitmark skill

Scaffold the skill named in the arguments (`$ARGUMENTS`) so that it follows the repo's conventions from the first commit. Copy the shared blocks from the guidelines each time, never from memory or an older skill, because the guidelines change.

## 1. Read first

- `docs/SKILL_GUIDELINES.md`, `docs/CONTRIBUTING.md`, `references/evidence-rules.md`, `references/fairness-rules.md`.
- The frontmatter of every `skills/*/SKILL.md`, the `README.md` shortcut table, `CHANGELOG.md` and `docs/specs/`.

## 2. Check the name

The name is a short verb for the recruiter's current step, in lowercase letters and hyphens, and `skills/<verb>/` must not exist yet. If it fails either check, propose a name and ask.

## 3. Ask once for what's missing

Ask in one message for anything the arguments and the conversation haven't given:

| Item | Used for |
| --- | --- |
| Job, in one sentence | The opening line and the description |
| Inputs and outputs | Steps, spec criteria |
| Kind: writes a spec version, writes a submittal, or reads only | Which Outputs steps to copy |
| Spec area, such as `agency-recruiting` | `docs/specs/<area>.md` |
| Design partner or user request | `CONTRIBUTING.md` requires one. If there is none, say so and ask whether to continue. |

## 4. Write `skills/<verb>/SKILL.md`

Fill in [template.md](template.md):

- **Description:** starts with "Use when", names the inputs the recruiter has and what they want, and ends with a "Not for ..." clause that names what each neighbouring skill handles. Check it against every other skill's description: no request should trigger both.
- **Start:** copy the `## Start` section from the fenced block in "Every skill starts and ends the same way" exactly, character for character, adding only this skill's own `job` or `candidate` arguments. Leave the folder-setting line and the stdin block untouched.
- **Outputs:** copy the `## Outputs` lines from the same block, then the numbered steps for this skill's kind from the guidelines, exactly.
- **Steps:** leave `TODO` items for the skill's own work unless the user has described it.

## 5. Spec, changelog, version

1. **Spec:** add a `## <verb>` section to `docs/specs/<area>.md`. If the file is new, start it like `agency-recruiting.md`. Write unchecked boxes only: the criteria from step 3, plus "Triggers from natural requests and `/fitmark:<verb>`, with no overlap with other skills", "Works without scripts and names the skipped checks", "Reads the agency rules from the workspace `agency_dir`" and "Manual evaluation passed in Claude Code and the Claude app". Boxes reflect what is verified, so never tick one here.
2. **CHANGELOG:** add a bullet under `## Unreleased`, in the area's `###` group: `` `<verb>` skill (`/fitmark:<verb>`) ``.
3. **Version:** if `CHANGELOG.md` has a released heading for the version in `plugin.json`, or `git tag` lists it, bump the minor version in both `.claude-plugin/plugin.json` and the `marketplace.json` plugin entry, to the same value. Otherwise the unreleased version already covers the new skill, so leave it. Say which applied.

## 6. Fixtures

Create fixtures only from a scenario the user describes: synthetic people and companies, emails only at `example.com`, `example.org` or `example.net`, and no phone numbers. Otherwise list fixtures as still to do.

## 7. Check and reply

Run `make check` and `claude plugin validate .`. If either can't run, say so; don't skip it silently. Don't commit.

Reply with:

- **Files:** created and changed.
- **Version:** bumped or left, and why.
- **Checks:** the result of each command.
- **Still to do:** the `TODO` steps, plus whatever `CONTRIBUTING.md`'s quality bar still needs: fixtures and tests, a README section with a walkthrough and before/after samples, and a manual evaluation (the `skill-evaluator` agent runs one).
