"""Technical rules of the COI Form Generator: checks and automatic repairs of the output JSON.

Pure functions only. `lint` reports issues, `fix` returns a repaired copy together with the
issues it repaired (`fixed=True`) and the ones that remain. JSONata queries are never rewritten,
only reported. Error codes are L0xx, quality warnings from the COI design standards are L1xx.
"""

import re
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from pydantic import BaseModel, ConfigDict

from formcompiler import schema
from formcompiler.compiler import SEARCH_THRESHOLD, build, slugify, stable_id
from formcompiler.ir import (
    CHOICE_TYPES,
    FieldIR,
    FieldType,
    FormIR,
    PageIR,
    SectionIR,
    Validator,
    simple_conds,
)
from formcompiler.query import parse

TITLE_MAX = 255
SECTION_TYPES = frozenset({"SECTION", "REPEATING_SECTION"})
FIELD_TYPES = frozenset(t.value for t in FieldType)
CHOICE = frozenset(t.value for t in CHOICE_TYPES)
FINISH_TYPES = frozenset({FieldType.TEXT_BLOCK.value, FieldType.INFO_SECTION.value})
PRESENTATION_TYPES = FINISH_TYPES | {FieldType.CONSENT_SECTION.value} | SECTION_TYPES
VALIDATORS = frozenset(v.value for v in Validator)
REGISTER_VALUE = re.compile(r"^(PESEL|PESEL_ADDRESS|MLPZ)\.[A-Za-z]+$")
PESEL_VALUE = re.compile(r"^PESEL(_ADDRESS)?\.")
FINISH_TITLE = "Strona końcowa"
PREVIEW_TEXT = (
    "Zanim przejdziesz do wyboru sposobu podpisu, sprawdź dane na podglądzie. "
    "Jeśli zobaczysz błędy, wróć do edycji."
)

WORD = re.compile(r"[^\W\d_]+")
VOWEL_RUN = re.compile(r"[aąeęioóuy]+")
HARD_WORD = re.compile(r"^(dokon|posiad)")
PARTICIPLE = re.compile(r"ąc$")
IMPERSONAL = frozenset({"należy", "trzeba"})
MAX_SYLLABLES = 4
CONSENT_PREFIXES = ("oświadczam", "wyrażam zgodę")


class Issue(BaseModel):
    """One finding, in the shape of `report.lint` in the API contract."""

    model_config = ConfigDict(frozen=True)

    code: str
    severity: Literal["error", "warning"]
    message: str
    path: str
    fixed: bool = False


def _error(code: str, path: str, message: str) -> Issue:
    return Issue(code=code, severity="error", message=message, path=path)


def _warning(code: str, path: str, message: str) -> Issue:
    return Issue(code=code, severity="warning", message=message, path=path)


@dataclass(frozen=True)
class Item:
    """A grid item anywhere in the form, with its path and position."""

    path: str
    item: schema.GridItem
    tab: int
    section: schema.GridItem | None

    @property
    def field(self) -> schema.Field:
        return self.item.field


def _items(form: schema.Form) -> Iterator[Item]:
    """Every grid item: page-level entries and the entries of their grids, recursively."""

    def walk(
        items: list[schema.GridItem], prefix: str, tab: int, parent: schema.GridItem | None
    ) -> Iterator[Item]:
        for i, item in enumerate(items):
            path = f"{prefix}[{i}]"
            yield Item(path, item, tab, parent)
            yield from walk(
                item.field.repeatingSectionGrid, f"{path}.field.repeatingSectionGrid", tab, item
            )

    for t, tab in enumerate(form.tabs):
        yield from walk(tab.questions, f"tabs[{t}].questions", t, None)


def _fields(form: schema.Form) -> Iterator[Item]:
    """Items that are not sections."""
    return (i for i in _items(form) if i.field.type not in SECTION_TYPES)


def _finish_indices(form: schema.Form) -> list[int]:
    return [t for t, tab in enumerate(form.tabs) if tab.type == "FINISH"]


# --- rules ------------------------------------------------------------------------------------


def check_title(form: schema.Form) -> list[Issue]:
    if not form.title.strip():
        return [_error("L001", "title", "Tytuł formularza jest pusty")]
    if len(form.title) > TITLE_MAX:
        return [
            _error(
                "L001",
                "title",
                f"Tytuł formularza ma {len(form.title)} znaków, a może mieć najwyżej {TITLE_MAX}",
            )
        ]
    return []


