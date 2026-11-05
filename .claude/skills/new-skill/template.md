---
name: <verb>
description: Use when a recruiter has <inputs> and wants <outputs>. Not for <what each neighbouring skill handles>.
---

# <Title>

<One or two sentences: the recruiter's job, from input to output. Say which file is the source of truth if the skill writes JSON and documents.>

<The ## Start section, copied exactly from docs/SKILL_GUIDELINES.md, plus only this skill's own job or candidate arguments.>

## <The skill's own work, in one or more sections>

1. TODO

## Outputs
<The ## Outputs lines, copied exactly from docs/SKILL_GUIDELINES.md, then the numbered steps for this skill's kind.>

Pass every value from outside in the JSON on stdin, as in Start, and the same `--plugin-root` and `--plugin-data` on every command. If Python can't run, follow `${CLAUDE_PLUGIN_ROOT}/references/workspace-layout.md` by hand and list "workspace check" under skipped checks.

Then reply with these parts, in order:

- **Files:** what you saved. All are drafts, and nothing has been sent. (A read-only skill puts its answer here instead.)
- **For your review:** each refused or flagged request and the rule behind it, each inference, and your proposals.
- **Skipped checks:** or "None".
