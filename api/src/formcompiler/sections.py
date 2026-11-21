"""Predefined COI sections and assembly of a full form around the subject pages.

The library is generated from the reference forms (devtools/extract_sections.py) and shipped as
data, so the service never reads Docs/. `assemble` adds the standard data page, the contact page
and the finish page, and prunes applicant branches the form does not need.
"""

from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict

from formcompiler.ir import (
    Addressee,
    Applicant,
    Cond,
    CondGroup,
    Condition,
    FieldIR,
    FieldType,
    FormIR,
    PageIR,
    SectionIR,
)

APPLICANT_FIELD = "wybierz_w_czyim_imieniu_wnioskujesz"
PROXY_OPTION = "Innej osoby"
ENTITY_OPTION = "Osoby prawnej lub jednostki organizacyjnej"
SINGLE_CHOICE = frozenset({FieldType.RADIO, FieldType.SELECT})


class Library(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    data_page_title: str
    addressee: dict[Literal["URZAD", "ORGAN"], SectionIR]
    applicant: list[SectionIR]
    contact: PageIR
    finish: PageIR

    def keys(self) -> set[str]:
        sections = [*self.addressee.values(), *self.applicant]
        sections += [*self.contact.sections, *self.finish.sections]
        return {s.key for s in sections} | {f.key for s in sections for f in s.fields}


LIBRARY = Library.model_validate_json(
    files("formcompiler").joinpath("data/sections.json").read_text(encoding="utf-8")
)
RESERVED_KEYS = frozenset(LIBRARY.keys())


def assemble(
    title: str, addressee: Addressee | None, applicant: Applicant, subject: list[PageIR]
) -> FormIR:
    """Standard data page, then the subject pages, then contact and finish pages."""
    clashes = RESERVED_KEYS & {
        key
        for page in subject
        for s in page.sections
        for key in (s.key, *(f.key for f in s.fields))
    }
    if clashes:
        raise ValueError(f"subject keys collide with predefined sections: {sorted(clashes)}")

    removed = set()
    if not applicant.proxy:
        removed.add((APPLICANT_FIELD, PROXY_OPTION))
    if not applicant.entities:
        removed.add((APPLICANT_FIELD, ENTITY_OPTION))
    data_sections = _prune(LIBRARY.applicant, removed)
    if addressee is not None:
        data_sections.insert(0, _addressee_section(addressee))

    data_page = PageIR(title=LIBRARY.data_page_title, sections=data_sections)
    return FormIR(
        title=title,
        addressee=addressee,
        applicant=applicant,
        pages=[data_page, *subject, LIBRARY.contact, LIBRARY.finish],
    )


def _addressee_section(addressee: Addressee) -> SectionIR:
    template = LIBRARY.addressee[addressee.kind]
    name_field = template.fields[0].model_copy(update={"default": addressee.name})
    return template.model_copy(update={"fields": [name_field, *template.fields[1:]]})


def _prune(sections: list[SectionIR], removed: set[tuple[str, str]]) -> list[SectionIR]:
    """Drop removed options, then every section or field that can no longer be shown."""
    current = [
        s.model_copy(update={"fields": [_without_options(f, removed) for f in s.fields]})
        for s in sections
    ]
    dropped: set[str] = set()
    while True:
        pruned = _prune_once(current, removed, dropped)
        if pruned == current:
            return pruned
        current = pruned


def _without_options(field: FieldIR, removed: set[tuple[str, str]]) -> FieldIR:
    return field.model_copy(
        update={"options": [o for o in field.options if (field.key, o) not in removed]}
    )


def _prune_once(
    sections: list[SectionIR], removed: set[tuple[str, str]], dropped: set[str]
) -> list[SectionIR]:
    out = []
    for section in sections:
        show = _simplify(section.show_if, removed, dropped)
        if show is False:
            dropped.update(f.key for f in section.fields)
            continue
        fields = []
        for field in section.fields:
            field_show = _simplify(field.show_if, removed, dropped)
            pointless_choice = (
                field.type in SINGLE_CHOICE and field.dictionary is None and len(field.options) < 2
            )
            if field_show is False or pointless_choice:
                dropped.add(field.key)
                continue
            read_only = (
                None
                if field.read_only_if is None
                else _simplify(field.read_only_if, removed, dropped)
            )
            fields.append(
                field.model_copy(
                    update={
                        "show_if": None if field_show is True else field_show,
                        "read_only": field.read_only or read_only is True,
                        "read_only_if": None if isinstance(read_only, bool) else read_only,
                    }
                )
            )
        if fields:
            out.append(
                section.model_copy(
                    update={"show_if": None if show is True else show, "fields": fields}
                )
            )
    return out


def _simplify(
    condition: Condition | None, removed: set[tuple[str, str]], dropped: set[str]
) -> Condition | bool:
    """Partially evaluate a condition: answers that can no longer occur are known to be empty."""
    match condition:
        case None:
            return True
        case Cond(field=key, op=op, value=value):
            if key in dropped or (key, value) in removed:
                return op == "NOT_IN"
            return condition
        case CondGroup(match=match, conds=conds):
            parts = [_simplify(c, removed, dropped) for c in conds]
            decisive = match == "any"
            if decisive in parts:
                return decisive
            rest = [p for p in parts if not isinstance(p, bool)]
            if not rest:
                return not decisive
            return rest[0] if len(rest) == 1 else CondGroup(match=match, conds=rest)
