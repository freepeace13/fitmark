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
ACME_ID = "acme-corp--senior-laravel-developer"


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
    job = in_ws(ws, "job", *ACME, "--create", "--ref", "r")
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
        "job", "--client", "evil", "--role", "r", "--create", "--ref", "r",
        "--workspace", ws, "--plugin-root", plugin,
    )  # fmt: skip
    assert code == 1
    assert out["code"] == "inside_plugin"
    assert list(plugin.iterdir()) == []


@pytest.mark.parametrize("sub", ["intake", "spec", "candidates"])
def test_guard_refuses_a_job_subfolder_linked_into_the_plugin(ws, tmp_path, sub):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    job_dir = Path(in_ws(ws, "job", *ACME, "--create", "--ref", "r")["job_dir"])
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


def test_guard_ignores_case_differences(tmp_path):
    data = tmp_path / "PluginData"
    data.mkdir()
    out = fail("init", "--path", tmp_path / "plugindata" / "ws", "--plugin-data", data)
    assert out["code"] == "inside_plugin"
    assert not (data / "ws").exists()


def test_guard_ignores_case_when_the_protected_folder_does_not_exist_yet(tmp_path):
    out = fail(
        "init", "--path", tmp_path / "plugindata" / "ws", "--plugin-data", tmp_path / "PluginData"
    )
    assert out["code"] == "inside_plugin"


def test_record_refuses_a_job_folder_linked_into_the_plugin(ws, tmp_path):
    plugin = tmp_path / "plugin"
    (plugin / "job").mkdir(parents=True)
    job_file = plugin / "job" / "job.yaml"
    job_file.write_text(
        json.dumps(
            {
                "spec_id": "a-b", "client": "a", "client_slug": "a", "job_slug": "b", "role": "b",
                "status": "intake", "current_spec_version": 0, "submittals": [],
            }
        )
    )  # fmt: skip
    before = job_file.read_text()
    (ws / "clients" / "a").mkdir()
    (ws / "clients" / "a" / "b").symlink_to(plugin / "job")
    code, out = run(
        "record", "--job", "a-b", "--event", "status", "--status", "closed",
        "--workspace", ws, "--plugin-root", plugin,
    )  # fmt: skip
    assert code == 1
    assert out["code"] == "inside_plugin"
    assert job_file.read_text() == before
    assert sorted(p.name for p in (plugin / "job").iterdir()) == ["job.yaml"]


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
    one = in_ws(ws, "job", "--client", "Acme", "--role", first, "--create", "--ref", "r")
    two = in_ws(ws, "job", "--client", "Acme", "--role", second, "--create", "--ref", "r")
    assert two["exists"] is False
    assert one["spec_id"] != two["spec_id"]
    assert one["job_dir"] != two["job_dir"]


def test_clients_that_differ_only_by_a_symbol_stay_separate(ws):
    one = in_ws(ws, "job", "--client", "C++ Corp", "--role", "Dev")
    two = in_ws(ws, "job", "--client", "C# Corp", "--role", "Dev")
    assert one["client_slug"] != two["client_slug"]


@pytest.mark.parametrize("spelling", ["senior developer", "Senior-Developer", "Senior  Developer."])
def test_spelling_variants_of_a_role_are_the_same_job(ws, spelling):
    one = in_ws(
        ws, "job", "--client", "Acme", "--role", "Senior Developer", "--create", "--ref", "r"
    )
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
        ("Northwind Traders", "Finance Manager", "northwind-traders--finance-manager"),
        ("Café Noël", "C++ / Rust Dev", "cafe-noel--c-plus-plus-rust-dev"),
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
    out = in_ws(ws, "job", *ACME, "--create", "--ref", "r")
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
    out = in_ws(ws, "job", *ACME, "--create", "--ref", "r")
    assert out["next_spec_version"] == 2
    Path(out["outputs"]["spec_json"]).write_text("{}")
    Path(out["outputs"]["changes_from_previous"]).write_text("x")


