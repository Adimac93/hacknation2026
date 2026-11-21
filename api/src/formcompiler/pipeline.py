"""Uploaded file -> form JSON and report: ingest, heuristics or model, assemble, compile, lint."""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from formcompiler import compiler, heuristics, ingest, lint, schema, sections
from formcompiler.config import Settings
from formcompiler.ingest import Reader
from formcompiler.ir import FormIR
from formcompiler.report import FieldReport, LintIssue, Report, Timings
from formcompiler.upload import FileKind, UploadError


@contextmanager
def _timed(timings: dict[str, int], stage: str) -> Iterator[None]:
    started = time.perf_counter()
    yield
    timings[stage] = round((time.perf_counter() - started) * 1000)


def process(
    data: bytes, kind: FileKind, settings: Settings, read: Reader = ingest.read
) -> tuple[schema.Form, Report]:
    timings: dict[str, int] = {}
    with _timed(timings, "ingest"):
        doc = read(data, kind, settings)
    if not any(page.lines for page in doc.pages):
        raise UploadError(
            422, "Dokument nieczytelny", "Nie udało się odczytać tekstu z przesłanego pliku."
        )

    with _timed(timings, "heuristics"):
        analysis = heuristics.analyze(doc)
    # The model steps (llm.py) plug in here; any model failure keeps this rules-mode result.
    ir = sections.assemble(analysis.title, analysis.addressee, analysis.applicant, analysis.pages)

    with _timed(timings, "compile"):
        form = compiler.build(ir)
    with _timed(timings, "lint"):
        form, issues = lint.fix(form)

    report = Report(
        mode="rules",
        timings_ms=Timings(**timings),
        lint=[LintIssue(**issue.model_dump()) for issue in issues],
        fields=_field_reports(ir),
        document=doc,
    )
    return form, report


def _field_reports(ir: FormIR) -> list[FieldReport]:
    return [FieldReport(tech_name=f.key, src=f.src, confidence=f.confidence) for f in ir.fields()]
