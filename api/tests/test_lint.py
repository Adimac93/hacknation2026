"""Linter rules: each one fires on a deliberately broken copy of a reference, and fix repairs it.

The broken forms start from `fix(reference)`, which has no errors, so every error in a mutated
form comes from the mutation.
"""

import json
import re
from collections.abc import Callable, Iterator
from copy import deepcopy
from typing import Any

import pytest
from conftest import REFERENCE_FILES

from formcompiler.compiler import build
from formcompiler.decompile import decompile
from formcompiler.lint import Issue, fix, lint
from formcompiler.schema import Form

type Data = dict[str, Any]
type Mutation = Callable[[Data], None]


def _errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]


def _pairs(issues: list[Issue]) -> set[tuple[str, str]]:
    return {(i.code, i.path) for i in issues}


def _load(name: str) -> Form:
    return Form.model_validate(json.loads(REFERENCE_FILES[name].read_text(encoding="utf-8")))


def _walk(items: list[Data], prefix: str) -> Iterator[tuple[str, Data]]:
    for i, item in enumerate(items):
        path = f"{prefix}[{i}]"
        yield path, item["field"]
        yield from _walk(
            item["field"]["repeatingSectionGrid"], f"{path}.field.repeatingSectionGrid"
        )


def _find(data: Data, tech_name: str) -> tuple[str, Data]:
    """Path of the grid item and the field with the given techName (first match)."""
    for t, tab in enumerate(data["tabs"]):
        for path, field in _walk(tab["questions"], f"tabs[{t}].questions"):
            if field["techName"] == tech_name:
                return path, field
    raise KeyError(tech_name)


def _query_field(data: Data) -> Data:
    """A section whose SHOW query references the 'Dane' page and the 'Innej osoby' option."""
    return _find(data, "dane_innej_osoby")[1]


@pytest.fixture
def clean(reference: Data) -> Data:
    return fix(Form.model_validate(reference))[0].dump()


# --- references -------------------------------------------------------------------------------


def test_reference_1_has_only_validation_dict_errors_and_fix_repairs_them() -> None:
    form = _load("ref1")
    expected = {
        ("L010", "tabs[0].questions[4].field.repeatingSectionGrid[3].field.validation"),
        ("L010", "tabs[0].questions[5].field.repeatingSectionGrid[2].field.validation"),
        ("L010", "tabs[0].questions[7].field.repeatingSectionGrid[0].field.validation"),
    }

    assert _pairs(_errors(lint(form))) == expected

    fixed, issues = fix(form)
    assert _pairs([i for i in issues if i.fixed]) == expected
    assert not _errors([i for i in issues if not i.fixed])
    assert not _errors(lint(fixed))


def test_reference_5_has_no_errors() -> None:
    assert not _errors(lint(_load("ref5")))


def test_references_have_no_errors_after_fix(reference: Data) -> None:
    fixed, issues = fix(Form.model_validate(reference))

    assert not _errors([i for i in issues if not i.fixed])
    assert not _errors(lint(fixed))


def test_compiled_references_have_no_errors(reference: Data) -> None:
    form = build(decompile(Form.model_validate(reference)))

    assert not _errors(lint(form))


def test_fix_is_idempotent(reference: Data) -> None:
    fixed, _ = fix(Form.model_validate(reference))
    again, issues = fix(fixed)

    assert again == fixed
    assert not [i for i in issues if i.fixed]


def test_fix_does_not_modify_its_input(reference: Data) -> None:
    form = Form.model_validate(reference)
    before = deepcopy(form.dump())

    fix(form)

    assert form.dump() == before


# --- error rules ------------------------------------------------------------------------------


def _set_title(value: str) -> Mutation:
    def mutate(d: Data) -> None:
        d["title"] = value

    return mutate


def _single_main_page(d: Data) -> None:
    d["tabs"] = d["tabs"][:1]
    d["flow"]["links"] = []


