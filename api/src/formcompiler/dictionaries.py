"""Proposals of new dictionaries for the report (task extension II), without the model.

A choice field with inline options that read like a short closed list is a candidate for a
reusable dictionary. The form itself keeps its inline options; the proposal only goes to the
report. Fields of the predefined COI sections, yes/no questions and lists that an existing COI
dictionary already covers are left out.
"""

import re
from collections.abc import Iterator

from formcompiler import schema
from formcompiler.compiler import slugify
from formcompiler.llm import Dictionary
from formcompiler.report import DictionaryProposal
from formcompiler.sections import RESERVED_KEYS

CHOICE = frozenset({"SELECT", "RADIO", "CHECKBOX"})
MIN_ITEMS = 3
# Dictionary entries are names, not sentences; longer options are form-specific statements.
MAX_ITEM_WORDS = 6

YES_NO = frozenset({"tak", "nie", "nie dotyczy", "nie wiem", "brak"})

# Existing COI dictionaries ("Hacknation - Słowniki") and the label stems they cover.
EXISTING: dict[Dictionary, tuple[str, ...]] = {
    Dictionary.KRAJE: ("kraj", "panstw", "obywatelstw"),
    Dictionary.WOJEWODZTWO: ("wojewodztw",),
    Dictionary.POWIAT: ("powiat",),
    Dictionary.GMINA: ("gmina",),
    Dictionary.MIEJSCOWOSC: ("miejscowosc",),
    Dictionary.NUMERY_KIERUNKOWE: ("kierunkow", "prefiks"),
}
VOIVODESHIPS = frozenset(
    slugify(name)
    for name in [
        "dolnośląskie",
        "kujawsko-pomorskie",
        "lubelskie",
        "lubuskie",
        "łódzkie",
        "małopolskie",
        "mazowieckie",
        "opolskie",
        "podkarpackie",
        "podlaskie",
        "pomorskie",
        "śląskie",
        "świętokrzyskie",
        "warmińsko-mazurskie",
        "wielkopolskie",
        "zachodniopomorskie",
    ]
)

# Labels that are instructions rather than names; the section title names the list instead.
INSTRUCTION = re.compile(r"^(a\s+)?(następnie\s+)?(wybierz|zaznacz|proszę|należy|wskaż|podaj)\b")


def propose(form: schema.Form) -> list[DictionaryProposal]:
    """One proposal per distinct option list, in form order, listing every field that uses it."""
    groups: dict[tuple[str, ...], DictionaryProposal] = {}
    for field, section in _choice_fields(form):
        items = [o.name.strip() for o in field.options if o.name.strip()]
        if not _looks_like_dictionary(field.title, items):
            continue
        signature = tuple(slugify(i) for i in items)
        if signature in groups:
            old = groups[signature]
            groups[signature] = old.model_copy(update={"fields": [*old.fields, field.techName]})
        else:
            name = _name(field.title, section.title if section else "")
            groups[signature] = DictionaryProposal(name=name, items=items, fields=[field.techName])
    return list(groups.values())


def _choice_fields(form: schema.Form) -> Iterator[tuple[schema.Field, schema.Field | None]]:
    def walk(
        items: list[schema.GridItem], parent: schema.Field | None
    ) -> Iterator[tuple[schema.Field, schema.Field | None]]:
        for item in items:
            field = item.field
            if (
                field.type in CHOICE
                and field.dictionaryName is None
                and field.techName not in RESERVED_KEYS
            ):
                yield field, parent
            yield from walk(field.repeatingSectionGrid, field)

    for tab in form.tabs:
        yield from walk(tab.questions, None)


def _looks_like_dictionary(label: str, items: list[str]) -> bool:
    slugs = [slugify(i).replace("_", " ") for i in items]
    if len(set(slugs)) < MIN_ITEMS:
        return False
    if all(s in YES_NO for s in slugs):
        return False
    if any(len(i.split()) > MAX_ITEM_WORDS for i in items):
        return False
    return not _covered(label, slugs)


def _covered(label: str, slugs: list[str]) -> bool:
    """True when an existing COI dictionary already holds this list."""
    words = slugify(label).split("_")
    if any(w.startswith(stems) for stems in EXISTING.values() for w in words):
        return True
    known = sum(s.replace(" ", "_") in VOIVODESHIPS for s in slugs) + slugs.count("polska")
    return known * 2 >= len(slugs)


def _name(label: str, section: str) -> str:
    def clean(text: str) -> str:
        text = re.sub(r"\([^)]*\)?", " ", text)
        return " ".join(text.split()).strip(" .:;?!-\u2013")

    name = clean(label)
    if INSTRUCTION.match(name.lower()) and clean(section):
        name = clean(section)
    return name[:1].upper() + name[1:]