def check_page_count(form: schema.Form) -> list[Issue]:
    if len(form.tabs) < 2:
        return [_error("L002", "tabs", "Formularz musi mieć co najmniej dwie strony")]
    return []


def check_finish_count(form: schema.Form) -> list[Issue]:
    finishes = _finish_indices(form)
    if not finishes:
        return [_error("L003", "tabs", "Brak strony końcowej (FINISH)")]
    return [
        _error("L003", f"tabs[{t}]", "Formularz może mieć tylko jedną stronę końcową (FINISH)")
        for t in finishes[:-1]
    ]


def check_finish_last(form: schema.Form) -> list[Issue]:
    finishes = _finish_indices(form)
    if len(finishes) == 1 and finishes[0] != len(form.tabs) - 1:
        return [_error("L004", f"tabs[{finishes[0]}]", "Strona końcowa (FINISH) nie jest ostatnia")]
    return []


def check_nesting(form: schema.Form) -> list[Issue]:
    issues = []
    for it in _items(form):
        is_section = it.field.type in SECTION_TYPES
        if it.section is None and not is_section:
            issues.append(_error("L005", it.path, "Pole leży poza sekcją"))
        elif it.section is not None and is_section:
            issues.append(_error("L006", it.path, "Sekcja leży w innej sekcji"))
        elif it.section is not None and it.section.field.type not in SECTION_TYPES:
            issues.append(_error("L006", it.path, "Pole leży wewnątrz innego pola, a nie w sekcji"))
    return issues


def check_page_has_fields(form: schema.Form) -> list[Issue]:
    with_fields = {it.tab for it in _fields(form)}
    return [
        _error("L007", f"tabs[{t}]", f"Strona „{tab.title}” nie ma żadnego pola")
        for t, tab in enumerate(form.tabs)
        if t not in with_fields
    ]


def check_finish_inputs(form: schema.Form) -> list[Issue]:
    finishes = set(_finish_indices(form))
    return [
        _error(
            "L008",
            it.path,
            f"Na stronie końcowej nie może być pola do wypełnienia ({it.field.type})",
        )
        for it in _fields(form)
        if it.tab in finishes and it.field.type not in FINISH_TYPES
    ]


def check_types(form: schema.Form) -> list[Issue]:
    allowed = FIELD_TYPES | SECTION_TYPES
    return [
        _error("L009", f"{it.path}.field.type", f"Niedozwolony typ komponentu: {it.field.type}")
        for it in _items(form)
        if it.field.type not in allowed
    ]


def check_validation_list(form: schema.Form) -> list[Issue]:
    return [
        _error("L010", f"{it.path}.field.validation", "Walidacja musi być listą nazw walidatorów")
        for it in _items(form)
        if not isinstance(it.field.validation, list)
    ]


def check_validators(form: schema.Form) -> list[Issue]:
    issues = []
    for it in _items(form):
        if not isinstance(it.field.validation, list):
            continue
        path = f"{it.path}.field.validation"
        if unknown := [v for v in it.field.validation if v not in VALIDATORS]:
            issues.append(_error("L011", path, f"Nieznany walidator: {', '.join(unknown)}"))
        if wrong := _incompatible_validators(it.field):
            issues.append(
                _error(
                    "L012",
                    path,
                    f"Walidator {', '.join(wrong)} nie pasuje do pola typu {it.field.type}",
                )
            )
    return issues


def _incompatible_validators(field: schema.Field) -> list[str]:
    """Per the technical rules: any validator on TEXT_FIELD, only REQUIRED on other inputs."""
    if not isinstance(field.validation, list) or field.type == FieldType.TEXT_FIELD.value:
        return []
    allowed: set[str] = set() if field.type in PRESENTATION_TYPES else {Validator.REQUIRED.value}
    return [v for v in field.validation if v in VALIDATORS and v not in allowed]


def check_dictionary(form: schema.Form) -> list[Issue]:
    issues = []
    for it in _items(form):
        if it.field.dictionaryName is None:
            continue
        path = f"{it.path}.field.dictionaryName"
        if it.field.type not in CHOICE:
            issues.append(
                _error("L013", path, "Słownik jest dozwolony tylko w SELECT, RADIO i CHECKBOX")
            )
        if it.field.options:
            issues.append(_error("L014", path, "Pole ze słownikiem musi mieć pustą listę opcji"))
    return issues


