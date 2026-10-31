# Agency recruiting

Acceptance criteria per skill. Status boxes reflect what has been verified, not what is planned.

## intake-to-job-spec

- [x] 3 mock transcripts in `fixtures/intakes/` produce valid spec JSON, a document and an email, with zero invented must-haves on review.
- [ ] Triggers from natural requests and `/fitmark:intake`, with no overlap with other skills.
- [x] Discriminatory requirements are absent from the spec, rubric and email, and reported to the recruiter. Proxies are flagged for review.
- [x] Update mode increments the version, fills the changelog and calls out changes that could invalidate submitted candidates.
- [ ] Works without scripts and names the skipped checks.
- [ ] Reads the agency profile through `load_profile.py` (arrives with the profile work).
- [ ] Renders DOCX through `render_doc.py` (arrives with the submittal work). Until then it writes Markdown and says DOCX was skipped.
- [ ] Manual evaluation passed in Claude Code and the Claude app.
