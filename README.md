# Fitmark `[✓]`

*Every candidate, marked against what was actually asked for.*

Fitmark is a Claude plugin for recruitment, hiring and talent work. This repository is both the marketplace and the plugin: one install, one version, one agency profile.

> **Status: foundation only.** The manifests, core rules, workspace script and CI are in place. No skills have shipped yet, so installing Fitmark today adds nothing you can use.

## Install

In Claude Code:

```
/plugin marketplace add freepeace13/fitmark
/plugin install fitmark@fitmark
```

When you enable the plugin, Claude Code asks for your Fitmark folder. Keep the default, `~/Fitmark`, or leave it blank and choose on first use.

## Planned for v0.1: agency recruiting

| Shortcut | Job |
| --- | --- |
| `/fitmark:setup` | Past submittals, a brand guide and scorecards become a validated agency profile. Also runs a health check and profile edits. |
| `/fitmark:intake` | Client intake transcript or notes become a versioned job spec, screening rubric and confirmation email. A change to an existing job produces the next version. |
| `/fitmark:submittal` | A CV and screening notes become a branded client-ready profile with a requirement-by-requirement evidence table. |
| `/fitmark:spec-diff` | Two spec versions become a change log and a list of affected submitted candidates. |
| `/fitmark:status` | Lists jobs, current spec versions, submittals and any assessed against an old spec. |

## Your workspace

Everything sits in one folder, laid out like the desk: client, then job, then candidate. `agency/` holds rules with no candidate data, so a team can share it. `clients/` holds case files and stays private. See [the workspace layout](references/workspace-layout.md).

## Core rules

Every skill follows [the evidence rules](references/evidence-rules.md) and [the fairness rules](references/fairness-rules.md), and no profile or request can override them. In short: no claim without evidence, no inference of protected attributes, and nothing reaches a client or candidate without a person's review.

## Privacy

Fitmark's outputs are drafts. The recruiter reviews them before sending, and data handling follows the agency's policies and local law. Fitmark has no telemetry.

## Contributing

See [CONTRIBUTING](docs/CONTRIBUTING.md) and [SECURITY](SECURITY.md). Licensed under [MIT](LICENSE).
