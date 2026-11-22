"""Every form we emit validates against the organiser's JSON Schema (importowanyPlikJsonSchemat).

The official schema is loose and partly outdated, so the test applies it with documented
deviations, each one following the reference JSONs (the format authority):

- the schema validates only page-level entries; nested fields sit in `repetingSectionGrid`
  (typo) with `items: {}`. We also validate every nested grid item with the question schema,
  under the key the references and the Generator use: `repeatingSectionGrid`.
- `defaultValue` is `string` in the schema, but the technical rules give SELECT
  `"defaultValue": []` and both references use lists for SELECT, so a list of strings is allowed.
- reference 1 has `validation: {}` in three fields; that is a defect of that file (the import
  description says "tablica stringów"), accepted only for the references.
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from conftest import DOCS, REFERENCE_FILES
from jsonschema import Draft202012Validator

from formcompiler.compiler import build
from formcompiler.decompile import decompile
from formcompiler.schema import Form

SCHEMA_FILE = next(DOCS.glob("Materiały do zadania dla Uczestników/importowanyPlikJsonSchemat*"))
OUTPUTS = sorted((Path(__file__).resolve().parents[2] / "outputs").glob("*.json"))


def _schema() -> dict[str, Any]:
    official: dict[str, Any] = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    schema = deepcopy(official)
    question = schema["properties"]["tabs"]["items"]["properties"]["questions"]["items"]
    field = question["properties"]["field"]["properties"]
    field["defaultValue"] = {
        "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]
    }
    field["repeatingSectionGrid"] = {"type": "array", "items": {"$ref": "#/$defs/question"}}
    schema["$defs"] = {"question": question}
    schema["properties"]["tabs"]["items"]["properties"]["questions"]["items"] = {
        "$ref": "#/$defs/question"
    }
    return schema


VALIDATOR = Draft202012Validator(_schema())


def _errors(data: dict[str, Any], *, reference: bool = False) -> list[str]:
    errors = []
    for e in VALIDATOR.iter_errors(data):
        if reference and e.absolute_path and e.absolute_path[-1] == "validation":
            continue
        errors.append(f"{'/'.join(map(str, e.absolute_path))}: {e.message}")
    return errors


def test_official_schema_is_valid() -> None:
    Draft202012Validator.check_schema(_schema())


def test_outputs_exist() -> None:
    assert len(OUTPUTS) >= 6


@pytest.mark.parametrize("path", OUTPUTS, ids=[p.stem[:40] for p in OUTPUTS])
def test_output_matches_official_schema(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))

    assert _errors(data) == []
    Form.model_validate(data)


@pytest.mark.parametrize("name", sorted(REFERENCE_FILES))
def test_reference_matches_official_schema(name: str) -> None:
    data = json.loads(REFERENCE_FILES[name].read_text(encoding="utf-8"))

    assert _errors(data, reference=True) == []


def test_compiled_reference_matches_official_schema(reference: dict[str, Any]) -> None:
    compiled = build(decompile(Form.model_validate(reference))).dump()

    assert _errors(compiled) == []


def test_nested_fields_are_validated() -> None:
    """The deviation is real: a bad nested field fails, which the raw schema would miss."""
    data = json.loads(REFERENCE_FILES["ref5"].read_text(encoding="utf-8"))
    data["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]["title"] = 1

    assert _errors(data)


def test_compiler_dedupes_options_and_never_leaves_empty_technames() -> None:
    from formcompiler.compiler import _options

    options = _options(["Tak", "Tak", " ", "-", "?", "Nie"])

    assert [o.name for o in options] == ["Tak", "-", "?", "Nie"]
    assert [o.techName for o in options] == ["tak", "opcja_4", "opcja_5", "nie"]