def check_external_values(form: schema.Form) -> list[Issue]:
    issues = []
    for it in _items(form):
        value = it.field.defaultValue
        if it.field.defaultValueType == "EXTERNAL_SYSTEM" and not (
            isinstance(value, str) and REGISTER_VALUE.match(value)
        ):
            issues.append(
                _error(
                    "L015",
                    f"{it.path}.field.defaultValue",
                    f"Dane inicjalne muszą wskazywać atrybut PESEL, PESEL_ADDRESS albo MLPZ, "
                    f"a jest: {value!r}",
                )
            )
    return issues


def _from_pesel(field: schema.Field) -> bool:
    value = field.defaultValue
    return (
        field.defaultValueType == "EXTERNAL_SYSTEM"
        and isinstance(value, str)
        and bool(PESEL_VALUE.match(value))
    )


def check_pesel_read_only(form: schema.Form) -> list[Issue]:
    return [
        _error(
            "L016", f"{it.path}.field.readOnly", "Pole z rejestru PESEL musi być tylko do odczytu"
        )
        for it in _items(form)
        if _from_pesel(it.field) and not it.field.readOnly
    ]


def check_unique_ids(form: schema.Form) -> list[Issue]:
    seen: set[str] = set()
    issues = []
    entries = [(f"tabs[{t}].id", tab.id) for t, tab in enumerate(form.tabs)]
    entries += [(f"{it.path}.field.id", it.field.id) for it in _items(form)]
    for path, id_ in entries:
        if id_ in seen:
            issues.append(_error("L017", path, f"Identyfikator {id_} się powtarza"))
        seen.add(id_)
    return issues


def check_technames(form: schema.Form) -> list[Issue]:
    seen: set[str] = set()
    issues = []
    for it in _items(form):
        name, path = it.field.techName, f"{it.path}.field.techName"
        if not name.strip():
            issues.append(_error("L018", path, "Brak nazwy technicznej (techName)"))
        elif name in seen:
            issues.append(_error("L018", path, f"Nazwa techniczna {name} się powtarza"))
        seen.add(name)
    return issues


def check_page_titles(form: schema.Form) -> list[Issue]:
    counts = Counter(tab.title for tab in form.tabs)
    return [
        _error("L019", f"tabs[{t}].title", f"Tytuł strony „{tab.title}” się powtarza")
        for t, tab in enumerate(form.tabs)
        if counts[tab.title] > 1
    ]


def check_queries(form: schema.Form) -> list[Issue]:
    issues = []
    for it in _items(form):
        for s, state in enumerate(it.field.states):
            issues += _check_query(form, state.query, f"{it.path}.field.states[{s}].query")
    return issues


def _check_query(form: schema.Form, query: str, path: str) -> list[Issue]:
    try:
        condition, locations = parse(query)
    except ValueError as exc:
        return [_error("L020", path, f"Zapytanie JSONata nie pasuje do szablonu: {exc}")]
    issues = []
    targets: dict[str, schema.Field] = {}
    for loc in locations.values():
        tabs = [tab for tab in form.tabs if tab.title == loc.page]
        sections = [
            q.field for tab in tabs for q in tab.questions if q.field.techName == loc.section
        ]
        fields = [
            g.field
            for s in sections
            for g in s.repeatingSectionGrid
            if g.field.techName == loc.field
        ]
        if not tabs:
            issues.append(
                _error("L021", path, f"Zapytanie wskazuje nieistniejącą stronę „{loc.page}”")
            )
        elif not sections:
            issues.append(
                _error("L021", path, f"Zapytanie wskazuje nieistniejącą sekcję {loc.section}")
            )
        elif not fields:
            issues.append(
                _error("L021", path, f"Zapytanie wskazuje nieistniejące pole {loc.field}")
            )
        else:
            targets[loc.field] = fields[0]
    for cond in simple_conds(condition):
        target = targets.get(cond.field)
        if target is None or not target.options:
            continue
        values = {o.name for o in target.options} | {o.id for o in target.options}
        if cond.value not in values:
            issues.append(
                _error(
                    "L022",
                    path,
                    f"Zapytanie wskazuje wartość „{cond.value}”, której nie ma w opcjach pola "
                    f"{cond.field}",
                )
            )
    return issues


