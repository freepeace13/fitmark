# Workspace layout

`scripts/workspace.py` works out these paths. Follow this page by hand only if Python can't run, list "workspace check" under skipped checks, and never write inside the plugin folder.

```
Fitmark/                                 # the workspace
├── fitmark.yaml                         # marker: schema_version, agency, created_at
├── agency/                              # rules only, safe to share or commit
│   ├── profile.yaml
│   ├── guidelines.md
│   ├── brand/                           # brand.yaml, logo, templates/*.docx
│   ├── criteria/                        # engineering.yaml, finance.yaml
│   └── clients/                         # acme.yaml (client rules, with a match list)
└── clients/                             # case files with candidate data, private
    └── acme/
        └── senior-laravel-developer/    # spec_id: acme--senior-laravel-developer
            ├── job.yaml                 # index, written only by scripts
            ├── intake/                  # dated copies of intake notes
            ├── spec/
            │   ├── v1/
            │   │   ├── spec.json
            │   │   ├── Acme – Senior Laravel Developer – Job spec v1.docx
            │   │   └── confirmation-email.txt
            │   └── v2/                  # same files, plus changes-from-v1.md
            └── candidates/
                └── jane-doe/
                    ├── source/          # cv.pdf, screening-notes.md
                    ├── submittal-s1.json
                    ├── submittal-s2.json
                    └── J.D. – Senior Laravel Developer – Acme v2.docx
```

## Naming

| Item | Rule |
| --- | --- |
| Client folder | The stem in kebab-case of the `agency/clients/<slug>.yaml` whose file name fits, otherwise of the first file whose `match` list fits, otherwise the client name in kebab-case. A file name with no letters or digits is ignored. A job keeps its folder and `spec_id` if a client rule is added later; only new jobs use the new folder. |
| Job folder | The role title in kebab-case. `spec_id` is `<client>--<job>`. Symbols that tell names apart become words: `C++` is `c-plus-plus`, `C#` is `c-sharp`, `.NET` is `dot-net`, `R&D` is `r-and-d`. Marks that change a word in other scripts are kept; only Latin accents are dropped. |
| Spec version | One folder per version. `job` with `create` claims one above every existing folder, and a retry with the same `ref` keeps it until work is saved there or in a later version. `record` refuses a version older than the current one. Old versions are never edited, and an abandoned run leaves a gap. |
| Candidate folder | The name in kebab-case. A different person with the same name gets `-2`. `--ref` says which person that is, so a retry finds the same folder until work is saved there; after that the same `--ref` gets a new folder. Once a name is shared, pick the folder explicitly, because the name alone is refused. |
| Submittal | `submittal-s<n>.json`, where `n` is the spec version assessed against. A second assessment against the same version is `submittal-s<n>-2.json`. |
| Job document | `<Client> – <Role> – Job spec v<n>.docx`. |
| Candidate document | `<Initials> – <Role> – <Client> v<n>.docx`, and `-2` on a repeat. Follow the profile's anonymisation for what goes inside it. |

`candidate --create` reserves the submittal and document names as empty files, so parallel runs never share a path. It needs a `--ref`, and a retry with the same `--ref` gets the names it reserved until work is saved to them; `.runs.json` in the candidate folder records which ref reserved which names. An empty file is a run that didn't finish; it can't be recorded and is safe to delete.

`job --create` makes the folder for the next spec version, so files can be saved straight to the paths it returns. A `.ref` file in a claimed folder records which run or person it belongs to.

## job.yaml

Scripts write this file; recruiters don't. It holds JSON, which is also valid YAML, and matches `schemas/job.schema.json`. A file that can't be read blocks only its own job, and `status` lists it under `unreadable_jobs`. Status is one of `intake`, `spec_sent`, `confirmed`, `on_hold`, `filled` or `closed`.
