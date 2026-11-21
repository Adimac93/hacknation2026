import pytest
from test_heuristics import FORM_3, document

from formcompiler import ingest, pipeline
from formcompiler.config import Settings
from formcompiler.document import Document
from formcompiler.lint import lint
from formcompiler.upload import FileKind, UploadError

SETTINGS = Settings(_env_file=None)


def read_form_3(data: bytes, kind: FileKind, settings: Settings) -> Document:
    return document(FORM_3)


def test_rules_mode_builds_a_lint_clean_form() -> None:
    form, report = pipeline.process(b"%PDF-", FileKind.PDF, SETTINGS, read=read_form_3)

    assert form.title == "Wniosek o wydanie zaświadczenia"
    assert [t.title for t in form.tabs] == [
        "Dane",
        "Szczegóły wniosku",
        "Kontakt i zgody",
        "Strona końcowa",
    ]
    assert [i for i in lint(form) if i.severity == "error"] == []
    assert report.mode == "rules"


def test_report_traces_fields_to_document_lines() -> None:
    _, report = pipeline.process(b"%PDF-", FileKind.PDF, SETTINGS, read=read_form_3)
    by_name = {f.tech_name: f for f in report.fields}

    assert "L14" in by_name["prosze_o_wydanie_zaswiadczenia_o"].src
    assert by_name["imie"].confidence == 1.0
    assert report.document.pages[0].lines[0].id == "L1"


def test_unreadable_document_is_rejected_with_422() -> None:
    def empty(data: bytes, kind: FileKind, settings: Settings) -> Document:
        return Document(pages=[])

    with pytest.raises(UploadError) as error:
        pipeline.process(b"%PDF-", FileKind.PDF, SETTINGS, read=empty)

    assert error.value.status == 422


def test_format_without_reader_is_rejected_with_422() -> None:
    with pytest.raises(UploadError) as error:
        ingest.read(b"x", FileKind.ODS, SETTINGS, readers={})

    assert error.value.status == 422
