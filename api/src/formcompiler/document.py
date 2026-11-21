"""Format-independent document from ingest: pages of lines with stable ids and layout hints."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

BBox = tuple[float, float, float, float]  # x0, y0, x1, y1 in page points


class LineKind(StrEnum):
    TEXT = "TEXT"
    HEADING = "HEADING"
    CHECKBOX = "CHECKBOX"
    TABLE_ROW = "TABLE_ROW"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Line(_Model):
    id: str = Field(pattern=r"^L\d+$")
    text: str
    kind: LineKind = LineKind.TEXT
    cells: list[str] = []
    bbox: BBox | None = None

    def render(self) -> str:
        match self.kind:
            case LineKind.HEADING:
                body = f"# {self.text}"
            case LineKind.CHECKBOX:
                body = f"[ ] {self.text}"
            case LineKind.TABLE_ROW:
                body = "| " + " | ".join(self.cells) + " |"
            case LineKind.TEXT:
                body = self.text
        return f"{self.id} {body}"


class Page(_Model):
    number: int = Field(ge=1)
    width: float | None = None
    height: float | None = None
    lines: list[Line] = []


class Document(_Model):
    pages: list[Page]

    @model_validator(mode="after")
    def _line_ids_unique(self) -> Self:
        seen: set[str] = set()
        for line in (line for page in self.pages for line in page.lines):
            if line.id in seen:
                raise ValueError(f"duplicate line id: {line.id}")
            seen.add(line.id)
        return self

    def linearize(self) -> str:
        """Compact text for the model: page separators and one marked-up line per row."""
        out: list[str] = []
        for page in self.pages:
            out.append(f"--- strona {page.number} ---")
            out.extend(line.render() for line in page.lines)
        return "\n".join(out)