def check_flow(form: schema.Form) -> list[Issue]:
    tab_ids = {tab.id for tab in form.tabs}
    links = form.flow.links
    issues = [
        _error("L023", f"flow.links[{i}]", "Przejście wskazuje nieistniejącą stronę")
        for i, link in enumerate(links)
        if link.source not in tab_ids or link.target not in tab_ids
    ]
    if issues or not form.tabs:
        return issues
    if not _is_single_path(form):
        issues.append(
            _error(
                "L024",
                "flow.links",
                "Przejścia między stronami nie tworzą jednej ścieżki przez wszystkie strony "
                "kończącej się na stronie końcowej",
            )
        )
    return issues


def _is_single_path(form: schema.Form) -> bool:
    links = form.flow.links
    if len(links) != len(form.tabs) - 1:
        return False
    targets = {link.target for link in links}
    following = {link.source: link.target for link in links}
    starts = [tab.id for tab in form.tabs if tab.id not in targets]
    if len(following) != len(links) or len(targets) != len(links) or len(starts) != 1:
        return False
    visited, current = [starts[0]], starts[0]
    while current in following and len(visited) <= len(form.tabs):
        current = following[current]
        visited.append(current)
    last = next((tab for tab in form.tabs if tab.id == current), None)
    return len(set(visited)) == len(form.tabs) and last is not None and last.type == "FINISH"


def check_plain_language(form: schema.Form) -> list[Issue]:
    issues = []
    for it in _items(form):
        words = WORD.findall(it.field.title.lower())
        path = f"{it.path}.field.title"
        if hard := [w for w in words if HARD_WORD.match(w)]:
            issues.append(_warning("L101", path, f"Zamiast „{hard[0]}” użyj prostszego słowa"))
        if participles := [w for w in words if PARTICIPLE.search(w)]:
            issues.append(_warning("L102", path, f"Unikaj imiesłowów: {', '.join(participles)}"))
        if long := [w for w in words if len(VOWEL_RUN.findall(w)) > MAX_SYLLABLES]:
            issues.append(
                _warning(
                    "L103",
                    path,
                    f"Długie słowa (powyżej {MAX_SYLLABLES} sylab): {', '.join(long)}",
                )
            )
        if impersonal := [w for w in words if w in IMPERSONAL]:
            issues.append(
                _warning(
                    "L104",
                    path,
                    f"Zwracaj się wprost do osoby zamiast formy „{impersonal[0]}”",
                )
            )
    return issues


def check_consent_checkbox(form: schema.Form) -> list[Issue]:
    issues = []
    for it in _fields(form):
        if it.field.type != FieldType.CHECKBOX.value:
            continue
        texts = [it.field.title] + [o.name for o in it.field.options]
        if any(t.strip().lower().startswith(CONSENT_PREFIXES) for t in texts):
            issues.append(
                _warning(
                    "L110",
                    it.path,
                    "Zgody i oświadczenia umieść w sekcji zgód (CONSENT_SECTION), nie w CHECKBOX",
                )
            )
    return issues


def _needs_search(field: schema.Field) -> bool:
    return (
        field.type == FieldType.SELECT.value
        and len(field.options) > SEARCH_THRESHOLD
        and not field.searchEnabled
    )


def check_select_search(form: schema.Form) -> list[Issue]:
    return [
        _warning(
            "L111",
            f"{it.path}.field.searchEnabled",
            f"Lista ma {len(it.field.options)} opcji, więc potrzebuje wyszukiwarki",
        )
        for it in _items(form)
        if _needs_search(it.field)
    ]


type Rule = Callable[[schema.Form], list[Issue]]

RULES: list[Rule] = [
    check_title,
    check_page_count,
    check_finish_count,
    check_finish_last,
    check_nesting,
    check_page_has_fields,
    check_finish_inputs,
    check_types,
    check_validation_list,
    check_validators,
    check_dictionary,
    check_external_values,
    check_pesel_read_only,
    check_unique_ids,
    check_technames,
    check_page_titles,
    check_queries,
    check_flow,
    check_plain_language,
    check_consent_checkbox,
    check_select_search,
]


