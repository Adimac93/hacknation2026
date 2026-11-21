"""Processing report returned with `?details=true` (contract in ARCHITECTURE 8.1)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from formcompiler.document import Document


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_by_name=True, serialize_by_alias=True
    )


class Timings(_Model):
    """Stage durations in milliseconds; stages that did not run stay at 0."""

    ingest: int = 0
    heuristics: int = 0
    llm: int = 0
    compile: int = 0
    lint: int = 0


class LintIssue(_Model):
    code: str
    severity: Literal["error", "warning"]
    message: str
    path: str
    fixed: bool = False


class FieldReport(_Model):
    """Where a field came from in the document and how sure the pipeline is about it."""

    tech_name: str = Field(alias="techName")
    src: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0)


class DictionaryProposal(_Model):
    """A new dictionary worth creating; the form keeps its options inline meanwhile."""

    name: str
    items: list[str]
    fields: list[str] = []


class Report(_Model):
    mode: Literal["llm", "rules"]
    model: str | None = None
    timings_ms: Timings = Timings()
    lint: list[LintIssue] = []
    fields: list[FieldReport] = []
    document: Document = Document(pages=[])
    dictionary_proposals: list[DictionaryProposal] = []