def _single_finish_page(d: Data) -> None:
    d["tabs"] = d["tabs"][-1:]
    d["flow"]["links"] = []


def _no_finish(d: Data) -> None:
    d["tabs"][-1]["type"] = "MAIN"


def _two_finishes(d: Data) -> None:
    d["tabs"][0]["type"] = "FINISH"


def _finish_first(d: Data) -> None:
    d["tabs"].insert(0, d["tabs"].pop())


def _field_on_page(d: Data) -> None:
    section = d["tabs"][1]["questions"][0]["field"]
    d["tabs"][1]["questions"].append(section["repeatingSectionGrid"].pop())


def _section_in_section(d: Data) -> None:
    questions = d["tabs"][0]["questions"]
    questions[0]["field"]["repeatingSectionGrid"].append(questions.pop())


def _page_without_fields(d: Data) -> None:
    for q in d["tabs"][1]["questions"]:
        q["field"]["repeatingSectionGrid"] = []


def _input_on_finish(d: Data) -> None:
    d["tabs"][-1]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]["type"] = (
        "TEXT_FIELD"
    )


def _set(tech_name: str, **values: Any) -> Mutation:
    def mutate(d: Data) -> None:
        _find(d, tech_name)[1].update(values)

    return mutate


def _duplicate_id(d: Data) -> None:
    _find(d, "imie")[1]["id"] = _find(d, "nazwisko")[1]["id"]


def _duplicate_page_title(d: Data) -> None:
    d["tabs"][1]["title"] = d["tabs"][0]["title"]


def _replace_in_query(old: str, new: str) -> Mutation:
    def mutate(d: Data) -> None:
        state = _query_field(d)["states"][0]
        state["query"] = state["query"].replace(old, new)

    return mutate


def _bad_link_target(d: Data) -> None:
    d["flow"]["links"][0]["target"] = "nie-ma-takiej-strony"


def _broken_chain(d: Data) -> None:
    d["flow"]["links"].pop()


def _duplicate_option(d: Data) -> None:
    field = _find(d, "wybierz_jako_kto_wnioskujesz")[1]
    field["options"].append(dict(field["options"][0]))


def _empty_section(d: Data) -> None:
    section = deepcopy(d["tabs"][1]["questions"][0])
    section["field"].update(
        id="00000000-0000-5000-8000-000000000001",
        techName="pusta_sekcja",
        repeatingSectionGrid=[],
        states=[],
    )
    d["tabs"][1]["questions"].append(section)


def _read_only_section(d: Data) -> None:
    _query_field(d)["states"][0]["type"] = "READ_ONLY"


def _path(tech_name: str, suffix: str = "") -> Callable[[Data], str]:
    return lambda d: _find(d, tech_name)[0] + suffix


def _last_path(tech_name: str, suffix: str = "") -> Callable[[Data], str]:
    return lambda d: [p for p, f in _iter_fields(d) if f["techName"] == tech_name][-1] + suffix


def _fixed(path: str) -> Callable[[Data], str]:
    return lambda _: path


GRID_0_0 = "tabs[0].questions[0].field.repeatingSectionGrid"
GRID_1_0 = "tabs[1].questions[0].field.repeatingSectionGrid"