def lint(form: schema.Form) -> list[Issue]:
    return [issue for rule in RULES for issue in rule(form)]


# --- repairs ----------------------------------------------------------------------------------
# Each repair mutates the working copy in place. `fix` runs them in order and marks the issues of
# the rules a repair targets that disappeared after it ran.


def _fix_validation(form: schema.Form) -> None:
    for it in _items(form):
        if it.field.validation == {}:
            it.field.validation = []
        if wrong := _incompatible_validators(it.field):
            it.field.validation = [v for v in it.field.validation if v not in wrong]


def _unique(base: str, taken: set[str]) -> str:
    name, n = base, 2
    while name in taken:
        name, n = f"{base}_{n}", n + 1
    taken.add(name)
    return name


def _fix_technames(form: schema.Form) -> None:
    taken = {it.field.techName for it in _items(form) if it.field.techName.strip()}
    seen: set[str] = set()
    for it in _items(form):
        name = it.field.techName
        if name.strip() and name not in seen:
            seen.add(name)
            continue
        base = name if name.strip() else slugify(it.field.title) or it.field.type.lower()
        it.field.techName = _unique(base, taken)
        seen.add(it.field.techName)


def _fix_finish(form: schema.Form) -> None:
    finishes = _finish_indices(form)
    if len(finishes) == 1:
        form.tabs.append(form.tabs.pop(finishes[0]))
    elif not finishes and form.tabs:
        form.tabs.append(_finish_tab(form))


def _finish_tab(form: schema.Form) -> schema.Tab:
    """End page like in the references: a preview section with a single text block."""
    taken = {it.field.techName for it in _items(form)}
    titles = {tab.title for tab in form.tabs}
    title, n = FINISH_TITLE, 2
    while title in titles:
        title, n = f"{FINISH_TITLE} {n}", n + 1
    page = PageIR(
        title=title,
        kind="FINISH",
        sections=[
            SectionIR(
                key=_unique("podglad_uzupelnionego_wniosku", taken),
                title="Podgląd uzupełnionego wniosku",
                fields=[
                    FieldIR(
                        key=_unique("podglad", taken),
                        label="",
                        type=FieldType.TEXT_BLOCK,
                        description=PREVIEW_TEXT,
                    )
                ],
            )
        ],
    )
    return build(FormIR(title=form.title[:TITLE_MAX], pages=[page])).tabs[0]


def _fix_ids(form: schema.Form) -> None:
    seen: set[str] = set()
    for t, tab in enumerate(form.tabs):
        if tab.id in seen:
            tab.id = stable_id("tab", f"{tab.title}#{t}")
        seen.add(tab.id)
    for it in _items(form):
        if it.field.id in seen:
            it.field.id = stable_id("item", f"{it.field.techName}#{it.path}")
        seen.add(it.field.id)


def _fix_fields(form: schema.Form) -> None:
    for it in _items(form):
        if _from_pesel(it.field):
            it.field.readOnly = True
        if _needs_search(it.field):
            it.field.searchEnabled = True


def _fix_flow(form: schema.Form) -> None:
    if not check_flow(form):
        return
    form.flow.links = [
        schema.Link(id=stable_id("link", f"{a.id}>{b.id}"), source=a.id, target=b.id)
        for a, b in pairwise(form.tabs)
    ]


type Repair = Callable[[schema.Form], None]

REPAIRS: list[tuple[Repair, frozenset[str]]] = [
    (_fix_validation, frozenset({"L010", "L012"})),
    (_fix_technames, frozenset({"L018"})),
    (_fix_finish, frozenset({"L002", "L003", "L004"})),
    (_fix_ids, frozenset({"L017"})),
    (_fix_fields, frozenset({"L016", "L111"})),
    (_fix_flow, frozenset({"L023", "L024"})),
]


def fix(form: schema.Form) -> tuple[schema.Form, list[Issue]]:
    """Repair what can be repaired; returns the copy, the repaired issues and the remaining ones."""
    work = form.model_copy(deep=True)
    repaired: list[Issue] = []
    for repair, codes in REPAIRS:
        before = [i for i in lint(work) if i.code in codes]
        repair(work)
        after = lint(work)
        repaired += [i.model_copy(update={"fixed": True}) for i in before if i not in after]
    return work, repaired + lint(work)
