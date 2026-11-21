"""Uploaded file -> form JSON and report: ingest, heuristics or model, assemble, compile, lint."""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Literal

from formcompiler import compiler, dictionaries, heuristics, ingest, lint, llm, schema, sections
from formcompiler.config import Settings
from formcompiler.ingest import Reader
from formcompiler.ir import FormIR
from formcompiler.report import FieldReport, LintIssue, Report, Timings
from formcompiler.upload import FileKind, UploadError

logger = logging.getLogger(__name__)

# Model refinement of the rules-mode analysis: (settings, document text, analysis) -> analysis.
type Refine = Callable[[Settings, str, heuristics.Analysis], heuristics.Analysis]


@contextmanager
def _timed(timings: dict[str, int], stage: str) -> Iterator[None]:
    started = time.perf_counter()
    yield
    timings[stage] = round((time.perf_counter() - started) * 1000)


def process(
    data: bytes,
    kind: FileKind,
    settings: Settings,
    read: Reader = ingest.read,
    refine: Refine | None = llm.refine,
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
    mode: Literal["llm", "rules"] = "rules"
    if settings.llm_enabled and refine is not None:
        with _timed(timings, "llm"):
            try:
                analysis = refine(settings, doc.linearize(), analysis)
                mode = "llm"
            except Exception as exc:  # any model failure keeps the rules-mode result
                logger.warning("model step failed, using rules: %s", type(exc).__name__)
    ir = sections.assemble(analysis.title, analysis.addressee, analysis.applicant, analysis.pages)

    with _timed(timings, "compile"):
        form = compiler.build(ir)
    with _timed(timings, "lint"):
        form, issues = lint.fix(form)

    report = Report(
        mode=mode,
        model=settings.llm_model if mode == "llm" else None,
        timings_ms=Timings(**timings),
        lint=[LintIssue(**issue.model_dump()) for issue in issues],
        fields=_field_reports(ir),
        document=doc,
        dictionary_proposals=dictionaries.propose(form),
    )
    return form, report


def _field_reports(ir: FormIR) -> list[FieldReport]:
    return [FieldReport(tech_name=f.key, src=f.src, confidence=f.confidence) for f in ir.fields()]