def test_job_without_create_makes_no_version_folder(ws):
    saved_spec(ws)
    assert not Path(in_ws(ws, "job", *ACME)["outputs"]["spec_json"]).parent.exists()


def test_job_create_needs_a_ref(ws):
    code, out = run("job", *ACME, "--create", "--workspace", ws)
    assert code == 1
    assert out["code"] == "usage"


def test_a_retry_with_the_same_ref_keeps_the_unused_version(ws):
    args = ("job", *ACME, "--create", "--ref", "intake-1")
    assert in_ws(ws, *args)["next_spec_version"] == 1
    assert in_ws(ws, *args)["next_spec_version"] == 1


def test_another_ref_gets_another_version(ws):
    assert in_ws(ws, "job", *ACME, "--create", "--ref", "a")["next_spec_version"] == 1
    assert in_ws(ws, "job", *ACME, "--create", "--ref", "b")["next_spec_version"] == 2
    assert in_ws(ws, "job", *ACME, "--create", "--ref", "a")["next_spec_version"] == 1


def test_a_partly_written_version_is_never_overwritten(ws):
    first = in_ws(ws, "job", *ACME, "--create", "--ref", "a")
    Path(first["outputs"]["spec_document"]).write_text("doc")
    second = in_ws(ws, "job", *ACME, "--create", "--ref", "a")
    assert second["next_spec_version"] == 2
    assert second["outputs"]["spec_document"] != first["outputs"]["spec_document"]


def test_changes_are_measured_from_the_last_saved_version(ws):
    saved_spec(ws)
    in_ws(ws, "job", *ACME, "--create", "--ref", "abandoned")
    out = in_ws(ws, "job", *ACME, "--create", "--ref", "next")
    assert out["next_spec_version"] == 3
    assert out["outputs"]["changes_from_previous"].endswith("spec/v3/changes-from-v1.md")


def test_parallel_job_runs_get_different_versions(ws):
    running = [
        start("job", *ACME, "--create", "--ref", f"run-{n}", "--workspace", ws) for n in range(8)
    ]
    versions = []
    for process in running:
        out, err = process.communicate()
        assert process.returncode == 0, err
        versions.append(json.loads(out)["next_spec_version"])
    assert sorted(versions) == list(range(1, 9))


def test_a_corrupt_job_in_its_original_folder_is_not_duplicated(ws):
    saved = in_ws(ws, "job", "--client", "Old", "--role", "Dev", "--create", "--ref", "r")
    job_file = Path(saved["job_dir"]) / "job.yaml"
    job_file.write_text("{}")
    (ws / "agency/clients/new.yaml").write_text("match: [Old]\n")
    code, out = run(
        "job", "--client", "Old", "--role", "Dev", "--create", "--ref", "r", "--workspace", ws
    )
    assert code == 1
    assert out["code"] == "bad_job_file"
    assert not (ws / "clients" / "new").exists()


@pytest.mark.parametrize(
    ("one", "two"), [("राम", "रीम"), ("カラ", "ガラ"), ("กา", "กี"), ("Ивай", "Ивак")]
)
def test_non_latin_names_that_differ_get_different_folders(ws, one, two):
    first = in_ws(ws, "job", "--client", one, "--role", "Dev")
    second = in_ws(ws, "job", "--client", two, "--role", "Dev")
    assert first["client_slug"] != second["client_slug"]


def test_latin_accents_still_fold(ws):
    assert in_ws(ws, "job", "--client", "Café Noël", "--role", "Dev")["client_slug"] == "cafe-noel"


def test_a_name_of_only_marks_is_refused(ws):
    code, out = run("job", "--client", "\u0301\u0301", "--role", "Dev", "--workspace", ws)
    assert code == 1
    assert out["code"] == "bad_name"


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
    job = in_ws(ws, "job", *ACME, "--create", "--ref", "r")
    Path(job["outputs"]["spec_json"]).write_text("{}")
    assert in_ws(ws, "job", *ACME)["next_spec_version"] == 2


