"""IR -> output JSON. Pure and deterministic: the same IR always gives the same JSON."""

import re
import unicodedata
import uuid
from collections.abc import Callable
from itertools import pairwise

from formcompiler import schema
from formcompiler.ir import Condition, FieldIR, FieldType, FormIR, PageIR, SectionIR, Validator
from formcompiler.query import Location, render
from formcompiler.richtext import EMPTY_DOCUMENT, to_html

ID_NAMESPACE = uuid.UUID("6f1c2b8e-3d4a-5f60-9b7c-0e1d2c3b4a59")
POLISH = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
GRID_COLS = 3
TREE_DICTIONARY_PREFIX = "TERYT"
SEARCH_THRESHOLD = 15

type Locate = Callable[[str], Location]


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text.translate(POLISH))
    ascii_text = ascii_text.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def stable_id(kind: str, name: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, f"{kind}:{name}"))


def description(text: str, html: str | None, *, empty: str) -> str:
    if html is not None:
        return html
    return to_html(text) if text else empty


def build(ir: FormIR) -> schema.Form:
    locations = {
        f.key: Location(page=page.title, section=section.key, field=f.key)
        for page in ir.pages
        for section in page.sections
        for f in section.fields
    }
    tabs = [_tab(page, locations.__getitem__) for page in ir.pages]
    links = [
        schema.Link(id=stable_id("link", f"{a.id}>{b.id}"), source=a.id, target=b.id)
        for a, b in pairwise(tabs)
    ]
    return schema.Form(title=ir.title, tabs=tabs, flow=schema.Flow(links=links))


def _tab(page: PageIR, locate: Locate) -> schema.Tab:
    questions: list[schema.GridItem] = []
    y = 0
    for section in page.sections:
        item = _section(section, y, locate)
        questions.append(item)
        y += item.rows
    return schema.Tab(
        id=stable_id("tab", page.title), title=page.title, type=page.kind, questions=questions
    )


def _states(
    locate: Locate, show_if: Condition | None, read_only_if: Condition | None = None
) -> list[schema.State]:
    states = []
    if show_if is not None:
        states.append(schema.State(type="SHOW", query=render(show_if, locate)))
    if read_only_if is not None:
        states.append(schema.State(type="READ_ONLY", query=render(read_only_if, locate)))
    return states


def _section(section: SectionIR, y: int, locate: Locate) -> schema.GridItem:
    grid = [
        schema.GridItem(x=0, y=i, rows=1, cols=GRID_COLS, field=_field(f, i, locate))
        for i, f in enumerate(section.fields)
    ]
    field = schema.Field(
        id=stable_id("item", section.key),
        type="REPEATING_SECTION" if section.repeating else "SECTION",
        techName=section.key,
        title=section.title,
        description=description(
            section.description, section.description_html, empty=EMPTY_DOCUMENT
        ),
        options=[],
        validation=[],
        readOnly=False,
        repeatingSectionGrid=grid,
        states=_states(locate, section.show_if),
        questionOrder=y,
        tooltipMessage="",
    )
    return schema.GridItem(x=0, y=y, rows=len(grid) + 1, cols=GRID_COLS, field=field)


def _validation(f: FieldIR) -> list[str]:
    names = [Validator.REQUIRED] if f.required else []
    names += [v for v in f.validators if v not in names]
    return [str(v) for v in names]


def _field(f: FieldIR, order: int, locate: Locate) -> schema.Field:
    field = schema.Field(
        id=stable_id("item", f.key),
        type=f.type.value,
        techName=f.key,
        title=f.label,
        description=description(f.description, f.description_html, empty=""),
        options=[schema.Option(id=o, name=o, techName=slugify(o)) for o in f.options],
        validation=_validation(f),
        readOnly=f.read_only,
        repeatingSectionGrid=[],
        states=_states(locate, f.show_if, f.read_only_if),
        questionOrder=order,
        tooltipMessage="",
        dictionaryName=f.dictionary,
    )
    if f.initial is not None:
        field.defaultValue = f.initial
        field.defaultValueType = "EXTERNAL_SYSTEM"
    elif f.type is FieldType.SELECT:
        field.defaultValue = [f.default] if f.default is not None else []
    elif f.default is not None:
        field.defaultValue = f.default
    if f.type is FieldType.SELECT:
        field.searchEnabled = f.dictionary is not None or len(f.options) > SEARCH_THRESHOLD
        if f.dictionary is not None:
            field.multiLevelTree = f.dictionary.startswith(TREE_DICTIONARY_PREFIX)
    if f.type is FieldType.CONSENT_SECTION:
        field.consentSectionConfig = schema.ConsentSectionConfig(
            consents=[
                schema.Consent(
                    description=description(c.text, c.html, empty=EMPTY_DOCUMENT),
                    required=c.required,
                )
                for c in f.consents
            ],
            files=[],
        )
    return field
