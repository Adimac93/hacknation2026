"""Output JSON of the COI Form Generator, modelled on the two reference files in Docs/.

The references (not the organiser's schema file) are the source of truth: for example the
section grid key is `repeatingSectionGrid`, while the schema file spells it `repetingSectionGrid`.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ComponentType = Literal[
    "SECTION",
    "REPEATING_SECTION",
    "TEXT_FIELD",
    "TEXTAREA",
    "NUMBER",
    "DATEPICKER",
    "SELECT",
    "RADIO",
    "CHECKBOX",
    "FILE_UPLOADER",
    "CONSENT_SECTION",
    "TEXT_BLOCK",
    "INFO_SECTION",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Option(_Model):
    id: str
    name: str
    techName: str | None = None


class State(_Model):
    type: Literal["SHOW", "READ_ONLY"]
    query: str


class Consent(_Model):
    description: str
    required: bool


class ConsentSectionConfig(_Model):
    consents: list[Consent]
    files: list[dict[str, Any]] = []


class Field(_Model):
    id: str
    type: ComponentType
    techName: str
    title: str
    description: str
    options: list[Option] = []
    # A list of validator names per the import description; reference 1 has `{}` in a few
    # fields, accepted only so the references parse. The compiler always writes a list.
    validation: list[str] | dict[str, Any] = []
    readOnly: bool = False
    repeatingSectionGrid: list[GridItem] = []
    states: list[State] = []
    questionOrder: int
    tooltipMessage: str = ""
    defaultValue: str | list[str] | None = None
    defaultValueType: Literal["EXTERNAL_SYSTEM"] | None = None
    dictionaryName: str | None = None
    multiLevelTree: bool | None = None
    searchEnabled: bool | None = None
    consentSectionConfig: ConsentSectionConfig | None = None


class GridItem(_Model):
    x: int
    y: int
    rows: int
    cols: int
    field: Field
    minItemRows: int | None = None


class Tab(_Model):
    id: str
    title: str
    type: Literal["MAIN", "FINISH"]
    questions: list[GridItem]


class Link(_Model):
    id: str
    source: str
    target: str


class Flow(_Model):
    links: list[Link]


class Form(_Model):
    title: str
    tabs: list[Tab]
    flow: Flow

    def dump(self) -> dict[str, Any]:
        """JSON ready for import: optional keys that are not set are left out."""
        return self.model_dump(mode="json", exclude_none=True)