def test_create_is_stable_when_run_twice_before_a_save(ws):
    in_ws(ws, "job", *ACME, "--create", "--ref", "r")
    assert in_ws(ws, "job", *ACME, "--create", "--ref", "r")["next_spec_version"] == 1


def test_document_name_cannot_escape_its_folder(ws):
    out = in_ws(ws, "job", "--client", "A/B", "--role", "../../etc", "--create", "--ref", "r")
    doc = Path(out["outputs"]["spec_document"])
    assert doc.parent == Path(out["job_dir"]) / "spec" / "v1"


@pytest.mark.parametrize("name", ["", "!!!", ".."])
def test_a_name_with_nothing_to_slug_is_refused(ws, name):
    code, out = run("job", "--client", name, "--role", "Dev", "--workspace", ws)
    assert code == 1
    assert out["code"] == "bad_name"


def test_names_that_join_the_same_way_are_different_jobs(ws):
    one = in_ws(ws, "job", "--client", "Blue Sky", "--role", "Dev", "--create", "--ref", "r")
    two = in_ws(ws, "job", "--client", "Blue", "--role", "Sky Dev", "--create", "--ref", "r")
    assert one["spec_id"] != two["spec_id"]
    assert two["exists"] is False


# candidate


def test_candidate_needs_a_saved_spec(ws):
    in_ws(ws, "job", *ACME, "--create", "--ref", "r")
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
    out = in_ws(
        ws,
        "candidate",
        "--job",
        ACME_ID,
        "--name",
        "Jane Doe",
        "--new",
        "--ref",
        "cv-2",
        "--create",
    )
    assert out["slug"] == "jane-doe-2"
    assert Path(out["candidate_dir"]).is_dir()


def test_retrying_new_with_the_same_ref_is_the_same_person(ws):
    saved_spec(ws)
    saved_submittal(ws)
    args = ("candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--ref", "cv-2")
    assert in_ws(ws, *args, "--create")["slug"] == "jane-doe-2"
    out = in_ws(ws, *args, "--create")
    assert out["slug"] == "jane-doe-2"
    assert out["exists"] is True


def test_new_with_another_ref_is_another_person(ws):
    saved_spec(ws)
    saved_submittal(ws)
    args = ("candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--create")
    assert in_ws(ws, *args, "--ref", "cv-2")["slug"] == "jane-doe-2"
    assert in_ws(ws, *args, "--ref", "cv-3")["slug"] == "jane-doe-3"
    assert in_ws(ws, *args, "--ref", "cv-2")["slug"] == "jane-doe-2"


def test_a_lone_numbered_folder_is_the_existing_person(ws):
    saved_spec(ws)
    cand = saved_submittal(ws, "Bob Lee")
    folder = Path(cand["candidate_dir"])
    moved = folder.with_name("bob-lee-2")
    folder.rename(moved)
    out = in_ws(ws, "candidate", "--job", ACME_ID, "--name", "Bob Lee")
    assert out["exists"] is True
    assert out["slug"] == "bob-lee-2"
    (moved / "submittal-s1-9.json").write_text("{}")
    code, recorded = run(
        "record", "--job", ACME_ID, "--event", "submittal_saved", "--candidate", "Bob Lee",
        "--file", "submittal-s1-9.json", "--workspace", ws,
    )  # fmt: skip
    assert code == 0, recorded


def test_new_needs_a_ref(ws):
    saved_spec(ws)
    code, out = run("candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--workspace", ws)
    assert code == 1
    assert out["code"] == "usage"


def test_parallel_new_keeps_different_people_apart(ws):
    saved_spec(ws)
    saved_submittal(ws, "Bob Ray")
    running = [
        start("candidate", "--job", ACME_ID, "--name", "Bob Ray", "--new", "--ref", f"cv-{n}",
              "--create", "--workspace", ws)
        for n in range(8)
    ]  # fmt: skip
    slugs = []
    for process in running:
        out, err = process.communicate()
        assert process.returncode == 0, err
        slugs.append(json.loads(out)["slug"])
    assert len(set(slugs)) == 8


