import json
from pathlib import Path
from typing import Any

import pytest

DOCS = Path(__file__).resolve().parents[2] / "Docs"
REFERENCE_FILES = {
    "ref1": next(DOCS.glob("1. */konfiguracja_*.json")),
    "ref5": next(DOCS.glob("5. */konfiguracja_*.json")),
}


@pytest.fixture(params=sorted(REFERENCE_FILES))
def reference(request: pytest.FixtureRequest) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(REFERENCE_FILES[request.param].read_text(encoding="utf-8"))
    return data
