from typing import Any

from formcompiler.schema import Form


def test_reference_parses_without_losing_anything(reference: dict[str, Any]) -> None:
    form = Form.model_validate(reference)

    assert form.model_dump(mode="json", exclude_unset=True) == reference
