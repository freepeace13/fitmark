"""Behaviour of scripts/workspace.py, run the way a skill runs it: as a subprocess."""

import json
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
    path = Path(job["outputs"]["spec_json"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
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


# job


@pytest.mark.parametrize(
    ("client", "role", "spec_id"),
    [
        ("Acme Corp", "Senior Laravel Developer", ACME_ID),
        ("Northwind Traders", "Finance Manager", "northwind-traders-finance-manager"),
        ("Café Noël", "C++ / Rust Dev", "cafe-noel-c-rust-dev"),
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
    path = Path(job["outputs"]["spec_json"])
    path.parent.mkdir(parents=True)
    path.write_text("{}")
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
