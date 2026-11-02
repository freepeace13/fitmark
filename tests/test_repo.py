"""Repository checks: manifests, skill lint, fixture privacy and size budget."""

import json
import re
import warnings
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = ROOT / ".claude-plugin"
SYNTHETIC_DOMAINS = {"example.com", "example.org", "example.net"}
NON_RUNTIME_BUDGET_BYTES = 5 * 1024 * 1024
EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
PHONE = re.compile(r"(?<![\w.-])\+?\d[\d ()-]{8,}\d(?![\w-])")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def manifest(name):
    return json.loads((PLUGIN_DIR / name).read_text())


def frontmatter_keys(text):
    match = FRONTMATTER.match(text)
    if not match:
        return set()
    return set(re.findall(r"^([\w-]+):\s*\S", match[1], re.M))


def skill_names():
    skills = ROOT / "skills"
    return {p.name for p in skills.iterdir() if p.is_dir()} if skills.is_dir() else set()


def test_names_and_versions_match():
    plugin = manifest("plugin.json")
    market = manifest("marketplace.json")
    entries = [e for e in market["plugins"] if e["name"] == plugin["name"]]
    assert market["name"] == plugin["name"] == "fitmark"
    assert len(entries) == 1
    assert entries[0]["source"] == "./"
    assert entries[0]["version"] == plugin["version"]


def test_only_manifests_inside_plugin_dir():
    assert {p.name for p in PLUGIN_DIR.iterdir()} == {"marketplace.json", "plugin.json"}


@pytest.mark.parametrize("name", sorted(skill_names()))
def test_skill_has_name_and_description(name):
    path = ROOT / "skills" / name / "SKILL.md"
    assert path.is_file(), f"{name} has no SKILL.md"
    assert {"name", "description"} <= frontmatter_keys(path.read_text())


def test_no_commands_folder():
    assert not (ROOT / "commands").exists(), "Skills provide the /fitmark: shortcuts"


def test_no_bin_folder():
    assert not (ROOT / "bin").exists(), "claude.ai and Cowork won't install a plugin with bin/"


def test_workspace_setting_is_declared():
    option = manifest("plugin.json")["userConfig"]["workspace"]
    assert option["type"] == "directory"
    assert option["default"] == "~/Fitmark"


@pytest.mark.parametrize("name", sorted(skill_names()))
def test_skill_gets_its_paths_from_the_workspace_script(name):
    text = (ROOT / "skills" / name / "SKILL.md").read_text()
    assert "workspace.py" in text
    assert "resolve" in text


def test_folder_setting_is_never_double_quoted_for_the_shell():
    # With no saved value the text stays literal, and "${user_config.x}" is a shell error.
    files = [ROOT / "docs" / "SKILL_GUIDELINES.md", *(ROOT / "skills").glob("*/SKILL.md")]
    for path in files:
        assert '"${user_config.' not in path.read_text(), path


@pytest.mark.parametrize("path", sorted((ROOT / "schemas").glob("*.json")), ids=lambda p: p.name)
def test_schemas_are_valid(path):
    jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text()))


def test_fixtures_contain_no_real_contact_details():
    problems = []
    for path in (ROOT / "fixtures").rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        problems += [
            f"{path}: email at {domain}"
            for domain in EMAIL.findall(text)
            if domain.lower() not in SYNTHETIC_DOMAINS
        ]
        problems += [f"{path}: phone {phone}" for phone in PHONE.findall(text)]
    assert not problems, "\n".join(problems)


def test_non_runtime_size_budget():
    size = sum(
        path.stat().st_size
        for folder in ("fixtures", "tests", "docs")
        for path in (ROOT / folder).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    if size > NON_RUNTIME_BUDGET_BYTES:
        warnings.warn(f"Non-runtime folders use {size} bytes", stacklevel=1)