def test_a_shared_name_must_say_which_person(ws):
    saved_spec(ws)
    saved_submittal(ws)
    in_ws(
        ws,
        "candidate",
        "--job",
        ACME_ID,
        "--name",
        "Jane Doe",
        "--new",
        "--ref",
        "cv-2",
        "--create",
    )
    code, out = run("candidate", "--job", ACME_ID, "--name", "Jane Doe", "--workspace", ws)
    assert code == 1
    assert out["code"] == "ambiguous_candidate"
    assert "jane-doe, jane-doe-2" in out["error"]


def test_slug_addresses_the_second_person_with_their_real_name(ws):
    saved_spec(ws)
    saved_submittal(ws)
    in_ws(
        ws,
        "candidate",
        "--job",
        ACME_ID,
        "--name",
        "Jane Doe",
        "--new",
        "--ref",
        "cv-2",
        "--create",
    )
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
    in_ws(ws, "job", *ACME, "--create", "--ref", "r")
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


def two_janes(ws):
    saved_spec(ws)
    first = saved_submittal(ws)
    second = in_ws(
        ws,
        "candidate",
        "--job",
        ACME_ID,
        "--name",
        "Jane Doe",
        "--new",
        "--ref",
        "cv-2",
        "--create",
    )
    Path(second["submittal_path"]).write_text("{}")
    return first, second


def record_submittal(ws, candidate, file):
    return run(
        "record", "--job", ACME_ID, "--event", "submittal_saved", "--candidate", candidate,
        "--file", file, "--workspace", ws,
    )  # fmt: skip


def recorded_people(ws):
    return [s["candidate"] for s in in_ws(ws, "status")["jobs"][0]["submittals"]]


def test_record_credits_the_person_whose_folder_holds_the_file(ws):
    _, second = two_janes(ws)
    code, out = record_submittal(ws, "Jane Doe", second["submittal_path"])
    assert code == 0, out
    assert recorded_people(ws) == ["jane-doe", "jane-doe-2"]


def test_record_refuses_a_shared_name_with_no_folder(ws):
    two_janes(ws)
    code, out = record_submittal(ws, "Jane Doe", "submittal-s1.json")
    assert code == 1
    assert out["code"] == "ambiguous_candidate"
    assert recorded_people(ws) == ["jane-doe"]


def test_record_refuses_a_file_in_another_persons_folder(ws):
    _, second = two_janes(ws)
    code, out = record_submittal(ws, "jane-doe", second["submittal_path"])
    assert code == 1
    assert out["code"] == "bad_file"


def test_record_accepts_the_exact_folder_name(ws):
    two_janes(ws)
    code, out = record_submittal(ws, "jane-doe-2", "submittal-s1.json")
    assert code == 0, out
    assert recorded_people(ws) == ["jane-doe", "jane-doe-2"]


def test_empty_spec_cannot_be_recorded_and_uses_no_version(ws):
    job = in_ws(ws, "job", *ACME, "--create", "--ref", "r")
    Path(job["outputs"]["spec_json"]).write_text("")
    code, out = run(
        "record", "--job", ACME_ID, "--event", "spec_saved", "--version", 1, "--workspace", ws
    )
    assert code == 1
    assert out["code"] == "missing_file"
    assert in_ws(ws, "job", *ACME, "--ref", "r")["next_spec_version"] == 1


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
    in_ws(ws, "job", "--client", "Northwind", "--role", "Analyst", "--create", "--ref", "r")
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
    code, out = run(
        "job", "--client", "Other", "--role", "Broken", "--create", "--ref", "r", "--workspace", ws
    )
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


