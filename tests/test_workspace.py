"""Behaviour of scripts/workspace.py, run the way a skill runs it: as a subprocess."""

import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "workspace.py"
ACME = ["--client", "Acme Corp", "--role", "Senior Laravel Developer"]
ACME_ID = "acme-corp-senior-laravel-developer"


def run(*args, cwd=None, home=None):
    env = {"HOME": str(home or cwd or ROOT), "PATH": ""}
    done = subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
        cwd=cwd or ROOT,
        env=env,
    )
    return done.returncode, json.loads(done.stdout)


def ok(*args, **kwargs):
    code, out = run(*args, **kwargs)
    assert code == 0, out
    return out


def fail(*args, **kwargs):
    code, out = run(*args, **kwargs)
    assert code == 1, out
    assert out["error"]
    return out


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "Fitmark"
    ok("init", "--path", root, "--agency", "Example Talent")
    return root


def in_ws(ws, *args, **kwargs):
    return ok(*args, "--workspace", ws, **kwargs)


def saved_spec(ws, version=None):
    """Create the Acme job if needed, write the next spec and record it."""
    job = in_ws(ws, "job", *ACME, "--create")
    n = job["next_spec_version"]
    Path(job["outputs"]["spec_json"]).write_text("{}")
    in_ws(ws, "record", "--job", ACME_ID, "--event", "spec_saved", "--version", n)
    return n


def saved_submittal(ws, name="Jane Doe"):
    cand = in_ws(ws, "candidate", "--job", ACME_ID, "--name", name, "--create")
    path = Path(cand["submittal_path"])
    path.write_text("{}")
    in_ws(
        ws,
        "record",
        "--job",
        ACME_ID,
        "--event",
        "submittal_saved",
        "--candidate",
        cand["slug"],
        "--file",
        path.name,
    )
    return cand


# init


def test_init_creates_the_workspace_tree(tmp_path):
    root = tmp_path / "Fitmark"
    out = ok("init", "--path", root, "--agency", "Example Talent")
    assert out["status"] == "created"
    for folder in ("agency/brand", "agency/criteria", "agency/clients", "clients"):
        assert (root / folder).is_dir()
    marker = yaml.safe_load((root / "fitmark.yaml").read_text())
    assert marker["agency"] == "Example Talent"
    assert marker["schema_version"] == 1


def test_init_on_an_existing_workspace_keeps_its_marker(ws):
    before = (ws / "fitmark.yaml").read_text()
    out = ok("init", "--path", ws, "--agency", "Other")
    assert out["status"] == "exists"
    assert (ws / "fitmark.yaml").read_text() == before


def test_init_refuses_a_path_that_is_a_file(tmp_path):
    target = tmp_path / "file"
    target.write_text("x")
    fail("init", "--path", target)


# The plugin folder guard (the PR #1 bug)


@pytest.mark.parametrize("sub", ["", "skills/x", "../plugin/deep"])
def test_guard_refuses_init_inside_plugin_root(tmp_path, sub):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    out = fail("init", "--path", plugin / sub, "--plugin-root", plugin)
    assert out["code"] == "inside_plugin"
    assert not (plugin / "fitmark.yaml").exists()


def test_guard_covers_this_plugin_without_any_flag():
    out = fail("init", "--path", ROOT / "output")
    assert out["code"] == "inside_plugin"
    assert not (ROOT / "output").exists()


