# Quick start

Use this when `workspace.py resolve` returns `no_workspace`. It takes one question, then the recruiter's task continues.

1. Ask: "I'll keep Fitmark files in `<suggested_path>`. OK, or another folder?"
2. Run `workspace.py init --path <folder>` with the same `--plugin-root` and `--plugin-data` values, and the same `--workspace-stdin` heredoc as the `resolve` step. This saves the choice, so later sessions find the folder without asking. If it returns `inside_plugin`, say that folder can't be used and ask again.
3. Pass that folder as `--workspace` to every later `workspace.py` command in this session.
4. Finish the task on Fitmark defaults.
5. End the reply with one line: "Run /fitmark:setup to use your own templates, branding and rules."

If the session has no folder to write to, skip these steps and send the outputs as downloads named `<client>/<job>/...`.
