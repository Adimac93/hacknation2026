"""Uploaded file -> form JSON and report: ingest, heuristics or model, compile, lint."""

import time

from formcompiler import compiler, schema
from formcompiler.config import Settings
from formcompiler.ir import FieldIR, FieldType, FormIR, PageIR, SectionIR
from formcompiler.report import Report, Timings
from formcompiler.upload import FileKind


# TEMPORARY: replaced by the real pipeline (owner: Adimac93)
def process(data: bytes, kind: FileKind, settings: Settings) -> tuple[schema.Form, Report]:
    started = time.perf_counter()
    ir = FormIR(
        title="Formularz w budowie",
        pages=[
            PageIR(
                title="Wniosek",
                sections=[
                    SectionIR(
                        key="informacja",
                        title="Informacja",
                        fields=[
                            FieldIR(
                                key="w_budowie",
                                label="Przetwarzanie w budowie",
                                type=FieldType.TEXT_BLOCK,
                            )
                        ],
                    )
                ],
            ),
            PageIR(title="Podsumowanie", kind="FINISH", sections=[]),
        ],
    )
    form = compiler.build(ir)
    elapsed = round((time.perf_counter() - started) * 1000)
    return form, Report(mode="rules", timings_ms=Timings(compile=elapsed))
