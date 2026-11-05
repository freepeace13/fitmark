"""Tests for scripts/validate_json.py using the golden job specs."""

import builtins
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = ROOT / "fixtures" / "expected"

spec = importlib.util.spec_from_file_location("validate_json", ROOT / "scripts/validate_json.py")
validate_json = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_json)


def golden(name):
    return json.loads((EXPECTED / name).read_text())


@pytest.fixture
def v1():
    return golden("spec-acme-senior-laravel-dev-v1.json")


@pytest.fixture
def v2():
    return golden("spec-acme-senior-laravel-dev-v2.json")


def errors_for(doc, previous=None):
    return validate_json.validate(doc, "job-spec", previous)["errors"]


@pytest.mark.parametrize("path", sorted(EXPECTED.glob("spec-*.json")), ids=lambda p: p.name)
def test_golden_specs_are_valid(path):
    result = validate_json.validate(json.loads(path.read_text()), "job-spec")
    assert result == {"valid": True, "errors": [], "warnings": [], "skipped": []}


def test_update_follows_previous_version(v1, v2):
    assert errors_for(v2, previous=v1) == []


def test_weights_must_sum_to_100(v1):
    v1["rubric"][0]["weight"] = 41
    assert errors_for(v1) == ["rubric weights sum to 101, expected 100"]


def test_rubric_criterion_must_exist(v1):
    v1["rubric"][0]["criterion_id"] = "mh-9"
    assert errors_for(v1) == ["rubric criterion mh-9 is not a must-have or nice-to-have"]


def test_must_have_needs_quote_or_inferred(v1):
    v1["must_haves"][0]["client_quote"] = None
    assert errors_for(v1) == ["mh-1: must-have needs client_quote or inferred: true"]
    v1["must_haves"][0]["inferred"] = True
    assert errors_for(v1) == []


def test_library_criteria_must_be_inferred(v1):
    v1["nice_to_haves"][0]["source"] = "library"
    assert errors_for(v1) == ["nh-1: library criteria must set inferred: true"]


def test_duplicate_ids_are_rejected(v1):
    v1["must_haves"].append(copy.deepcopy(v1["must_haves"][0]))
    assert errors_for(v1) == ["duplicate requirement id mh-1"]


def test_later_version_needs_changelog(v2):
    v2["changelog"] = []
    assert errors_for(v2) == ["version 2 has no changelog entry"]


def test_version_must_increment_by_one(v1, v2):
    v1["version"] = 2
    v1["changelog"] = v2["changelog"]
    previous = copy.deepcopy(v1)
    assert errors_for(v2, previous=previous) == ["version 2 does not follow previous version 2"]


def test_spec_id_must_match_previous(v1, v2):
    v1["spec_id"] = "other-role"
    assert errors_for(v2, previous=v1) == ["spec_id differs from the previous version"]


def test_too_many_must_haves_is_a_warning(v1):
    result = validate_json.validate(v1, "job-spec", max_must_haves=1)
    assert result["valid"] is True
    assert result["warnings"] == ["2 must-haves exceeds the limit of 1"]


def test_schema_violation_is_reported(v1):
    v1["status"] = "sent"
    assert any(error.startswith("status:") for error in errors_for(v1))


def test_rules_still_run_without_jsonschema(v1, monkeypatch):
    real_import = builtins.__import__

    def no_jsonschema(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_jsonschema)
    v1["rubric"][0]["weight"] = 41
    result = validate_json.validate(v1, "job-spec")
    assert result["skipped"] == ["schema check: jsonschema is not installed"]
    assert result["errors"] == ["rubric weights sum to 101, expected 100"]


def test_cli_exit_codes(tmp_path, capsys, v1):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(v1))
    assert validate_json.main([str(good), "--schema", "job-spec"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True

    v1["rubric"] = []
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(v1))
    assert validate_json.main([str(bad), "--schema", "job-spec"]) == 1
    assert json.loads(capsys.readouterr().out)["valid"] is False

    assert validate_json.main([str(good), "--schema", "nope"]) == 2
    assert "error" in json.loads(capsys.readouterr().out)
    assert validate_json.main([str(tmp_path / "missing.json"), "--schema", "job-spec"]) == 2
