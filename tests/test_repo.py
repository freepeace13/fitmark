"""Repository checks: manifests, skill lint, fixture privacy and size budget."""

import json
import re
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = ROOT / ".claude-plugin"
SYNTHETIC_DOMAINS = {"example.com", "example.org", "example.net"}
NON_RUNTIME_BUDGET_BYTES = 5 * 1024 * 1024
EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
PHONE = re.compile(r"(?<![\w.-])\+?\d[\d ()-]{8,}\d(?![\w-])")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
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


def phone_numbers(text):
    return [match for match in PHONE.findall(text) if not ISO_DATE.fullmatch(match)]


def test_phone_scan_ignores_iso_dates_only():
    assert phone_numbers("created 2026-11-03, call +63 917 555 0100") == ["+63 917 555 0100"]


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


def test_commands_point_to_existing_skills():
    for command in (ROOT / "commands").glob("*.md"):
        text = command.read_text()
        assert any(name in text for name in skill_names()), f"{command.name} names no skill"


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
        problems += [f"{path}: phone {phone}" for phone in phone_numbers(text)]
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