def test_a_job_with_an_unusable_client_name_blocks_only_itself(ws):
    saved_spec(ws)
    other_job(ws, json.dumps(
        {
            "spec_id": "x", "client": "_", "client_slug": "x", "job_slug": "y", "role": "y",
            "status": "intake", "current_spec_version": 0, "submittals": [],
        }
    ))  # fmt: skip
    assert in_ws(ws, "job", *ACME)["exists"] is True
    out = in_ws(ws, "status", "--client", "Acme Corp")
    assert [j["spec_id"] for j in out["jobs"]] == [ACME_ID]
    assert len(out["unreadable_jobs"]) == 1


def test_an_unreadable_client_rule_file_is_skipped(ws):
    saved_spec(ws)
    (ws / "agency/clients/dir.yaml").mkdir()
    (ws / "agency/clients/gone.yaml").symlink_to(ws / "missing")
    assert in_ws(ws, "job", *ACME)["exists"] is True
    assert in_ws(ws, "status", "--client", "Acme Corp")["jobs"]


# Always JSON


def test_a_version_folder_with_an_odd_digit_is_ignored(ws):
    job = in_ws(ws, "job", *ACME, "--create", "--ref", "r")
    odd = Path(job["job_dir"]) / "spec" / "v²"
    odd.mkdir()
    (odd / "spec.json").write_text("{}")
    assert in_ws(ws, "job", *ACME, "--ref", "r")["next_spec_version"] == 1


def test_a_symlink_loop_as_the_setting_still_gives_json(tmp_path):
    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    code, out = run("resolve", "--workspace", loop, cwd=tmp_path, home=tmp_path)
    assert code in (0, 1), out


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell")
def test_closed_stdin_still_gives_json(tmp_path):
    done = subprocess.run(
        ["/bin/sh", "-c", f'"{sys.executable}" "{SCRIPT}" resolve <&-'],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["status"] == "no_workspace"


# Passing untrusted values safely


def through_shell(command, payload, tmp_path):
    """Run a command the documented way: values as JSON in a quoted heredoc, in a real shell."""
    text = (
        f'"{sys.executable}" "{SCRIPT}" {command} --args-stdin <<\'FITMARK_ARGS\'\n'
        f"{json.dumps(payload, ensure_ascii=False)}\nFITMARK_ARGS\n"
    )
    done = subprocess.run(
        ["/bin/sh", "-c", text],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tmp_path,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )
    return done.returncode, json.loads(done.stdout)


def test_a_setting_with_an_apostrophe_reaches_the_script_intact(tmp_path):
    folder = str(tmp_path / "Recruiter's Files")
    code, out = through_shell("resolve", {"workspace": folder}, tmp_path)
    assert code == 0
    assert out["suggested_path"] == str(Path(folder).resolve())


HOSTILE = "x'; touch pwned; '$(touch pwned)`touch pwned`\"; touch pwned; \""


@pytest.mark.parametrize("key", ["name", "ref"])
def test_text_from_a_cv_cannot_run_a_command(ws, tmp_path, key):
    saved_spec(ws)
    payload = {
        "job": ACME_ID, "workspace": str(ws), "name": "Jane Doe", "new": True, "ref": "cv",
        "create": True, key: HOSTILE,
    }  # fmt: skip
    code, out = through_shell("candidate", payload, tmp_path)
    assert code == 0, out
    assert not (tmp_path / "pwned").exists()


def test_a_setting_cannot_run_a_command(tmp_path):
    code, out = through_shell("resolve", {"workspace": HOSTILE}, tmp_path)
    assert code == 0, out
    assert out["status"] == "no_workspace"
    assert not (tmp_path / "pwned").exists()


def test_a_setting_of_several_lines_cannot_end_the_block_or_be_used(tmp_path):
    value = "x\nFITMARK_ARGS\ntouch pwned"
    code, out = through_shell("resolve", {"workspace": value}, tmp_path)
    assert code == 1
    assert out["code"] == "bad_setting"
    assert not (tmp_path / "pwned").exists()


@pytest.mark.parametrize("value", ["", "${user_config.workspace}"])
def test_an_unset_setting_through_the_shell_counts_as_unset(tmp_path, value):
    code, out = through_shell("resolve", {"workspace": value}, tmp_path)
    assert code == 0
    assert out["suggested_path"] == str(tmp_path.resolve() / "Fitmark")


def test_a_value_starting_with_a_dash_is_a_value(ws, tmp_path):
    payload = {"workspace": str(ws), "client": "--create", "role": "-x"}
    code, out = through_shell("job", payload, tmp_path)
    assert code == 0, out
    assert out["client_slug"] == "create"
    assert out["exists"] is False
    assert not (ws / "clients" / "create").exists()


def test_flags_numbers_and_real_names_arrive_correctly(ws, tmp_path):
    payload = {
        "workspace": str(ws), "client": "株式会社 O'Brien", "role": "Dev", "create": True,
        "ref": "r",
    }  # fmt: skip
    code, out = through_shell("job", payload, tmp_path)
    assert code == 0, out
    Path(out["outputs"]["spec_json"]).write_text("{}")
    payload = {"workspace": str(ws), "job": out["spec_id"], "event": "spec_saved", "version": 1}
    code, recorded = through_shell("record", payload, tmp_path)
    assert code == 0, recorded
    assert recorded["job"]["client"] == "株式会社 O'Brien"
    assert recorded["job"]["current_spec_version"] == 1


@pytest.mark.parametrize("payload", ["not json", "[1]", '{"name": ["x"]}', '{"no such!": "x"}'])
def test_bad_arguments_are_a_json_error(tmp_path, payload):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "resolve", "--args-stdin"],
        input=payload,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert done.returncode == 1
    assert json.loads(done.stdout)["code"] == "bad_args"


