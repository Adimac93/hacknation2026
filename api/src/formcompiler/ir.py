"""Intermediate representation (IR) of a form: what the model returns and the compiler consumes."""

from collections.abc import Iterator
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,59}$")]
LineId = Annotated[str, Field(pattern=r"^L\d+$")]
RegisterAttribute = Annotated[str, Field(pattern=r"^(PESEL|PESEL_ADDRESS|MLPZ)\.[A-Za-z]+$")]


class FieldType(StrEnum):
    TEXT_FIELD = "TEXT_FIELD"
    TEXTAREA = "TEXTAREA"
    NUMBER = "NUMBER"
    DATEPICKER = "DATEPICKER"
    SELECT = "SELECT"
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    FILE_UPLOADER = "FILE_UPLOADER"
    CONSENT_SECTION = "CONSENT_SECTION"
    TEXT_BLOCK = "TEXT_BLOCK"
    INFO_SECTION = "INFO_SECTION"


CHOICE_TYPES = frozenset({FieldType.SELECT, FieldType.RADIO, FieldType.CHECKBOX})


class Validator(StrEnum):
    REQUIRED = "REQUIRED"
    EMAIL = "EMAIL"
    PESEL = "PESEL"
    NIP = "NIP"
    REGON = "REGON"
    ZIP_CODE = "ZIP_CODE"
    EPUAP = "EPUAP"
    ADE = "ADE"
    SERIAL_NUMBER_ID_CARD = "SERIAL_NUMBER_ID_CARD"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Cond(_Model):
    """Simple condition: the answer of choice field `field` contains (or not) `value`."""

    field: Key
    op: Literal["IN", "NOT_IN"] = "IN"
    value: str


class CondGroup(_Model):
    match: Literal["all", "any"]
    conds: list[Cond | CondGroup] = Field(min_length=2)


type Condition = Cond | CondGroup


def simple_conds(condition: Condition | None) -> list[Cond]:
    match condition:
        case None:
            return []
        case Cond():
            return [condition]
        case CondGroup(conds=conds):
            return [c for inner in conds for c in simple_conds(inner)]


class Consent(_Model):
    text: str = ""
    # Verbatim HTML from a template or a reference; the model only ever writes `text`.
    html: str | None = None
    required: bool = True


class FieldIR(_Model):
    key: Key
    label: str
    description: str = ""
    description_html: str | None = None
    type: FieldType
    required: bool = False
    validators: list[Validator] = []
    options: list[str] = []
    dictionary: str | None = None
    initial: RegisterAttribute | None = None
    default: str | None = None
    read_only: bool = False
    consents: list[Consent] = []
    show_if: Condition | None = None
    read_only_if: Condition | None = None
    src: list[LineId] = []
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _type_specific_rules(self) -> Self:
        if self.dictionary is not None:
            if self.type not in CHOICE_TYPES:
                raise ValueError(f"dictionary is allowed only for {sorted(CHOICE_TYPES)}")
            if self.options:
                raise ValueError("a field with a dictionary must have empty options")
        if self.consents and self.type is not FieldType.CONSENT_SECTION:
            raise ValueError("consents are allowed only in CONSENT_SECTION")
        return self


class SectionIR(_Model):
    key: Key
    ref: str | None = None
    title: str
    description: str = ""
    description_html: str | None = None
    repeating: bool = False
    show_if: Condition | None = None
    fields: list[FieldIR] = []


class PageIR(_Model):
    title: str
    kind: Literal["MAIN", "FINISH"] = "MAIN"
    sections: list[SectionIR]


class Addressee(_Model):
    name: str
    kind: Literal["URZAD", "ORGAN"]


class Applicant(_Model):
    persons: bool = True
    entities: bool = False
    proxy: bool = False


class FormIR(_Model):
    title: str = Field(max_length=255)
    addressee: Addressee | None = None
    applicant: Applicant = Applicant()
    pages: list[PageIR]

    def fields(self) -> Iterator[FieldIR]:
        for page in self.pages:
            for section in page.sections:
                yield from section.fields

    @model_validator(mode="after")
    def _references_resolve(self) -> Self:
        section_keys = [s.key for p in self.pages for s in p.sections]
        by_key: dict[str, FieldIR] = {}
        for f in self.fields():
            if f.key in by_key or f.key in section_keys:
                raise ValueError(f"duplicate key: {f.key}")
            by_key[f.key] = f
        if duplicates := {k for k in section_keys if section_keys.count(k) > 1}:
            raise ValueError(f"duplicate section keys: {sorted(duplicates)}")

        conditions = [s.show_if for p in self.pages for s in p.sections]
        conditions += [c for f in self.fields() for c in (f.show_if, f.read_only_if)]
        for cond in (c for condition in conditions for c in simple_conds(condition)):
            target = by_key.get(cond.field)
            if target is None:
                raise ValueError(f"condition references unknown field: {cond.field}")
            if target.type not in CHOICE_TYPES:
                raise ValueError(f"condition references non-choice field: {cond.field}")
            if target.options and cond.value not in target.options:
                raise ValueError(f"condition value {cond.value!r} is not an option of {cond.field}")
        return self