def test_guard_refuses_plugin_data_folder(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    out = fail("init", "--path", data / "w", "--plugin-data", data)
    assert out["code"] == "inside_plugin"


def test_guard_sees_through_symlinks(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    link = tmp_path / "innocent"
    link.symlink_to(plugin)
    out = fail("init", "--path", link / "w", "--plugin-root", plugin)
    assert out["code"] == "inside_plugin"


def test_guard_refuses_a_marker_found_inside_the_plugin(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    (plugin / "fitmark.yaml").write_text("schema_version: 1\n")
    out = fail("resolve", "--plugin-root", plugin, cwd=plugin, home=tmp_path)
    assert out["code"] == "inside_plugin"


def test_suggested_path_is_never_inside_the_plugin(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    out = fail("resolve", "--workspace", plugin / "w", "--plugin-root", plugin, home=tmp_path)
    assert out["code"] == "inside_plugin"


def test_guard_refuses_a_client_folder_linked_into_the_plugin(ws, tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    (ws / "clients" / "evil").symlink_to(plugin)
    code, out = run(
        "job", "--client", "evil", "--role", "r", "--create",
        "--workspace", ws, "--plugin-root", plugin,
    )  # fmt: skip
    assert code == 1
    assert out["code"] == "inside_plugin"
    assert list(plugin.iterdir()) == []


@pytest.mark.parametrize("sub", ["intake", "spec", "candidates"])
def test_guard_refuses_a_job_subfolder_linked_into_the_plugin(ws, tmp_path, sub):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    job_dir = Path(in_ws(ws, "job", *ACME, "--create")["job_dir"])
    shutil.rmtree(job_dir / sub)
    (job_dir / sub).symlink_to(plugin)
    code, out = run("job", *ACME, "--workspace", ws, "--plugin-root", plugin)
    assert code == 1
    assert out["code"] == "inside_plugin"


def test_guard_refuses_a_candidate_folder_linked_into_the_plugin(ws, tmp_path):
    saved_spec(ws)
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    job_dir = Path(in_ws(ws, "job", *ACME)["job_dir"])
    (job_dir / "candidates" / "jane-doe").symlink_to(plugin)
    code, out = run(
        "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--create",
        "--workspace", ws, "--plugin-root", plugin,
    )  # fmt: skip
    assert code == 1
    assert out["code"] == "inside_plugin"
    assert list(plugin.iterdir()) == []


def test_guard_refuses_an_agency_folder_linked_into_the_plugin(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    root = tmp_path / "w"
    root.mkdir()
    (root / "agency").symlink_to(plugin)
    out = fail("init", "--path", root, "--plugin-root", plugin)
    assert out["code"] == "inside_plugin"
    assert list(plugin.iterdir()) == []


# resolve


def test_resolve_uses_the_folder_setting_first(ws, tmp_path):
    other = tmp_path / "other"
    ok("init", "--path", other)
    out = ok("resolve", "--workspace", ws, cwd=other)
    assert out["status"] == "ok"
    assert out["root"] == str(ws.resolve())
    assert out["found_by"] == "setting"
    assert out["agency_dir"] == str(ws.resolve() / "agency")
    assert out["profile_exists"] is False


def test_resolve_walks_up_to_the_marker(ws):
    deep = ws / "clients" / "acme" / "job"
    deep.mkdir(parents=True)
    out = ok("resolve", cwd=deep, home=ws.parent)
    assert out["root"] == str(ws.resolve())
    assert out["found_by"] == "marker"


def test_resolve_reports_an_existing_profile(ws):
    (ws / "agency" / "profile.yaml").write_text("x: 1\n")
    assert in_ws(ws, "resolve")["profile_exists"] is True


def test_resolve_without_a_workspace_suggests_the_default(tmp_path):
    out = ok("resolve", cwd=tmp_path, home=tmp_path)
    assert out["status"] == "no_workspace"
    assert out["suggested_path"] == str(tmp_path.resolve() / "Fitmark")


def test_resolve_with_an_unset_folder_setting_suggests_that_folder(tmp_path):
    wanted = tmp_path / "Wanted"
    out = ok("resolve", "--workspace", wanted, cwd=tmp_path, home=tmp_path)
    assert out["status"] == "no_workspace"
    assert out["suggested_path"] == str(wanted)
    assert not wanted.exists()


def test_tilde_in_the_folder_setting_expands_to_home(tmp_path):
    out = ok("resolve", "--workspace", "~/Fitmark", cwd=tmp_path, home=tmp_path)
    assert out["suggested_path"] == str(tmp_path.resolve() / "Fitmark")


@pytest.mark.parametrize("value", ["", "${user_config.workspace}"])
def test_blank_or_unsubstituted_setting_counts_as_unset(tmp_path, value):
    out = ok("resolve", "--workspace", value, cwd=tmp_path, home=tmp_path)
    assert out["status"] == "no_workspace"
    assert out["suggested_path"] == str(tmp_path.resolve() / "Fitmark")


def test_commands_needing_a_workspace_fail_without_one(tmp_path):
    out = fail("job", *ACME, cwd=tmp_path, home=tmp_path)
    assert out["code"] == "no_workspace"


# Remembering the folder chosen at first use


def test_a_workspace_in_the_default_folder_is_found_with_a_blank_setting(tmp_path):
    root = tmp_path / "Fitmark"
    ok("init", "--path", root)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    out = ok("resolve", "--workspace", "", cwd=elsewhere, home=tmp_path)
    assert out["status"] == "ok"
    assert out["root"] == str(root.resolve())
    assert out["found_by"] == "default"


def test_a_custom_folder_is_remembered_in_plugin_data(tmp_path):
    custom = tmp_path / "Custom"
    data = tmp_path / "data"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert ok("init", "--path", custom, "--plugin-data", data, home=tmp_path)["remembered"] is True
    out = ok("resolve", "--plugin-data", data, cwd=elsewhere, home=tmp_path)
    assert out["root"] == str(custom.resolve())
    assert out["found_by"] == "saved"


def test_a_custom_folder_beats_an_unused_default_setting(tmp_path):
    custom = tmp_path / "Custom"
    data = tmp_path / "data"
    setting = ("--workspace", "~/Fitmark", "--plugin-data", data)
    ok("init", "--path", custom, *setting, home=tmp_path)
    out = ok("resolve", *setting, cwd=tmp_path, home=tmp_path)
    assert out["root"] == str(custom.resolve())


def test_changing_the_setting_replaces_the_remembered_folder(tmp_path):
    data = tmp_path / "data"
    ok("init", "--path", tmp_path / "Custom", "--plugin-data", data, home=tmp_path)
    wanted = tmp_path / "Wanted"
    out = ok("resolve", "--workspace", wanted, "--plugin-data", data, cwd=tmp_path, home=tmp_path)
    assert out["status"] == "no_workspace"
    assert out["suggested_path"] == str(wanted.resolve())


def test_a_remembered_folder_that_is_gone_or_unreadable_is_ignored(tmp_path):
    data = tmp_path / "data"
    custom = tmp_path / "Custom"
    ok("init", "--path", custom, "--plugin-data", data, home=tmp_path)
    (custom / "fitmark.yaml").unlink()
    out = ok("resolve", "--plugin-data", data, cwd=tmp_path, home=tmp_path)
    assert out["status"] == "no_workspace"
    (data / "workspace.json").write_text("not json")
    out = ok("resolve", "--plugin-data", data, cwd=tmp_path, home=tmp_path)
    assert out["status"] == "no_workspace"


# job


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("C++ Developer", "C# Developer"),
        ("C++ Developer", "C Developer"),
        (".NET Developer", "NET Developer"),
        ("R&D Lead", "RD Lead"),
    ],
)
def test_roles_that_differ_only_by_a_symbol_stay_separate(ws, first, second):
    one = in_ws(ws, "job", "--client", "Acme", "--role", first, "--create")
    two = in_ws(ws, "job", "--client", "Acme", "--role", second, "--create")
    assert two["exists"] is False
    assert one["spec_id"] != two["spec_id"]
    assert one["job_dir"] != two["job_dir"]


def test_clients_that_differ_only_by_a_symbol_stay_separate(ws):
    one = in_ws(ws, "job", "--client", "C++ Corp", "--role", "Dev")
    two = in_ws(ws, "job", "--client", "C# Corp", "--role", "Dev")
    assert one["client_slug"] != two["client_slug"]


@pytest.mark.parametrize("spelling", ["senior developer", "Senior-Developer", "Senior  Developer."])
def test_spelling_variants_of_a_role_are_the_same_job(ws, spelling):
    one = in_ws(ws, "job", "--client", "Acme", "--role", "Senior Developer", "--create")
    two = in_ws(ws, "job", "--client", "Acme", "--role", spelling)
    assert two["exists"] is True
    assert two["spec_id"] == one["spec_id"]


def test_a_new_client_rule_keeps_an_existing_job_in_its_folder(ws):
    saved_spec(ws)
    before = in_ws(ws, "job", *ACME)
    (ws / "agency/clients/acme.yaml").write_text("match: [Acme Corp, ACME Inc]\n")
    for client in ("Acme Corp", "ACME Inc", "acme"):
        out = in_ws(ws, "job", "--client", client, "--role", ACME[3])
        assert out["exists"] is True
        assert out["spec_id"] == ACME_ID
        assert out["job_dir"] == before["job_dir"]
        assert out["client_slug"] == "acme-corp"
        assert out["next_spec_version"] == 2


def test_a_new_client_rule_sends_new_jobs_to_the_new_folder(ws):
    saved_spec(ws)
    (ws / "agency/clients/acme.yaml").write_text("match: [Acme Corp]\n")
    out = in_ws(ws, "job", "--client", "Acme Corp", "--role", "Analyst")
    assert out["exists"] is False
    assert out["client_slug"] == "acme"


def test_status_still_lists_a_job_after_a_new_client_rule(ws):
    saved_spec(ws)
    (ws / "agency/clients/acme.yaml").write_text("match: [Acme Corp]\n")
    for client in ("Acme Corp", "acme"):
        jobs = in_ws(ws, "status", "--client", client)["jobs"]
        assert [j["spec_id"] for j in jobs] == [ACME_ID]


@pytest.mark.parametrize(
    ("client", "role", "spec_id"),
    [
        ("Acme Corp", "Senior Laravel Developer", ACME_ID),
        ("Northwind Traders", "Finance Manager", "northwind-traders-finance-manager"),
        ("Café Noël", "C++ / Rust Dev", "cafe-noel-c-plus-plus-rust-dev"),
    ],
)
def test_job_slugs_and_spec_id(ws, client, role, spec_id):
    out = in_ws(ws, "job", "--client", client, "--role", role)
    assert out["spec_id"] == spec_id
    assert out["exists"] is False
    assert Path(out["job_dir"]) == ws.resolve() / "clients" / out["client_slug"] / out["job_slug"]


def test_job_without_create_writes_nothing(ws):
    in_ws(ws, "job", *ACME)
    assert list((ws / "clients").iterdir()) == []


def test_job_paths_for_the_first_version(ws):
    out = in_ws(ws, "job", *ACME, "--create")
    job_dir = ws.resolve() / "clients" / "acme-corp" / "senior-laravel-developer"
    assert out["next_spec_version"] == 1
    assert out["outputs"] == {
        "spec_json": str(job_dir / "spec/v1/spec.json"),
        "spec_document": str(
            job_dir / "spec/v1/Acme Corp – Senior Laravel Developer – Job spec v1.docx"
        ),
        "confirmation_email": str(job_dir / "spec/v1/confirmation-email.txt"),
        "intake_dir": str(job_dir / "intake"),
        "job_yaml": str(job_dir / "job.yaml"),
    }
    for folder in ("intake", "spec", "candidates"):
        assert (job_dir / folder).is_dir()
    assert (job_dir / "spec/v1").is_dir()


def test_files_can_be_saved_straight_to_the_returned_paths(ws):
    saved_spec(ws)
    out = in_ws(ws, "job", *ACME, "--create")
    assert out["next_spec_version"] == 2
    Path(out["outputs"]["spec_json"]).write_text("{}")
    Path(out["outputs"]["changes_from_previous"]).write_text("x")


def test_job_without_create_makes_no_version_folder(ws):
    saved_spec(ws)
    assert not Path(in_ws(ws, "job", *ACME)["outputs"]["spec_json"]).parent.exists()


def test_an_unsaved_version_folder_does_not_use_up_a_version(ws):
    in_ws(ws, "job", *ACME, "--create")
    assert in_ws(ws, "job", *ACME)["next_spec_version"] == 1


def test_job_uses_the_client_match_list(ws):
    (ws / "agency/clients/acme.yaml").write_text(
        'name: Acme\nmatch:\n  - Acme Corp\n  - "ACME Inc"\n'
    )
    assert in_ws(ws, "job", *ACME)["client_slug"] == "acme"
    assert in_ws(ws, "job", "--client", "acme inc", "--role", "X")["client_slug"] == "acme"


def test_job_uses_an_inline_match_list(ws):
    (ws / "agency/clients/acme.yaml").write_text("match: [Acme Corp, ACME Inc]\n")
    assert in_ws(ws, "job", *ACME)["client_slug"] == "acme"


def test_job_matches_the_client_file_name(ws):
    (ws / "agency/clients/acme-corp.yaml").write_text("name: Acme\n")
    assert in_ws(ws, "job", *ACME)["client_slug"] == "acme-corp"


def test_repeat_job_reports_existing_and_next_version(ws):
    assert saved_spec(ws) == 1
    out = in_ws(ws, "job", *ACME)
    assert out["exists"] is True
    assert out["current_spec_version"] == 1
    assert out["next_spec_version"] == 2
    assert out["outputs"]["spec_json"].endswith("spec/v2/spec.json")
    assert out["outputs"]["changes_from_previous"].endswith("spec/v2/changes-from-v1.md")


def test_next_version_never_reuses_a_saved_spec_even_if_unrecorded(ws):
    job = in_ws(ws, "job", *ACME, "--create")
    Path(job["outputs"]["spec_json"]).write_text("{}")
    assert in_ws(ws, "job", *ACME)["next_spec_version"] == 2


def test_create_is_stable_when_run_twice_before_a_save(ws):
    in_ws(ws, "job", *ACME, "--create")
    assert in_ws(ws, "job", *ACME, "--create")["next_spec_version"] == 1


def test_document_name_cannot_escape_its_folder(ws):
    out = in_ws(ws, "job", "--client", "A/B", "--role", "../../etc", "--create")
    doc = Path(out["outputs"]["spec_document"])
    assert doc.parent == Path(out["job_dir"]) / "spec" / "v1"


@pytest.mark.parametrize("name", ["", "!!!", ".."])
def test_a_name_with_nothing_to_slug_is_refused(ws, name):
    code, out = run("job", "--client", name, "--role", "Dev", "--workspace", ws)
    assert code == 1
    assert out["code"] == "bad_name"


def test_two_jobs_cannot_share_a_spec_id(ws):
    in_ws(ws, "job", "--client", "Acme", "--role", "Senior Dev", "--create")
    code, out = run(
        "job", "--client", "Acme Senior", "--role", "Dev", "--create", "--workspace", ws
    )
    assert code == 1
    assert out["code"] == "spec_id_clash"


# candidate


def test_candidate_needs_a_saved_spec(ws):
    in_ws(ws, "job", *ACME, "--create")
    code, out = run("candidate", "--job", ACME_ID, "--name", "Jane Doe", "--workspace", ws)
    assert code == 1
    assert out["code"] == "no_spec"


def test_candidate_on_an_unknown_job_fails(ws):
    code, out = run("candidate", "--job", "nope", "--name", "Jane Doe", "--workspace", ws)
    assert code == 1
    assert out["code"] == "unknown_job"


def test_candidate_paths(ws):
    saved_spec(ws)
    out = in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--create")
    folder = Path(in_ws(ws, "job", *ACME)["job_dir"]) / "candidates" / "jane-doe"
    assert out["slug"] == "jane-doe"
    assert out["exists"] is False
    assert Path(out["candidate_dir"]) == folder
    assert (folder / "source").is_dir()
    assert Path(out["submittal_path"]) == folder / "submittal-s1.json"
    assert Path(out["document_path"]).name == "J.D. – Senior Laravel Developer – Acme Corp v1.docx"


def test_reassessment_on_a_new_spec_gets_the_new_version(ws):
    saved_spec(ws)
    saved_submittal(ws)
    saved_spec(ws)
    out = in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe")
    assert out["exists"] is True
    assert Path(out["submittal_path"]).name == "submittal-s2.json"


def test_reassessment_on_the_same_spec_never_overwrites(ws):
    saved_spec(ws)
    saved_submittal(ws)
    out = in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe")
    assert Path(out["submittal_path"]).name == "submittal-s1-2.json"


def test_a_different_person_with_the_same_name_gets_a_suffix(ws):
    saved_spec(ws)
    saved_submittal(ws)
    out = in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--create")
    assert out["slug"] == "jane-doe-2"
    assert Path(out["candidate_dir"]).is_dir()


def test_retrying_new_reuses_the_unused_folder(ws):
    saved_spec(ws)
    saved_submittal(ws)
    args = ("candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--create")
    assert in_ws(ws, *args)["slug"] == "jane-doe-2"
    out = in_ws(ws, *args)
    assert out["slug"] == "jane-doe-2"
    assert out["exists"] is True


def test_new_moves_on_once_the_folder_is_in_use(ws):
    saved_spec(ws)
    saved_submittal(ws)
    args = ("candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--create")
    second = in_ws(ws, *args)
    (Path(second["source_dir"]) / "cv.pdf").write_text("cv")
    assert in_ws(ws, *args)["slug"] == "jane-doe-3"


def test_a_shared_name_must_say_which_person(ws):
    saved_spec(ws)
    saved_submittal(ws)
    in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--create")
    code, out = run("candidate", "--job", ACME_ID, "--name", "Jane Doe", "--workspace", ws)
    assert code == 1
    assert out["code"] == "ambiguous_candidate"
    assert "jane-doe, jane-doe-2" in out["error"]


def test_slug_addresses_the_second_person_with_their_real_name(ws):
    saved_spec(ws)
    saved_submittal(ws)
    in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--create")
    out = in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--slug", "jane-doe-2")
    assert out["slug"] == "jane-doe-2"
    assert out["exists"] is True
    assert Path(out["document_path"]).name.startswith("J.D. – ")


@pytest.mark.parametrize("value", ["jane-doe-9", "john-smith", "../jane-doe"])
def test_slug_must_be_an_existing_folder_for_that_name(ws, value):
    saved_spec(ws)
    saved_submittal(ws)
    code, out = run(
        "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--slug", value, "--workspace", ws
    )
    assert code == 1
    assert out["code"] == "unknown_candidate"


def test_new_and_slug_cannot_be_combined(ws):
    saved_spec(ws)
    code, out = run(
        "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--slug", "jane-doe",
        "--workspace", ws,
    )  # fmt: skip
    assert code == 2
    assert out["code"] == "usage"


# record


def test_job_yaml_is_valid_yaml_and_matches_its_schema(ws):
    saved_spec(ws)
    saved_submittal(ws)
    job = yaml.safe_load((Path(in_ws(ws, "job", *ACME)["job_dir"]) / "job.yaml").read_text())
    schema = json.loads((ROOT / "schemas/job.schema.json").read_text())
    jsonschema.validate(job, schema)
    assert job["spec_id"] == ACME_ID
    assert job["client"] == "Acme Corp"
    assert job["role"] == "Senior Laravel Developer"
    assert job["status"] == "intake"
    assert job["current_spec_version"] == 1
    assert job["submittals"] == [
        {
            "candidate": "jane-doe",
            "spec_version": 1,
            "file": "submittal-s1.json",
            "date": date.today().isoformat(),
        }
    ]


def test_marker_matches_its_schema(ws):
    schema = json.loads((ROOT / "schemas/fitmark.schema.json").read_text())
    jsonschema.validate(yaml.safe_load((ws / "fitmark.yaml").read_text()), schema)


def test_record_refuses_a_spec_that_was_not_written(ws):
    in_ws(ws, "job", *ACME, "--create")
    code, out = run(
        "record", "--job", ACME_ID, "--event", "spec_saved", "--version", 1, "--workspace", ws
    )
    assert code == 1
    assert out["code"] == "missing_file"


def test_record_refuses_a_submittal_that_was_not_written(ws):
    saved_spec(ws)
    code, out = run(
        "record",
        "--job",
        ACME_ID,
        "--event",
        "submittal_saved",
        "--candidate",
        "jane-doe",
        "--file",
        "submittal-s1.json",
        "--workspace",
        ws,
    )
    assert code == 1
    assert out["code"] == "missing_file"


def test_recording_the_same_submittal_twice_adds_one_entry(ws):
    saved_spec(ws)
    cand = saved_submittal(ws)
    out = in_ws(
        ws,
        "record",
        "--job",
        ACME_ID,
        "--event",
        "submittal_saved",
        "--candidate",
        cand["slug"],
        "--file",
        "submittal-s1.json",
    )
    assert len(out["job"]["submittals"]) == 1


def test_record_changes_status(ws):
    saved_spec(ws)
    out = in_ws(ws, "record", "--job", ACME_ID, "--event", "status", "--status", "confirmed")
    assert out["job"]["status"] == "confirmed"


def test_record_refuses_an_unknown_status(ws):
    saved_spec(ws)
    code, out = run(
        "record", "--job", ACME_ID, "--event", "status", "--status", "done", "--workspace", ws
    )
    assert code == 1
    assert out["code"] == "bad_status"


# status


def test_status_lists_jobs_and_stale_submittals(ws):
    saved_spec(ws)
    saved_submittal(ws)
    saved_spec(ws)
    job = in_ws(ws, "status")["jobs"][0]
    assert job["spec_id"] == ACME_ID
    assert job["current_spec_version"] == 2
    assert job["stale_submittals"] == [
        {"candidate": "jane-doe", "spec_version": 1, "file": "submittal-s1.json"}
    ]


def test_a_reassessed_candidate_is_no_longer_stale(ws):
    saved_spec(ws)
    saved_submittal(ws)
    saved_spec(ws)
    saved_submittal(ws)
    assert in_ws(ws, "status")["jobs"][0]["stale_submittals"] == []


def test_status_filters_by_client(ws):
    saved_spec(ws)
    in_ws(ws, "job", "--client", "Northwind", "--role", "Analyst", "--create")
    jobs = in_ws(ws, "status", "--client", "Northwind")["jobs"]
    assert [j["client_slug"] for j in jobs] == ["northwind"]


def test_status_open_hides_closed_jobs(ws):
    saved_spec(ws)
    in_ws(ws, "record", "--job", ACME_ID, "--event", "status", "--status", "filled")
    assert in_ws(ws, "status")["jobs"]
    assert in_ws(ws, "status", "--open")["jobs"] == []


# A bad job file (finding: one file must not block the workspace)


def other_job(ws, content):
    folder = ws / "clients" / "other" / "broken"
    folder.mkdir(parents=True)
    (folder / "job.yaml").write_text(content)
    return folder / "job.yaml"


BAD_JOB_FILES = [
    "{}",
    "spec_id: z\n",
    "[]",
    '{"spec_id": 1}',
    json.dumps(
        {
            "spec_id": "s", "client": "c", "client_slug": "c", "job_slug": "j", "role": "r",
            "status": "intake", "current_spec_version": "1", "submittals": [],
        }
    ),
    json.dumps(
        {
            "spec_id": "s", "client": "c", "client_slug": "c", "job_slug": "j", "role": "r",
            "status": "intake", "current_spec_version": 1, "submittals": [{}],
        }
    ),
]  # fmt: skip


@pytest.mark.parametrize("content", BAD_JOB_FILES)
def test_a_bad_job_file_does_not_block_other_jobs(ws, content):
    saved_spec(ws)
    bad = other_job(ws, content)
    assert in_ws(ws, "job", *ACME)["exists"] is True
    assert in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe")["spec_version"] == 1
    out = in_ws(ws, "status")
    assert [j["spec_id"] for j in out["jobs"]] == [ACME_ID]
    assert [u["path"] for u in out["unreadable_jobs"]] == [str(bad.resolve())]


@pytest.mark.parametrize("content", BAD_JOB_FILES)
def test_asking_for_the_bad_job_itself_is_a_json_error(ws, content):
    bad = other_job(ws, content)
    code, out = run("job", "--client", "Other", "--role", "Broken", "--create", "--workspace", ws)
    assert code == 1
    assert out["code"] == "bad_job_file"
    assert bad.read_text() == content


def test_a_missing_job_mentions_unreadable_files(ws):
    other_job(ws, "{}")
    code, out = run("record", "--job", "nope", "--event", "status", "--status", "closed",
                    "--workspace", ws)  # fmt: skip
    assert code == 1
    assert out["code"] == "unknown_job"
    assert "job.yaml" in out["error"]


# Passing the folder setting safely


def resolve_through_shell(value, tmp_path):
    """Run the documented Start step in a real shell, with the setting substituted as text."""
    command = (
        f'"{sys.executable}" "{SCRIPT}" resolve --workspace-stdin <<\'FITMARK_WORKSPACE\'\n'
        f"{value}\nFITMARK_WORKSPACE\n"
    )
    done = subprocess.run(
        ["/bin/sh", "-c", command],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_a_setting_with_an_apostrophe_reaches_the_script_intact(tmp_path):
    folder = tmp_path / "Recruiter's Files"
    assert resolve_through_shell(folder, tmp_path)["suggested_path"] == str(folder.resolve())


def test_a_setting_cannot_run_a_command(tmp_path):
    out = resolve_through_shell("x'; touch pwned; '$(touch pwned)`touch pwned`", tmp_path)
    assert out["status"] == "no_workspace"
    assert not (tmp_path / "pwned").exists()


@pytest.mark.parametrize("value", ["", "${user_config.workspace}"])
def test_an_unset_setting_through_the_shell_counts_as_unset(tmp_path, value):
    out = resolve_through_shell(value, tmp_path)
    assert out["suggested_path"] == str(tmp_path.resolve() / "Fitmark")


def test_a_setting_of_several_lines_is_refused(tmp_path):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "resolve", "--workspace-stdin"],
        input="one\ntwo\n",
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert done.returncode == 1
    assert json.loads(done.stdout)["code"] == "bad_setting"


# Running at the same time


def start(*args):
    return subprocess.Popen(
        [sys.executable, str(SCRIPT), *map(str, args)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_parallel_records_lose_nothing(ws):
    saved_spec(ws)
    job_dir = Path(in_ws(ws, "job", *ACME)["job_dir"])
    names = [f"person-{n}" for n in range(12)]
    for name in names:
        folder = job_dir / "candidates" / name
        folder.mkdir()
        (folder / "submittal-s1.json").write_text("{}")
    running = [
        start("record", "--job", ACME_ID, "--event", "submittal_saved", "--candidate", name,
              "--file", "submittal-s1.json", "--workspace", ws)
        for name in names
    ]  # fmt: skip
    for process in running:
        _, err = process.communicate()
        assert process.returncode == 0, err
    job = json.loads((job_dir / "job.yaml").read_text())
    assert sorted(s["candidate"] for s in job["submittals"]) == sorted(names)
    assert not (job_dir / ".job.lock").exists()


def test_parallel_candidates_get_different_paths(ws):
    saved_spec(ws)
    running = [
        start("candidate", "--job", ACME_ID, "--name", "Jane Doe", "--create", "--workspace", ws)
        for _ in range(12)
    ]
    results = []
    for process in running:
        out, err = process.communicate()
        assert process.returncode == 0, err
        results.append(json.loads(out))
    assert len({r["submittal_path"] for r in results}) == 12
    assert len({r["document_path"] for r in results}) == 12


def test_a_stale_lock_does_not_block_recording(ws):
    saved_spec(ws)
    lock = Path(in_ws(ws, "job", *ACME)["job_dir"]) / ".job.lock"
    lock.write_text("")
    os.utime(lock, (1, 1))
    out = in_ws(ws, "record", "--job", ACME_ID, "--event", "status", "--status", "confirmed")
    assert out["job"]["status"] == "confirmed"


def test_a_reserved_empty_submittal_cannot_be_recorded(ws):
    saved_spec(ws)
    cand = in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--create")
    assert Path(cand["submittal_path"]).stat().st_size == 0
    code, out = run(
        "record", "--job", ACME_ID, "--event", "submittal_saved", "--candidate", "jane-doe",
        "--file", "submittal-s1.json", "--workspace", ws,
    )  # fmt: skip
    assert code == 1
    assert out["code"] == "missing_file"


def test_candidate_without_create_reserves_nothing(ws):
    saved_spec(ws)
    in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe")
    job_dir = Path(in_ws(ws, "job", *ACME)["job_dir"])
    assert list((job_dir / "candidates").iterdir()) == []


# File permissions


def run_with_umask(umask, *args):
    command = [sys.executable, str(SCRIPT), *map(str, args)]
    done = subprocess.run(
        command, capture_output=True, text=True, preexec_fn=lambda: os.umask(umask)
    )
    assert done.returncode == 0, done.stdout
    return json.loads(done.stdout)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
@pytest.mark.parametrize(("umask", "mode"), [(0o022, 0o644), (0o002, 0o664), (0o077, 0o600)])
def test_scripts_write_files_with_the_normal_permissions(tmp_path, umask, mode):
    root = tmp_path / "w"
    run_with_umask(umask, "init", "--path", root)
    out = run_with_umask(umask, "job", *ACME, "--create", "--workspace", root)
    assert (root / "fitmark.yaml").stat().st_mode & 0o777 == mode
    assert (Path(out["job_dir"]) / "job.yaml").stat().st_mode & 0o777 == mode


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_changing_a_job_keeps_its_permissions(ws):
    job_file = Path(in_ws(ws, "job", *ACME, "--create")["job_dir"]) / "job.yaml"
    job_file.chmod(0o660)
    in_ws(ws, "record", "--job", ACME_ID, "--event", "status", "--status", "confirmed")
    assert job_file.stat().st_mode & 0o777 == 0o660


# Encoding


LATIN1 = {"LC_ALL": "en_US.ISO8859-1", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}


def test_non_ascii_names_work_under_a_non_utf8_locale(ws):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "job", "--client", "株式会社", "--role", "Dev",
         "--create", "--workspace", str(ws)],
        capture_output=True,
        env={"HOME": str(ws), "PATH": "", **LATIN1},
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout.decode("utf-8"))
    job = json.loads((Path(out["job_dir"]) / "job.yaml").read_text(encoding="utf-8"))
    assert job["client"] == "株式会社"


def test_a_failed_write_leaves_no_temp_file(ws):
    job_dir = ws / "clients" / "acme" / "dev"
    (job_dir / "job.yaml").mkdir(parents=True)
    code, out = run("job", "--client", "Acme", "--role", "Dev", "--create", "--workspace", ws)
    assert code == 1
    assert out["error"]
    assert [p.name for p in job_dir.glob(".*")] == []


def test_a_client_file_that_is_not_utf8_only_loses_its_own_rules(ws):
    (ws / "agency/clients/latin.yaml").write_bytes("match: [Soci\xe9t\xe9]\n".encode("latin-1"))
    assert in_ws(ws, "job", *ACME)["client_slug"] == "acme-corp"
    assert in_ws(ws, "job", "--client", "Latin", "--role", "Dev")["client_slug"] == "latin"


# Client match lists


def test_inline_match_list_respects_quotes(ws):
    (ws / "agency/clients/globex.yaml").write_text("match: [\"Globex, Inc\", 'A, B', Globex]\n")
    for client in ("Globex, Inc", "A, B", "Globex"):
        assert in_ws(ws, "job", "--client", client, "--role", "Dev")["client_slug"] == "globex"
    assert in_ws(ws, "job", "--client", "Inc", "--role", "Dev")["client_slug"] == "inc"


@pytest.mark.parametrize("text", ['match:\n  - "&"\n  - Acme Corp\n', 'match: ["&", Acme Corp]\n'])
def test_an_unusable_match_entry_is_skipped(ws, text):
    (ws / "agency/clients/acme.yaml").write_text(text)
    assert in_ws(ws, "job", *ACME)["client_slug"] == "acme"
    assert in_ws(ws, "job", "--client", "Other", "--role", "Dev")["client_slug"] == "other"


# Script contract


def test_usage_errors_are_json_with_exit_2():
    code, out = run("job")
    assert code == 2
    assert out["code"] == "usage"


def test_script_uses_only_the_standard_library():
    done = subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT), "resolve"],
        capture_output=True,
        text=True,
        cwd="/",
    )
    assert done.returncode == 0, done.stderr