def test_an_unknown_argument_is_a_usage_error(tmp_path):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "resolve", "--args-stdin"],
        input='{"nope": "x"}',
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert done.returncode == 2
    assert json.loads(done.stdout)["code"] == "usage"


# Running at the same time

HOLD_LOCK = """
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_CREAT | os.O_WRONLY)
fcntl.flock(fd, fcntl.LOCK_EX)
print("held", flush=True)
time.sleep(60)
"""


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


def test_a_lock_left_by_a_killed_run_does_not_block_recording(ws):
    saved_spec(ws)
    lock = Path(in_ws(ws, "job", *ACME)["job_dir"]) / ".job.lock"
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLD_LOCK, str(lock)], stdout=subprocess.PIPE, text=True
    )
    assert holder.stdout.readline().strip() == "held"
    holder.kill()
    holder.communicate()
    out = in_ws(ws, "record", "--job", ACME_ID, "--event", "status", "--status", "confirmed")
    assert out["job"]["status"] == "confirmed"


def test_a_lock_held_by_a_live_run_is_respected(ws):
    saved_spec(ws)
    lock = Path(in_ws(ws, "job", *ACME)["job_dir"]) / ".job.lock"
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLD_LOCK, str(lock)], stdout=subprocess.PIPE, text=True
    )
    assert holder.stdout.readline().strip() == "held"
    try:
        code, out = run(
            "record", "--job", ACME_ID, "--event", "status", "--status", "closed",
            "--workspace", ws,
        )  # fmt: skip
    finally:
        holder.kill()
        holder.communicate()
    assert code == 1
    assert out["code"] == "job_locked"


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
    out = run_with_umask(umask, "job", *ACME, "--create", "--ref", "r", "--workspace", root)
    assert (root / "fitmark.yaml").stat().st_mode & 0o777 == mode
    assert (Path(out["job_dir"]) / "job.yaml").stat().st_mode & 0o777 == mode


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_reserved_files_are_not_executable(ws):
    saved_spec(ws)
    out = run_with_umask(
        0o022, "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--create", "--workspace", ws
    )
    for key in ("submittal_path", "document_path"):
        assert Path(out[key]).stat().st_mode & 0o777 == 0o644


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_changing_a_job_keeps_its_permissions(ws):
    job_file = Path(in_ws(ws, "job", *ACME, "--create", "--ref", "r")["job_dir"]) / "job.yaml"
    job_file.chmod(0o660)
    in_ws(ws, "record", "--job", ACME_ID, "--event", "status", "--status", "confirmed")
    assert job_file.stat().st_mode & 0o777 == 0o660


