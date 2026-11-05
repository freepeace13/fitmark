# Spec template

Render from the spec JSON only. Omit a section if it has no content, except "Open questions", which shows "None". Follow the profile's section and style settings where it has them. Keep `spec_id`, ids and JSON field names out of the body, except the header line.

```markdown
# <role_title> at <client>

Spec <spec_id>, version <version> · <created_at> · Status: <status> · Recruiter: <recruiter>

## Summary
<summary>

## Must-haves
- <text> *(client: "<client_quote>")* or *(inferred, to confirm)*

## Nice-to-haves
- <text> *(library criterion, to confirm)* where source is library, *(inferred, to confirm)* where inferred

## Deal-breakers
- <item>

## Compensation, location and process
| Item | Detail |
| --- | --- |
| Compensation | <currency min-max per period, or "To confirm"> |
| Location | <mode, timezone overlap, notes> |
| Interview process | <steps, or "To confirm"> |
| Commercial terms | <fee, exclusivity, deadline, or "To confirm"> |

## Screening rubric
| Requirement | Weight | Evidence | Lowest score | Highest score |
| --- | --- | --- | --- | --- |

## Open questions
1. <question>

## Changes in this version
| Field | From | To | May affect submitted candidates |
| --- | --- | --- | --- |
```
