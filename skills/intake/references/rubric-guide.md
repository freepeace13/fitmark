# Rubric guide

The rubric tells a recruiter what to look for and how to score it. A person makes every decision from those scores.

## Criterion

- `criterion_id`: exactly one id from `must_haves` or `nice_to_haves`, such as `mh-1`. One criterion per requirement.
- `weight`: a positive number. All weights in a rubric sum to 100. Must-haves carry more weight than nice-to-haves. Weights are your proposal unless the client gave them, so list them under "For your review".
- `evidence`: what to look for in a CV or screening call. Describe evidence only.
- `anchors`: what each score means. Keys are the numbers on the profile's `rubric_scale`; the default is 1 to 4. Include at least the lowest and highest score, with concrete descriptions tied to the requirement. For a yes/no requirement, the lowest and highest are enough.

## Scoring and decisions

Scores inform a recruiter. Express knockouts as `deal_breakers` the client stated, for a person to apply.

Score job-related evidence: skills, scope, results and qualifications. When a client asks for a trait such as "culture fit" or "drive", add an open question asking what it looks like on the job, then score the behaviours once the client has defined them.