# Encoding


LATIN1 = {"LC_ALL": "en_US.ISO8859-1", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}


def test_non_ascii_names_work_under_a_non_utf8_locale(ws):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "job", "--client", "株式会社", "--role", "Dev",
         "--create", "--ref", "r", "--workspace", str(ws)],
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
    code, out = run(
        "job", "--client", "Acme", "--role", "Dev", "--create", "--ref", "r", "--workspace", ws
    )
    assert code == 1
    assert out["error"]
    assert [p.name for p in job_dir.glob(".*") if p.name != ".job.lock"] == []


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


@pytest.mark.parametrize(
    "text",
    [
        "match: [Acme Corp] # legal name\n",
        "match:   # names\n  - Acme Corp # legal\n\n  - ACo\n",
        "match: [\n  Acme Corp, # legal\n  ACo\n]\nname: Acme\n",
        "match: Acme Corp\n",
        "name: x\nmatch:\n- Acme Corp\nother: y\n",
    ],
)
def test_valid_yaml_match_lists_are_understood(ws, text):
    (ws / "agency/clients/acme.yaml").write_text(text)
    assert in_ws(ws, "job", *ACME)["client_slug"] == "acme"
    assert in_ws(ws, "job", "--client", "Other", "--role", "Dev")["client_slug"] == "other"


def test_hash_and_apostrophe_inside_names_are_kept(ws):
    (ws / "agency/clients/x.yaml").write_text("match:\n  - C# Corp\n  - O'Brien # legal\n")
    assert in_ws(ws, "job", "--client", "C# Corp", "--role", "Dev")["client_slug"] == "x"
    assert in_ws(ws, "job", "--client", "OBrien", "--role", "Dev")["client_slug"] != "x"
    assert in_ws(ws, "job", "--client", "O'Brien", "--role", "Dev")["client_slug"] == "x"


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


# Spec versions after a later save


def test_a_retry_after_a_later_save_gets_a_newer_version(ws):
    in_ws(ws, "job", *ACME, "--create", "--ref", "a")
    in_ws(ws, "job", *ACME, "--create", "--ref", "b")
    Path(ws / "clients/acme-corp/senior-laravel-developer/spec/v2/spec.json").write_text("{}")
    in_ws(ws, "record", "--job", ACME_ID, "--event", "spec_saved", "--version", 2)
    retry = in_ws(ws, "job", *ACME, "--create", "--ref", "a")
    assert retry["next_spec_version"] == 3
    assert retry["outputs"]["changes_from_previous"].endswith("spec/v3/changes-from-v2.md")
    assert in_ws(ws, "job", *ACME, "--create", "--ref", "a")["next_spec_version"] == 3
    Path(retry["outputs"]["spec_json"]).write_text("{}")
    in_ws(ws, "record", "--job", ACME_ID, "--event", "spec_saved", "--version", 3)
    assert in_ws(ws, "job", *ACME)["current_spec_version"] == 3


def test_record_refuses_a_version_older_than_the_current_one(ws):
    old = in_ws(ws, "job", *ACME, "--create", "--ref", "a")
    in_ws(ws, "job", *ACME, "--create", "--ref", "b")
    Path(old["job_dir"], "spec/v2/spec.json").write_text("{}")
    in_ws(ws, "record", "--job", ACME_ID, "--event", "spec_saved", "--version", 2)
    Path(old["outputs"]["spec_json"]).write_text("{}")
    out = fail(
        "record", "--job", ACME_ID, "--event", "spec_saved", "--version", 1, "--workspace", ws
    )
    assert out["code"] == "stale_version"
    assert in_ws(ws, "job", *ACME)["current_spec_version"] == 2


def test_recording_the_current_version_again_is_allowed(ws):
    n = saved_spec(ws)
    in_ws(ws, "record", "--job", ACME_ID, "--event", "spec_saved", "--version", n)
    assert in_ws(ws, "job", *ACME)["current_spec_version"] == n


