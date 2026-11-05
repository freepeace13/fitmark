# workspace.py review notes

- `job --create` always claims a new spec version folder for an unseen `ref`. Only the intake skill should call it; a submittal, status or spec-diff skill calling it inflates version numbers.
- `record` keys: `event` is `spec_saved` (needs `version`), `submittal_saved` (needs `candidate` and `file`) or `status` (needs `status`). There is no `slug` or `submittal_path` key on `record`.
- Without a `spec_saved` record, `current_spec_version` stays 0 and `candidate` returns `no_spec`.
- `candidate --create` now requires `--ref`; a retry with the same ref reuses the names recorded in the candidate folder's `.runs.json` until work is saved (fixed in PR #2). Check new callers pass a stable ref.
- Tests must never run the script with `HOME` inside the checkout: macOS system Python writes `Library/Caches/com.apple.python` under `HOME`. `run()` now defaults to a per-test temp home (fixed in PR #2); flag any new subprocess call that sets `HOME` to `ROOT`.
- Each skill kind has its own Outputs steps in `docs/SKILL_GUIDELINES.md` (spec version, submittal, read-only); check a new skill uses the one for its kind.
