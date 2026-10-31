# Fitmark `[✓]`

*Every candidate, marked against what was actually asked for.*

Fitmark is a Claude plugin for recruitment, hiring and talent work. This repository is both the marketplace and the plugin: one install, one version, one agency profile.

> **Status: foundation only.** The manifests, core rules and CI are in place. No skills or commands have shipped yet, so installing Fitmark today adds nothing you can use.

## Install

In Claude Code:

```
/plugin marketplace add freepeace13/fitmark
/plugin install fitmark@fitmark
```

## Planned for v0.1: agency recruiting

| Command | Job |
| --- | --- |
| `/fitmark:intake` | Client intake transcript or notes become a versioned job spec, screening rubric and confirmation email. |
| `/fitmark:submittal` | A CV and screening notes become a branded client-ready profile with a requirement-by-requirement evidence table. |
| `/fitmark:spec-diff` | Two spec versions become a change log and a list of affected submitted candidates. |
| `/fitmark:setup` | Past submittals, a brand guide and scorecards become a validated agency profile. |

## Core rules

Every skill follows [the evidence rules](references/evidence-rules.md) and [the fairness rules](references/fairness-rules.md), and no profile or request can override them. In short: no claim without evidence, no inference of protected attributes, and nothing reaches a client or candidate without a person's review.

## Privacy

Fitmark's outputs are drafts. The recruiter reviews them before sending, and data handling follows the agency's policies and local law. Fitmark has no telemetry.

## Contributing

See [CONTRIBUTING](docs/CONTRIBUTING.md) and [SECURITY](SECURITY.md). Licensed under [MIT](LICENSE).