# Client rule files


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [("Foo Bar.yaml", "foo-bar"), ("a--b.yaml", "a-b"), ("Foo.Bar.yaml", "foo-bar")],
)
def test_a_rule_file_name_is_made_into_a_slug(ws, file_name, expected):
    (ws / "agency/clients" / file_name).write_text("match: Foo\n")
    out = in_ws(ws, "job", "--client", "Foo", "--role", "Dev")
    assert out["client_slug"] == expected
    assert out["spec_id"] == f"{expected}--dev"
    assert Path(out["job_dir"]) == ws.resolve() / "clients" / expected / "dev"


def test_a_rule_file_name_with_capitals_matches_its_client(ws):
    (ws / "agency/clients/Acme.yaml").write_text("name: Acme\n")
    assert in_ws(ws, "job", "--client", "Acme", "--role", "Dev")["client_slug"] == "acme"


def test_a_rule_file_name_with_no_letters_cannot_leave_the_clients_folder(ws):
    (ws / "agency/clients/...yaml").write_text("match: Baz\n")
    out = in_ws(ws, "job", "--client", "Baz", "--role", "Dev", "--create", "--ref", "r")
    assert out["client_slug"] == "baz"
    assert Path(out["job_dir"]) == ws.resolve() / "clients/baz/dev"
    assert not (ws / "dev").exists()


def test_a_file_named_for_the_client_beats_an_earlier_match_list(ws):
    (ws / "agency/clients/aaa.yaml").write_text("match: Zeta\n")
    (ws / "agency/clients/zeta.yaml").write_text("name: Zeta\n")
    out = in_ws(ws, "job", "--client", "Zeta", "--role", "Dev")
    assert out["client_slug"] == "zeta"
    assert out["spec_id"] == "zeta--dev"


# A repeated ref for different people


def new_person(ws, ref):
    return in_ws(
        ws, "candidate", "--job", ACME_ID, "--name", "Jane Doe", "--new", "--ref", ref, "--create"
    )


def test_a_ref_reused_after_work_is_saved_is_another_person(ws):
    saved_spec(ws)
    saved_submittal(ws)
    second = new_person(ws, "cv.pdf")
    assert second["slug"] == "jane-doe-2"
    Path(second["submittal_path"]).write_text("{}")
    assert new_person(ws, "cv.pdf")["slug"] == "jane-doe-3"


def test_a_ref_reused_after_a_cv_is_saved_is_another_person(ws):
    saved_spec(ws)
    saved_submittal(ws)
    second = new_person(ws, "cv.pdf")
    Path(second["source_dir"], "cv.pdf").write_text("cv")
    assert new_person(ws, "cv.pdf")["slug"] == "jane-doe-3"


def test_a_finder_file_is_not_a_persons_work(ws):
    saved_spec(ws)
    saved_submittal(ws)
    second = new_person(ws, "cv.pdf")
    Path(second["candidate_dir"], ".DS_Store").write_text("x")
    assert new_person(ws, "cv.pdf")["slug"] == "jane-doe-2"


# Options that stay on the command line


def with_stdin(payload, *args):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args), "--args-stdin"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return done.returncode, json.loads(done.stdout)


@pytest.mark.parametrize("key", ["plugin-data", "plugin-root", "args-stdin"])
def test_stdin_cannot_set_a_command_line_option(key):
    code, out = with_stdin({key: ""}, "resolve")
    assert code == 1
    assert out["code"] == "bad_args"


@pytest.mark.parametrize("key", ["plugin-data", "plugin-d", "plugin-da"])
def test_stdin_cannot_turn_off_the_data_folder_guard(tmp_path, key):
    data = tmp_path / "data"
    code, _ = with_stdin({key: "", "path": str(data), "agency": "A"}, "init", "--plugin-data", data)
    assert code != 0
    assert not (data / "fitmark.yaml").exists()
