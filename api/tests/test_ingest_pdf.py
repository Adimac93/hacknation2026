from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from formcompiler import heuristics, ingest, main, pipeline
from formcompiler.config import Settings
from formcompiler.document import Document, LineKind
from formcompiler.ingest import pdf
from formcompiler.lint import lint
from formcompiler.upload import FileKind, UploadError

DOCS = Path(__file__).resolve().parents[2] / "Docs"
PDFS = sorted(p for p in DOCS.glob("[0-9]*/*") if p.suffix.lower() == ".pdf")
SETTINGS = Settings(_env_file=None)


def form(number: str) -> Path:
    return next(p for p in PDFS if p.parent.name.startswith(f"{number}."))


def read(path: Path, settings: Settings = SETTINGS) -> Document:
    return pdf.read(path.read_bytes(), FileKind.PDF, settings)


def kinds(doc: Document, kind: LineKind) -> list[str]:
    return [line.text for page in doc.pages for line in page.lines if line.kind is kind]


def blank_pdf() -> bytes:
    """One empty A4 page, like a scan without a text layer."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
    ]
    out = bytearray(b"%PDF-1.7\n")
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def test_all_sample_forms_are_found() -> None:
    assert len(PDFS) == 8


@pytest.mark.parametrize("path", PDFS, ids=lambda p: p.parent.name[:2].strip(". "))
def test_sample_form_reads_into_numbered_lines(path: Path) -> None:
    doc = read(path)
    ids = [line.id for page in doc.pages for line in page.lines]

    assert ids == [f"L{n}" for n in range(1, len(ids) + 1)]
    assert all(page.width and page.height for page in doc.pages)
    assert heuristics.analyze(doc).title.startswith(("Wniosek", "Deklaracja"))


def test_form_3_matches_the_paper_layout() -> None:
    doc = read(form("3"))
    lines = [line.text for line in doc.pages[0].lines]

    assert kinds(doc, LineKind.HEADING) == ["WNIOSEK O WYDANIE ZAŚWIADCZENIA"]
    assert len(kinds(doc, LineKind.CHECKBOX)) == 5
    assert kinds(doc, LineKind.CHECKBOX)[2] == "okresie posiadania gospodarstwa rolnego"
    # Header columns are separate lines, in reading order.
    assert lines[4:6] == ["/ adres /", "Urząd Miasta i Gminy Młynary"]
    assert "Zaświadczenie potrzebne jest celem przedłożenia w" in lines[20]


def test_vector_squares_become_checkboxes() -> None:
    doc = read(form("8"))

    assert {"TAK", "NIE"} <= set(kinds(doc, LineKind.CHECKBOX))


def test_row_of_character_boxes_is_one_blank() -> None:
    texts = [line.text for page in read(form("5")).pages for line in page.lines]

    assert texts.count("____") == 1  # bank account comb; the footnote rule is not a blank


def test_heading_broken_over_two_lines_is_joined() -> None:
    headings = kinds(read(form("8")), LineKind.HEADING)

    assert headings[0] == (
        "DEKLARACJA O WYSOKOŚCI MIESIĘCZNEJ OPŁATY ZA GOSPODAROWANIE ODPADAMI KOMUNALNYMI"
    )


def test_simple_grid_becomes_table_rows() -> None:
    rows = [
        line
        for page in read(form("7")).pages
        for line in page.lines
        if line.kind is LineKind.TABLE_ROW
    ]

    assert ["Ulica:", "Nr domu:", "Nr lokalu:"] in [row.cells for row in rows]


def test_too_many_pages_is_413() -> None:
    with pytest.raises(UploadError) as error:
        read(form("9"), Settings(_env_file=None, max_pages=5))

    assert error.value.status == 413


def test_pdf_without_text_layer_has_no_lines() -> None:
    doc = pdf.read(blank_pdf(), FileKind.PDF, SETTINGS)

    assert [page.lines for page in doc.pages] == [[]]


def test_broken_pdf_is_422() -> None:
    with pytest.raises(UploadError) as error:
        pdf.read(b"%PDF-1.7\nnot really a pdf", FileKind.PDF, SETTINGS)

    assert error.value.status == 422


def test_pipeline_builds_lint_clean_form_3() -> None:
    form_json, report = pipeline.process(form("3").read_bytes(), FileKind.PDF, SETTINGS)

    assert form_json.title == "Wniosek o wydanie zaświadczenia"
    assert [i for i in lint(form_json) if i.severity == "error"] == []
    assert report.mode == "rules"


def test_pdf_reader_is_registered() -> None:
    assert ingest.READERS[FileKind.PDF] is pdf.read


def test_upload_of_form_3_end_to_end() -> None:
    main.app.dependency_overrides[main.get_settings] = lambda: SETTINGS
    try:
        path = form("3")
        response = TestClient(main.app).post(
            "/api/v1/forms",
            params={"details": "true"},
            files={"file": (path.name, path.read_bytes())},
        )
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    report = response.json()["report"]
    line_ids = {line["id"] for page in report["document"]["pages"] for line in page["lines"]}
    subject = {f["techName"]: f["src"] for f in report["fields"] if f["src"]}
    assert report["mode"] == "rules"
    assert subject["prosze_o_wydanie_zaswiadczenia_o"][0] == "L14"
    assert all(set(src) <= line_ids for src in subject.values())
