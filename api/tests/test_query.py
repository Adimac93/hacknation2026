from typing import Any

import pytest

from formcompiler.ir import Cond, CondGroup
from formcompiler.query import Location, normalize, parse, render

PATH = (
    "tabs['Dane' in title].questions['podmiot_wniosku' in field.techName]"
    ".field.repeatingSectionGrid['{f}' in field.techName].field.__userAnswer"
)


def locate(key: str) -> Location:
    return Location(page="Dane", section="podmiot_wniosku", field=key)


def test_render_simple_condition_matches_reference_format() -> None:
    cond = Cond(field="kto", value="Innej osoby")

    assert render(cond, locate) == '("Innej osoby" in ' + PATH.format(f="kto") + ")"


def test_render_negated_condition_uses_not() -> None:
    cond = Cond(field="kraj", op="NOT_IN", value="Polska")

    assert render(cond, locate) == '$not("Polska" in ' + PATH.format(f="kraj") + ")"


def test_render_nested_group_parenthesizes_inner_group() -> None:
    cond = CondGroup(
        match="any",
        conds=[
            Cond(field="kto", value="Innej osoby"),
            CondGroup(
                match="all", conds=[Cond(field="kto", value="Firmy"), Cond(field="rola", value="P")]
            ),
        ],
    )

    a, b, c = (
        '("Innej osoby" in ' + PATH.format(f="kto") + ")",
        '("Firmy" in ' + PATH.format(f="kto") + ")",
        '("P" in ' + PATH.format(f="rola") + ")",
    )
    assert render(cond, locate) == f"{a} or ({b} and {c})"


def test_render_rejects_quotes_in_values() -> None:
    with pytest.raises(ValueError, match="quote"):
        render(Cond(field="kto", value='Pan "X"'), locate)


def test_parse_inverts_render() -> None:
    cond = CondGroup(
        match="any",
        conds=[
            Cond(field="kto", value="Innej osoby"),
            CondGroup(
                match="all",
                conds=[
                    Cond(field="kto", value="Firmy"),
                    Cond(field="rola", op="NOT_IN", value="P"),
                ],
            ),
        ],
    )

    parsed, locations = parse(render(cond, locate))

    assert parsed == cond
    assert locations["rola"] == locate("rola")


def test_every_reference_query_parses_and_renders_back(reference: dict[str, Any]) -> None:
    queries = [
        state["query"]
        for tab in reference["tabs"]
        for question in tab["questions"]
        for item in [question, *question["field"]["repeatingSectionGrid"]]
        for state in item["field"].get("states", [])
    ]
    locations: dict[str, Location] = {}

    def record(key: str) -> Location:
        return locations[key]

    assert len(queries) >= 29
    for query in queries:
        cond, found = parse(query)
        locations.update(found)
        assert normalize(render(cond, record)) == normalize(query)