ERROR_CASES: list[tuple[str, Mutation, Callable[[Data], str]]] = [
    ("L001", _set_title(""), _fixed("title")),
    ("L001", _set_title("x" * 256), _fixed("title")),
    ("L002", _single_main_page, _fixed("tabs")),
    ("L002", _single_finish_page, _fixed("tabs")),
    ("L003", _no_finish, _fixed("tabs")),
    ("L003", _two_finishes, _fixed("tabs[0]")),
    ("L004", _finish_first, _fixed("tabs[0]")),
    ("L005", _field_on_page, lambda d: f"tabs[1].questions[{len(d['tabs'][1]['questions']) - 1}]"),
    ("L006", _section_in_section, lambda d: f"{GRID_0_0}[{len(_grid_0_0(d)) - 1}]"),
    ("L007", _page_without_fields, _fixed("tabs[1]")),
    ("L008", _input_on_finish, _fixed("tabs[3].questions[0].field.repeatingSectionGrid[0]")),
    ("L010", _set("imie", validation={"REQUIRED": True}), _path("imie", ".field.validation")),
    ("L011", _set("imie", validation=["MAGIC"]), _path("imie", ".field.validation")),
    ("L012", _set("podglad_1", validation=["EMAIL"]), _path("podglad_1", ".field.validation")),
    (
        "L012",
        _set("wybierz_jako_kto_wnioskujesz", validation=["REQUIRED", "PESEL"]),
        _path("wybierz_jako_kto_wnioskujesz", ".field.validation"),
    ),
    ("L013", _set("imie", dictionaryName="Kraje"), _path("imie", ".field.dictionaryName")),
    (
        "L014",
        _set("kraj", options=[{"id": "Polska", "name": "Polska", "techName": "polska"}]),
        _path("kraj", ".field.dictionaryName"),
    ),
    (
        "L025",
        _set("wybierz_jako_kto_wnioskujesz", options=[]),
        _path("wybierz_jako_kto_wnioskujesz", ".field.options"),
    ),
    ("L015", _set("imie", defaultValue="USOS.name"), _path("imie", ".field.defaultValue")),
    (
        "L015",
        _set("nazwa", defaultValueType="EXTERNAL_SYSTEM"),
        _path("nazwa", ".field.defaultValue"),
    ),
    (
        "L016",
        _set("imie", defaultValue="PESEL.name", defaultValueType="EXTERNAL_SYSTEM", readOnly=False),
        _path("imie", ".field.readOnly"),
    ),
    ("L017", _duplicate_id, _path("imie", ".field.id")),
    ("L018", _set("imie", techName="nazwisko"), _last_path("nazwisko", ".field.techName")),
    ("L018", _set("imie", techName=""), _path("", ".field.techName")),
    ("L019", _duplicate_page_title, _fixed("tabs[1].title")),
    (
        "L020",
        _replace_in_query("tabs[", "pages["),
        _path("dane_innej_osoby", ".field.states[0].query"),
    ),
    (
        "L021",
        _replace_in_query("'Dane' in title", "'Brak' in title"),
        _path("dane_innej_osoby", ".field.states[0].query"),
    ),
    (
        "L021",
        _replace_in_query("'podmiot_wniosku'", "'brak_sekcji'"),
        _path("dane_innej_osoby", ".field.states[0].query"),
    ),
    (
        "L021",
        _replace_in_query("'wybierz_w_czyim_imieniu_wnioskujesz'", "'brak_pola'"),
        _path("dane_innej_osoby", ".field.states[0].query"),
    ),
    (
        "L022",
        _replace_in_query('"Innej osoby"', '"Kogoś innego"'),
        _path("dane_innej_osoby", ".field.states[0].query"),
    ),
    ("L023", _bad_link_target, _fixed("flow.links[0]")),
    ("L024", _broken_chain, _fixed("flow.links")),
    ("L026", _set("kraj", dictionaryName="Waluty"), _path("kraj", ".field.dictionaryName")),
    ("L027", _set("kraj", type="RADIO"), _path("kraj", ".field.dictionaryName")),
    (
        "L028",
        _set(
            "imie", defaultValue="PESEL.shoeSize", defaultValueType="EXTERNAL_SYSTEM", readOnly=True
        ),
        _path("imie", ".field.defaultValue"),
    ),
    ("L029", _duplicate_option, _path("wybierz_jako_kto_wnioskujesz", ".field.options")),
    ("L030", _empty_section, _path("pusta_sekcja")),
    ("L031", _read_only_section, _path("dane_innej_osoby", ".field.states[0].type")),
]


def _grid_0_0(d: Data) -> list[Data]:
    grid: list[Data] = d["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"]
    return grid


