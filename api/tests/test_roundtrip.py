"""build(decompile(reference)) must reproduce each reference, up to the differences listed here.

Ignored on purpose, because the references are hand-made and not consistent with themselves:
- ids, flow link ids and layout (x, y, rows, cols, questionOrder, minItemRows): the compiler
  generates them deterministically; only the order of pages, sections and fields is compared,
- whitespace inside JSONata queries,
- `multiLevelTree` and `searchEnabled` on SELECT, which differ between identical fields,
- `validation: {}` in reference 1, which the import description defines as a list,
- option `techName`, compared separately in test_option_technames_are_slugs (one is missing).
"""

from copy import deepcopy
from typing import Any

from formcompiler.compiler import build, slugify
from formcompiler.decompile import decompile
from formcompiler.query import normalize as normalize_query
from formcompiler.schema import Form

FIELD_KEYS_IGNORED = {"id", "questionOrder"}


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    field = item["field"]
    out = {k: v for k, v in field.items() if k not in FIELD_KEYS_IGNORED}
    out["repeatingSectionGrid"] = [
        _normalize_item(g) for g in sorted(field["repeatingSectionGrid"], key=lambda g: g["y"])
    ]
    out["states"] = [{**s, "query": normalize_query(s["query"])} for s in field.get("states", [])]
    out["options"] = [o["name"] for o in field["options"]]
    if field["validation"] == {}:
        out["validation"] = []
    if field["type"] == "SELECT":
        out.pop("multiLevelTree", None)
        out.pop("searchEnabled", None)
    return out


def normalize(form: dict[str, Any]) -> dict[str, Any]:
    form = deepcopy(form)
    tab_ids = [t["id"] for t in form["tabs"]]
    return {
        "title": form["title"],
        "flow": [
            (tab_ids.index(link["source"]), tab_ids.index(link["target"]))
            for link in form["flow"]["links"]
        ],
        "tabs": [
            {
                "title": t["title"],
                "type": t["type"],
                "questions": [
                    _normalize_item(q) for q in sorted(t["questions"], key=lambda q: q["y"])
                ],
            }
            for t in form["tabs"]
        ],
    }


def test_build_of_decompiled_reference_reproduces_it(reference: dict[str, Any]) -> None:
    rebuilt = build(decompile(Form.model_validate(reference))).dump()

    assert normalize(rebuilt) == normalize(reference)


def test_build_is_deterministic(reference: dict[str, Any]) -> None:
    ir = decompile(Form.model_validate(reference))

    assert build(ir).dump() == build(ir).dump()


def test_build_output_has_unique_ids(reference: dict[str, Any]) -> None:
    form = build(decompile(Form.model_validate(reference)))
    ids = [t.id for t in form.tabs] + [
        item.field.id
        for t in form.tabs
        for q in t.questions
        for item in [q, *q.field.repeatingSectionGrid]
    ]

    assert len(ids) == len(set(ids))


def test_option_technames_are_slugs(reference: dict[str, Any]) -> None:
    pairs = [
        (o["name"], o["techName"])
        for t in reference["tabs"]
        for q in t["questions"]
        for g in q["field"]["repeatingSectionGrid"]
        for o in g["field"]["options"]
        if "techName" in o
    ]

    assert pairs
    assert [(name, slugify(name)) for name, _ in pairs] == pairs


def test_slugify_transliterates_polish_letters() -> None:
    assert slugify("Zażółć gęślą jaźń, ŁÓDŹ!") == "zazolc_gesla_jazn_lodz"
