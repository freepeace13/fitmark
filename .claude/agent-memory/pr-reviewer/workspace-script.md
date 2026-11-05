# workspace.py review notes

- `job --create` always claims a new spec version folder for an unseen `ref`. Only the intake skill should call it; a submittal, status or spec-diff skill calling it inflates version numbers.
- `record` keys: `event` is `spec_saved` (needs `version`), `submittal_saved` (needs `candidate` and `file`) or `status` (needs `status`). There is no `slug` or `submittal_path` key on `record`.
- Without a `spec_saved` record, `current_spec_version` stays 0 and `candidate` returns `no_spec`.
- `candidate --create` requires `--ref`. A retry with the same ref reuses the names in the candidate folder's `.runs.json` until that submittal is recorded in `job.yaml` (not merely written), and reserving names drops any other ref that held them, so one ref holds a name at a time (fixed in PR #2, rounds 1-2). Check new callers pass a stable ref, and that skills call `candidate` without `create` first to check `exists`.
- Tests must never run the script with `HOME` inside the checkout: macOS system Python writes `Library/Caches/com.apple.python` under `HOME`. `run()` now defaults to a per-test temp home (fixed in PR #2); flag any new subprocess call that sets `HOME` to `ROOT`.
- Each skill kind has its own Outputs steps in `docs/SKILL_GUIDELINES.md` (spec version, submittal, read-only); check a new skill uses the one for its kind.
- `candidate --create` reserves names immediately, so a skill must call `candidate` without `create` first to see `exists` and ask the recruiter; otherwise a different same-name person leaves empty files in the first person's folder.
- `job` `outputs` includes `job_yaml` and `intake_dir`, which skills must not write to; docs should name the output keys a skill writes.