def _case_id(case: tuple[Any, ...]) -> str:
    code, mutate = case[0], case[1]
    return f"{code}-{getattr(mutate, '__name__', 'mutation')}"


@pytest.mark.parametrize("case", ERROR_CASES, ids=[_case_id(c) for c in ERROR_CASES])
def test_error_rule(clean: Data, case: tuple[str, Mutation, Callable[[Data], str]]) -> None:
    code, mutate, path = case
    data = deepcopy(clean)
    mutate(data)

    errors = _errors(lint(Form.model_validate(data)))

    assert (code, path(data)) in _pairs(errors)


def test_unknown_component_type(clean: Data) -> None:
    form = Form.model_validate(clean)
    grid = form.tabs[1].questions[0].field.repeatingSectionGrid
    grid[0] = grid[0].model_copy(
        update={"field": grid[0].field.model_copy(update={"type": "PODPIS"})}
    )

    errors = _errors(lint(form))

    assert ("L009", f"{GRID_1_0}[0].field.type") in _pairs(errors)


# --- repairs ----------------------------------------------------------------------------------

REPAIR_CASES: list[tuple[str, Mutation]] = [
    ("L002", _single_main_page),
    ("L003", _no_finish),
    ("L004", _finish_first),
    ("L010", _set("imie", validation={})),
    ("L012", _set("podglad_1", validation=["EMAIL"])),
    (
        "L016",
        _set("imie", defaultValue="PESEL.name", defaultValueType="EXTERNAL_SYSTEM", readOnly=False),
    ),
    ("L017", _duplicate_id),
    ("L018", _set("imie", techName="nazwisko")),
    ("L018", _set("imie", techName="")),
    ("L023", _bad_link_target),
    ("L024", _broken_chain),
    ("L029", _duplicate_option),
    ("L030", _empty_section),
]


@pytest.mark.parametrize("case", REPAIR_CASES, ids=[_case_id(c) for c in REPAIR_CASES])
def test_repair(clean: Data, case: tuple[str, Mutation]) -> None:
    code, mutate = case
    data = deepcopy(clean)
    mutate(data)
    broken = Form.model_validate(data)

    fixed, issues = fix(broken)

    assert code in {i.code for i in issues if i.fixed}
    assert not _errors([i for i in issues if not i.fixed])
    assert not _errors(lint(fixed))
    assert fix(fixed)[0] == fixed


def test_missing_finish_gets_preview_page(clean: Data) -> None:
    data = deepcopy(clean)
    del data["tabs"][-1]
    data["flow"]["links"].pop()

    fixed, _ = fix(Form.model_validate(data))

    finish = fixed.tabs[-1]
    assert finish.type == "FINISH"
    assert finish.title not in {t.title for t in fixed.tabs[:-1]}
    [section] = finish.questions
    assert [g.field.type for g in section.field.repeatingSectionGrid] == ["TEXT_BLOCK"]
    assert [(link.source, link.target) for link in fixed.flow.links][-1] == (
        fixed.tabs[-2].id,
        finish.id,
    )


def test_duplicate_techname_gets_suffix(clean: Data) -> None:
    data = deepcopy(clean)
    _set("imie", techName="nazwisko")(data)

    fixed, _ = fix(Form.model_validate(data))

    names = [f["techName"] for f in (field for _, field in _iter_fields(fixed.dump()))]
    assert "nazwisko_2" in names
    assert len(names) == len(set(names))


def _iter_fields(data: Data) -> Iterator[tuple[str, Data]]:
    for t, tab in enumerate(data["tabs"]):
        yield from _walk(tab["questions"], f"tabs[{t}].questions")


def test_queries_are_reported_but_never_rewritten(clean: Data) -> None:
    data = deepcopy(clean)
    _replace_in_query('"Innej osoby"', '"Kogoś innego"')(data)
    query = _query_field(data)["states"][0]["query"]

    fixed, issues = fix(Form.model_validate(data))

    assert _query_field(fixed.dump())["states"][0]["query"] == query
    assert "L022" in {i.code for i in issues if not i.fixed}


