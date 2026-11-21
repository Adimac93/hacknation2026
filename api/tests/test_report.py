from typing import Any

import pytest
from pydantic import ValidationError

from formcompiler.report import Report

# The `report` example from ARCHITECTURE 8.1, agreed with the frontend.
CONTRACT_EXAMPLE: dict[str, Any] = {
    "mode": "llm",
    "model": "mistral/ministral-8b-2512@eu",
    "timings_ms": {"ingest": 120, "heuristics": 4, "llm": 9100, "compile": 3, "lint": 2},
    "lint": [
        {
            "code": "L005",
            "severity": "error",
            "message": "Pole leży poza sekcją",
            "path": "tabs[1].questions[0]",
            "fixed": True,
        }
    ],
    "fields": [{"techName": "imie", "src": ["L12"], "confidence": 0.9}],
    "document": {
        "pages": [{"number": 1, "lines": [{"id": "L1", "text": "WNIOSEK", "kind": "HEADING"}]}]
    },
    "dictionary_proposals": [],
}


def test_contract_example_round_trips() -> None:
    dumped = Report.model_validate(CONTRACT_EXAMPLE).model_dump(mode="json", exclude_unset=True)

    assert dumped == CONTRACT_EXAMPLE


def test_rules_mode_report_has_every_contract_key() -> None:
    dumped = Report(mode="rules").model_dump(mode="json")

    assert set(dumped) == set(CONTRACT_EXAMPLE)
    assert dumped["model"] is None
    assert set(dumped["timings_ms"]) == set(CONTRACT_EXAMPLE["timings_ms"])


@pytest.mark.parametrize(
    "change",
    [
        {"mode": "hybrid"},
        {"lint": [{"code": "L1", "severity": "info", "message": "", "path": ""}]},
        {"fields": [{"techName": "imie", "confidence": 1.5}]},
    ],
)
def test_values_outside_the_contract_are_rejected(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Report.model_validate(CONTRACT_EXAMPLE | change)
