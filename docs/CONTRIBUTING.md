# Contributing

Fitmark is one plugin. New capabilities arrive as skills, commands and MCP servers inside it, not as separate plugins.

## Proposing a capability

Open an issue from the capability template. A capability is added only when it has a named job, at least one design partner or clear user request, and acceptance criteria in `docs/specs/<area>.md`.

## Before opening a pull request

```sh
make install
make check
make validate   # needs the Claude Code CLI
```

The owner reviews all pull requests for now.

## Quality bar for a new capability

- Spec in `docs/specs/<area>.md` with acceptance criteria.
- Fixtures and tests, with CI green.
- README section with a walkthrough and before/after samples.
- Manual evaluation passed in Claude Code and the Claude app.

See [SKILL_GUIDELINES.md](SKILL_GUIDELINES.md) for conventions.

## Fixtures

Fixtures are synthetic only. Never commit real CVs, names, contact details or client data. Use `example.com`, `example.org` or `example.net` for emails.
