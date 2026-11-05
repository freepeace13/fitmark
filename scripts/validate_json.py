#!/usr/bin/env python3
"""Validate a Fitmark JSON document against its schema and business rules.

Prints {"valid", "errors", "warnings", "skipped"} and exits 0 when valid, 1 when invalid.
Usage problems print {"error": ...} and exit 2.
"""

import argparse
import json
import sys
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"
DEFAULT_MAX_MUST_HAVES = 6


def dicts(doc, key):
    value = doc.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def schema_errors(doc, schema):
    from jsonschema import Draft202012Validator

    found = Draft202012Validator(schema).iter_errors(doc)
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '(root)'}: {error.message}"
        for error in sorted(found, key=lambda error: list(map(str, error.absolute_path)))
    ]


def duplicate_id_errors(must_haves, nice_to_haves):
    seen = set()
    errors = []
    for item in must_haves + nice_to_haves:
        item_id = item.get("id")
        if item_id in seen:
            errors.append(f"duplicate requirement id {item_id}")
        seen.add(item_id)
    return errors, seen


def must_have_errors(must_haves):
    errors = []
    for item in must_haves:
        if not item.get("client_quote") and item.get("inferred") is not True:
            errors.append(f"{item.get('id')}: must-have needs client_quote or inferred: true")
    return errors


def library_errors(requirements):
    return [
        f"{item.get('id')}: library criteria must set inferred: true"
        for item in requirements
        if item.get("source") == "library" and item.get("inferred") is not True
    ]


def rubric_errors(rubric, known_ids):
    errors = [
        f"rubric criterion {item.get('criterion_id')} is not a must-have or nice-to-have"
        for item in rubric
        if item.get("criterion_id") not in known_ids
    ]
    weights = [item.get("weight") for item in rubric]
    if not all(isinstance(weight, (int, float)) for weight in weights):
        errors.append("rubric weights must be numbers")
    elif sum(weights) != 100:
        errors.append(f"rubric weights sum to {sum(weights)}, expected 100")
    return errors


def version_errors(doc, previous):
    version = doc.get("version")
    if not isinstance(version, int):
        return []
    errors = []
    if version > 1 and not any(item.get("version") == version for item in dicts(doc, "changelog")):
        errors.append(f"version {version} has no changelog entry")
    if previous is not None:
        if previous.get("spec_id") != doc.get("spec_id"):
            errors.append("spec_id differs from the previous version")
        if version != previous.get("version", 0) + 1:
            errors.append(
                f"version {version} does not follow previous version {previous.get('version')}"
            )
    return errors


def job_spec_rules(doc, previous, max_must_haves):
    must_haves = dicts(doc, "must_haves")
    nice_to_haves = dicts(doc, "nice_to_haves")
    errors, known_ids = duplicate_id_errors(must_haves, nice_to_haves)
    errors += must_have_errors(must_haves)
    errors += library_errors(must_haves + nice_to_haves)
    errors += rubric_errors(dicts(doc, "rubric"), known_ids)
    errors += version_errors(doc, previous)
    warnings = []
    if len(must_haves) > max_must_haves:
        warnings.append(f"{len(must_haves)} must-haves exceeds the limit of {max_must_haves}")
    return errors, warnings


def validate(doc, schema_name, previous=None, max_must_haves=DEFAULT_MAX_MUST_HAVES):
    schema = json.loads((SCHEMAS / f"{schema_name}.schema.json").read_text())
    skipped = []
    try:
        errors = schema_errors(doc, schema)
    except ImportError:
        errors = []
        skipped.append("schema check: jsonschema is not installed")
    warnings = []
    if schema_name == "job-spec" and isinstance(doc, dict):
        rule_errors, warnings = job_spec_rules(doc, previous, max_must_haves)
        errors += rule_errors
    return {"valid": not errors, "errors": errors, "warnings": warnings, "skipped": skipped}


def fail(message):
    print(json.dumps({"error": message}))
    return 2


def read_json(path):
    return json.loads(Path(path).read_text())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--schema", required=True, help="schema name, such as job-spec")
    parser.add_argument("--previous", help="previous version of the document")
    parser.add_argument("--max-must-haves", type=int, default=DEFAULT_MAX_MUST_HAVES)
    args = parser.parse_args(argv)

    if not (SCHEMAS / f"{args.schema}.schema.json").is_file():
        return fail(f"unknown schema: {args.schema}")
    try:
        doc = read_json(args.file)
        previous = read_json(args.previous) if args.previous else None
    except (OSError, ValueError) as error:
        return fail(f"cannot read input: {error}")

    result = validate(doc, args.schema, previous, args.max_must_haves)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
