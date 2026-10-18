"""Validate the actual OpenAPI response schemas and positive/negative JSON fixtures.

No HTTP server is contacted. Run from any working directory; exit 0 means PASS.
"""

from __future__ import annotations

import argparse
import json
import sys
from importlib.metadata import version
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parent
SPEC_PATH = ROOT / "openapi.yaml"


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate object key: {key}")
        result[key] = value
    return result


class UniqueLoader(yaml.SafeLoader):
    """Prevent a duplicate YAML key from silently replacing a schema or path."""


def unique_mapping(loader, node):
    return unique_pairs(
        (loader.construct_object(key), loader.construct_object(value))
        for key, value in node.value
    )


UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)


def local_file(relative):
    resolved = (ROOT / relative).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("Fixture path must stay within contracts/")
    return resolved


def pointer_get(spec, ref):
    if not ref.startswith("#/"):
        raise ValueError("Only local OpenAPI references are allowed")
    value = spec
    for part in ref[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def response_media(spec, path, status):
    escaped = path.replace("~", "~0").replace("/", "~1")
    pointer = f"#/paths/{escaped}/get/responses/{status}"
    response = pointer_get(spec, pointer)
    visited = set()
    while "$ref" in response:
        pointer = response["$ref"]
        if pointer in visited:
            raise ValueError("Circular response reference")
        visited.add(pointer)
        response = pointer_get(spec, pointer)
    return response["content"]["application/json"], pointer


def load_contract():
    spec = yaml.load(SPEC_PATH.read_text(encoding="utf-8"), Loader=UniqueLoader)
    if spec["openapi"] != "3.1.0":
        raise ValueError("This suite requires OpenAPI 3.1.0")
    if set(spec["paths"]) != {"/health", "/api/v1/cities"}:
        raise ValueError("S2 WP2 permits exactly /health and /api/v1/cities")
    for path, item in spec["paths"].items():
        if set(item) != {"get"}:
            raise ValueError(f"Only GET is allowed for {path}")
        if set(item["get"]["responses"]) != {"200", "400", "404", "405", "406", "500", "503"}:
            raise ValueError(f"Unexpected response coverage for {path}")
    validate(spec, base_uri=SPEC_PATH.as_uri())
    for schema in spec["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(
        SPEC_PATH.as_uri(), Resource(contents=spec, specification=DRAFT202012)
    )
    checker = FormatChecker(formats=["date-time", "uuid"])
    # Fail closed if optional format support has not been installed.
    if checker.conforms("2026-02-30T10:00:00Z", "date-time"):
        raise ValueError("date-time validation is not active")
    if checker.conforms("not-a-uuid", "uuid"):
        raise ValueError("uuid validation is not active")
    return spec, registry, checker


def body_errors(spec, registry, checker, path, status, body):
    _, pointer = response_media(spec, path, status)
    validator = Draft202012Validator(
        {"$ref": SPEC_PATH.as_uri() + pointer + "/content/application~1json/schema"},
        registry=registry,
        format_checker=checker,
    )
    return list(validator.iter_errors(body))


def error_summary(errors):
    # Report only schema keywords and field paths, never payload contents.
    return "; ".join(
        f"{error.validator}@/{'/'.join(map(str, error.absolute_path))}"
        for error in errors
    )


def run_suite(spec, registry, checker):
    cases = read_json(ROOT / "cases.json")
    names = [case["name"] for case in cases]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate fixture case name")
    positive_files = set()
    count = {True: 0, False: 0}
    for case in cases:
        body = read_json(local_file(case["file"]))
        errors = body_errors(spec, registry, checker, case["path"], str(case["status"]), body)
        expected_valid = case["valid"]
        if (not errors) != expected_valid:
            raise ValueError(f"Unexpected result for {case['name']}: {error_summary(errors)}")
        if not expected_valid:
            expected = case["expectedKeyword"]
            if not any(error.validator == expected for error in errors):
                raise ValueError(f"Wrong rejection reason for {case['name']}: {error_summary(errors)}")
        else:
            positive_files.add(case["file"])
        count[expected_valid] += 1
        outcome = "ACCEPT" if expected_valid else "REJECT"
        print(f"PASS {outcome} {case['name']}" + (f" [{error_summary(errors)}]" if errors else ""))

    # Every OpenAPI external example is loaded and checked against its own HTTP schema.
    examples_checked = 0
    for path, item in spec["paths"].items():
        for status in item["get"]["responses"]:
            media, _ = response_media(spec, path, status)
            for name, example in media.get("examples", {}).items():
                relative = example["externalValue"]
                if relative.removeprefix("./") not in positive_files:
                    raise ValueError(f"Unlisted external example: {relative}")
                errors = body_errors(spec, registry, checker, path, status, read_json(local_file(relative)))
                if errors:
                    raise ValueError(f"Invalid external example {path}/{status}/{name}: {error_summary(errors)}")
                examples_checked += 1
    print(f"PASS fixtures: {count[True]} accepted, {count[False]} rejected; OpenAPI examples: {examples_checked} accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", type=Path, help="Validate one JSON response; invalid returns exit 1")
    parser.add_argument("--path", choices=["/health", "/api/v1/cities"], default="/api/v1/cities")
    parser.add_argument("--status", choices=["200", "400", "404", "405", "406", "500", "503"], default="200")
    args = parser.parse_args()
    try:
        spec, registry, checker = load_contract()
        print("PASS OpenAPI 3.1 specification and component JSON Schemas")
        print("TOOLS " + ", ".join(f"{name}=={version(name)}" for name in (
            "openapi-spec-validator", "jsonschema", "PyYAML", "referencing", "rfc3339-validator"
        )))
        if args.instance:
            errors = body_errors(spec, registry, checker, args.path, args.status, read_json(args.instance))
            if errors:
                print("REJECT instance: " + error_summary(errors))
                return 1
            print("PASS ACCEPT instance")
        else:
            run_suite(spec, registry, checker)
        print("STATIC CONTRACT VALIDATION ONLY; no HTTP integration tested")
        return 0
    except Exception as error:
        print(f"FAIL {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
