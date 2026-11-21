import os
from pathlib import Path
from typing import Any

import httpx
import pytest

from formcompiler import heuristics, ingest
from formcompiler.config import Settings
from formcompiler.document import Document, LineKind
from formcompiler.ingest import office
from formcompiler.upload import FileKind, UploadError

FIXTURES = Path(__file__).parent / "fixtures" / "tika"
DOCS = Path(__file__).resolve().parents[2] / "Docs"
SETTINGS = Settings(_env_file=None)


def fixture(name: str) -> Document:
    return office.parse((FIXTURES / f"{name}.xhtml").read_text(encoding="utf-8"))


def texts(doc: Document, kind: LineKind | None = None) -> list[str]:
    return [
        line.text for page in doc.pages for line in page.lines if kind is None or line.kind is kind
    ]


def body(html: str) -> Document:
    return office.parse(f'<html xmlns="http://www.w3.org/1999/xhtml"><body>{html}</body></html>')


@pytest.mark.parametrize("name", ["form3-doc", "form3-docx"])
def test_word_form_3_keeps_checkboxes_and_title(name: str) -> None:
    doc = fixture(name)

    assert texts(doc, LineKind.HEADING) == ["WNIOSEK O WYDANIE ZAŚWIADCZENIA"]
    assert len(texts(doc, LineKind.CHECKBOX)) == 5
    assert texts(doc, LineKind.CHECKBOX)[2] == "okresie posiadania gospodarstwa rolnego"
    assert heuristics.analyze(doc).title == "Wniosek o wydanie zaświadczenia"


@pytest.mark.parametrize("name", ["form3-ods", "form3-xlsx"])
def test_spreadsheet_form_3_reads_cells_as_lines(name: str) -> None:
    doc = fixture(name)
    lines = texts(doc)

    # Spreadsheets keep no trace of the checkboxes, only the option texts.
    assert "okresie posiadania gospodarstwa rolnego" in lines
    assert "Urząd Miasta i Gminy Młynary" in lines  # a multi-line cell is split into lines
    assert heuristics.analyze(doc).title == "Wniosek o wydanie zaświadczenia"


def test_docx_text_frames_are_separate_lines() -> None:
    lines = texts(fixture("form3-docx"))

    assert lines[3:7] == [
        "Urząd Miasta i Gminy Młynary",
        "ul. Dworcowa 29",
        "14-420 Młynary",
        "………………………………..",
    ]


def test_form_7_tables_keep_rows_and_checkbox_glyphs() -> None:
    doc = fixture("form7-doc")
    rows = [
        line.cells for page in doc.pages for line in page.lines if line.kind is LineKind.TABLE_ROW
    ]
    lines = texts(doc)

    assert ["Ulica:", "Nr domu:", "Nr lokalu:"] in rows
    at = lines.index("Płeć:")
    assert lines[at + 1 : at + 3] == ["pies", "suka"]
    assert {"pies", "suka", "brak"} <= set(texts(doc, LineKind.CHECKBOX))


def test_line_ids_are_continuous() -> None:
    ids = [line.id for page in fixture("form7-doc").pages for line in page.lines]

    assert ids == [f"L{n}" for n in range(1, len(ids) + 1)]


def test_markup_rules() -> None:
    doc = body(
        "<h2>Dane wnioskodawcy</h2>"
        "<p>\n    <b>OŚWIADCZENIE</b>\n</p>"
        "<p><b>Proszę o:</b></p>"
        "<ul><li>&middot; tak</li></ul>"
        f"<p>&middot; {'długi akapit listy punktowanej ' * 5}</p>"
        "<p>pierwsza<br/>druga</p>"
        "<h1>I. \n    <b>Wniosek o nagrodę</b>\n</h1>"
        "<table><tbody>"
        "<tr><td><p>Imię</p></td><td/></tr>"
        "<tr><td>Kwota</td><td>100 zł</td><td/></tr>"
        "<tr><td/><td/></tr>"
        "</tbody></table>"
    )
    lines = [(line.kind, line.text, line.cells) for line in doc.pages[0].lines]

    assert lines[:6] == [
        (LineKind.HEADING, "Dane wnioskodawcy", []),
        (LineKind.HEADING, "OŚWIADCZENIE", []),
        (LineKind.TEXT, "Proszę o:", []),
        (LineKind.CHECKBOX, "tak", []),
        (LineKind.TEXT, lines[4][1], []),
        (LineKind.TEXT, "pierwsza", []),
    ]
    assert lines[6:] == [
        (LineKind.TEXT, "druga", []),
        (LineKind.HEADING, "I. Wniosek o nagrodę", []),
        (LineKind.TEXT, "Imię", []),
        (LineKind.TABLE_ROW, "Kwota 100 zł", ["Kwota", "100 zł"]),
    ]


def test_office_readers_are_registered() -> None:
    for kind in (FileKind.DOC, FileKind.DOCX, FileKind.XLSX, FileKind.ODS):
        assert ingest.READERS[kind] is office.read


def test_tika_request_names_the_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def put(url: str, **kwargs: Any) -> httpx.Response:
        seen.update(url=url, **kwargs)
        return httpx.Response(
            200, text="<html><body><p>WNIOSEK</p></body></html>", request=httpx.Request("PUT", url)
        )

    monkeypatch.setattr(httpx, "put", put)
    doc = office.read(
        b"PK\x03\x04", FileKind.DOCX, Settings(_env_file=None, tika_url="http://tika:9998/")
    )

    assert seen["url"] == "http://tika:9998/tika"
    assert seen["headers"]["Content-Type"] == office.CONTENT_TYPES[FileKind.DOCX]
    assert seen["headers"]["Accept"] == "text/html"
    assert seen["content"] == b"PK\x03\x04"
    assert texts(doc) == ["WNIOSEK"]


def test_unreachable_tika_is_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def put(url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "put", put)
    with pytest.raises(UploadError) as error:
        office.read(b"x", FileKind.DOC, SETTINGS)

    assert error.value.status == 503


def test_file_tika_cannot_parse_is_422(monkeypatch: pytest.MonkeyPatch) -> None:
    def put(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(422, request=httpx.Request("PUT", url))

    monkeypatch.setattr(httpx, "put", put)
    with pytest.raises(UploadError) as error:
        office.read(b"x", FileKind.XLSX, SETTINGS)

    assert error.value.status == 422


def _tika_url() -> str | None:
    url = os.environ.get("TIKA_URL", SETTINGS.tika_url).rstrip("/")
    try:
        httpx.get(f"{url}/tika", timeout=1.0).raise_for_status()
    except httpx.HTTPError:
        return None
    return url


TIKA_URL = _tika_url()


@pytest.mark.skipif(TIKA_URL is None, reason="Tika is not reachable at TIKA_URL")
def test_live_tika_reads_form_3_docx() -> None:
    assert TIKA_URL is not None
    data = next(DOCS.glob("3. */*.docx")).read_bytes()

    doc = office.read(data, FileKind.DOCX, Settings(_env_file=None, tika_url=TIKA_URL))

    assert len(texts(doc, LineKind.CHECKBOX)) == 5
