import pytest
from pydantic import ValidationError

from formcompiler.document import Document, Line, LineKind, Page


def line(n: int, text: str, kind: LineKind = LineKind.TEXT, cells: list[str] | None = None) -> Line:
    return Line(id=f"L{n}", text=text, kind=kind, cells=cells or [])


def test_linearize_marks_pages_headings_checkboxes_and_tables() -> None:
    doc = Document(
        pages=[
            Page(
                number=1,
                lines=[
                    line(1, "WNIOSEK O WYDANIE ZAŚWIADCZENIA", LineKind.HEADING),
                    line(2, "Imię i nazwisko ____"),
                    line(3, "osoba fizyczna", LineKind.CHECKBOX),
                ],
            ),
            Page(
                number=2,
                lines=[line(4, "", LineKind.TABLE_ROW, cells=["Lp.", "Nazwa załącznika"])],
            ),
        ]
    )

    assert doc.linearize() == (
        "--- strona 1 ---\n"
        "L1 # WNIOSEK O WYDANIE ZAŚWIADCZENIA\n"
        "L2 Imię i nazwisko ____\n"
        "L3 [ ] osoba fizyczna\n"
        "--- strona 2 ---\n"
        "L4 | Lp. | Nazwa załącznika |"
    )


def test_line_ids_must_be_unique_across_pages() -> None:
    with pytest.raises(ValidationError, match="L1"):
        Document(pages=[Page(number=1, lines=[line(1, "a")]), Page(number=2, lines=[line(1, "b")])])