# --- warnings ---------------------------------------------------------------------------------


def _long_select(d: Data) -> None:
    names = ["Polska"] + [f"Kraj {i}" for i in range(15)]
    options = [{"id": n, "name": n, "techName": n.lower().replace(" ", "_")} for n in names]
    _set("kraj", options=options, searchEnabled=False, dictionaryName=None, defaultValue=[])(d)


def _consent_checkbox(d: Data) -> None:
    _set(
        "imie",
        type="CHECKBOX",
        title="Oświadczam, że dane są prawdziwe",
        options=[{"id": "Tak", "name": "Tak", "techName": "tak"}],
        defaultValue=None,
        defaultValueType=None,
    )(d)


WARNING_CASES: list[tuple[str, Mutation, Callable[[Data], str]]] = [
    ("L101", _set("imie", title="Dokonaj wyboru"), _path("imie", ".field.title")),
    ("L101", _set("imie", title="Czy posiadasz konto?"), _path("imie", ".field.title")),
    ("L102", _set("imie", title="Będąc właścicielem, podaj imię"), _path("imie", ".field.title")),
    ("L103", _set("imie", title="Wyczerpujące uzasadnienie"), _path("imie", ".field.title")),
    ("L104", _set("imie", title="Należy podać imię"), _path("imie", ".field.title")),
    ("L110", _consent_checkbox, _path("imie")),
    ("L111", _long_select, _path("kraj", ".field.searchEnabled")),
]


@pytest.mark.parametrize("case", WARNING_CASES, ids=[_case_id(c) for c in WARNING_CASES])
def test_warning_rule(clean: Data, case: tuple[str, Mutation, Callable[[Data], str]]) -> None:
    code, mutate, path = case
    data = deepcopy(clean)
    mutate(data)

    issues = lint(Form.model_validate(data))

    assert (code, path(data)) in _pairs([i for i in issues if i.severity == "warning"])
    assert not _errors(issues)


def test_long_select_gets_search(clean: Data) -> None:
    data = deepcopy(clean)
    _long_select(data)

    fixed, issues = fix(Form.model_validate(data))

    assert _find(fixed.dump(), "kraj")[1]["searchEnabled"] is True
    assert "L111" in {i.code for i in issues if i.fixed}


def test_short_plain_label_has_no_warnings(clean: Data) -> None:
    data = deepcopy(clean)
    _set("imie", title="Imię")(data)
    path = _path("imie", ".field.title")(data)

    issues = lint(Form.model_validate(data))

    assert not [i for i in issues if i.path == path]


def test_dictionary_list_covers_the_model_dictionaries() -> None:
    from formcompiler.lint import DICTIONARIES
    from formcompiler.llm import Dictionary

    assert {d.value for d in Dictionary} <= DICTIONARIES


def test_register_attributes_cover_the_predefined_sections() -> None:
    """Every attribute the section library prefills is on the organiser's list."""
    from importlib.resources import files

    from formcompiler.lint import REGISTER_ATTRIBUTES, REGISTER_VALUE

    text = files("formcompiler").joinpath("data/sections.json").read_text(encoding="utf-8")
    values = {m.group(0) for m in re.finditer(r"(PESEL_ADDRESS|PESEL|MLPZ)\.[A-Za-z]+", text)}

    assert values
    for value in values:
        assert REGISTER_VALUE.match(value)
        source, attribute = value.split(".", 1)
        assert attribute in REGISTER_ATTRIBUTES[source], value


def test_duplicate_options_keep_the_first(clean: Data) -> None:
    data = deepcopy(clean)
    _duplicate_option(data)

    fixed, _ = fix(Form.model_validate(data))

    field = _find(fixed.dump(), "wybierz_jako_kto_wnioskujesz")[1]
    original = _find(clean, "wybierz_jako_kto_wnioskujesz")[1]
    assert field["options"] == original["options"]
