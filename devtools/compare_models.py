"""Compare candidate models on step A (inventory) for reference forms 1 and 5 (decision D20).

Development tool only, never part of the image. Needs LLM_* in the repo .env (EdenAI key).
Run from api/: uv run python ../devtools/compare_models.py [--out DIR] [--models M ...]
Forms without a gold standard (round 2): --unlabeled 3 4 6 runs the production path
(heuristics, refine, assemble, build, lint.fix) and stores the fields for manual review.
--pipeline 3 4 6 7 runs the whole pipeline.process with the PDF text from load_document.

Gold standard: subject pages of the decompiled reference JSON, plus addressee and applicant
flags read by hand from the references. Each call is written to --out as soon as it returns:
raw HTTP bodies under raw/, one JSON line per call in results.jsonl.
"""

import argparse
import difflib
import json
import tempfile
import time
from pathlib import Path
from typing import Any, NamedTuple

import httpx
import pdfplumber

from formcompiler import compiler, heuristics, lint, pipeline
from formcompiler.compiler import slugify
from formcompiler.config import Settings
from formcompiler.decompile import decompile
from formcompiler.document import Document, Line, Page
from formcompiler.ir import Addressee, Applicant, FieldIR
from formcompiler.llm import (
    EXAMPLES,
    INVENTORY_MAX_TOKENS,
    InventoryIR,
    LLMError,
    inventory_messages,
    refine,
    request_json,
)
from formcompiler.schema import Form
from formcompiler.sections import LIBRARY, RESERVED_KEYS, assemble
from formcompiler.upload import FileKind

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "Docs"
MATCH_THRESHOLD = 0.6
BUDGET_USD = 2.0
# USD per million tokens (input, output), research/05 section 2a.
MODELS = {
    "mistral/ministral-8b-2512@eu": (0.165, 0.165),
    "flexai/Qwen3.5-9B@eu": (0.10, 0.15),
}
ALL = Applicant(persons=True, entities=True, proxy=True)


class Gold(NamedTuple):
    name: str
    pdf: str
    reference: str
    addressee: Addressee
    applicant: Applicant


GOLD = [
    Gold(
        "1",
        "1. */*.pdf",
        "1. */konfiguracja_*.json",
        Addressee(name="Wójt Gminy Elbląg", kind="ORGAN"),
        ALL,
    ),
    Gold(
        "5",
        "5. */*.PDF",
        "5. */konfiguracja_*.json",
        Addressee(name="Urząd Gminy Ulan-Majorat", kind="URZAD"),
        ALL,
    ),
]


class Recorder(httpx.BaseTransport):
    """Passes requests through and saves every raw response body right away."""

    def __init__(self, directory: Path, stem: str) -> None:
        self.inner = httpx.HTTPTransport()
        self.directory = directory
        self.stem = stem
        self.count = 0
        self.usage: dict[str, int] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)
        content = response.read()
        self.count += 1
        path = self.directory / f"{self.stem}-attempt{self.count}.json"
        path.write_bytes(content)
        try:
            self.usage = json.loads(content).get("usage") or {}
        except ValueError:
            self.usage = {}
        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
        }
        return httpx.Response(response.status_code, headers=headers, content=content)

    def close(self) -> None:
        self.inner.close()


def document_text(pdf_path: Path) -> str:
    return load_document(pdf_path).linearize()


def load_document(pdf_path: Path) -> Document:
    pages = []
    n = 0
    with pdfplumber.open(pdf_path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            lines = []
            for text in (page.extract_text() or "").splitlines():
                if text.strip():
                    n += 1
                    lines.append(Line(id=f"L{n}", text=text.strip()))
            pages.append(Page(number=number, lines=lines))
    return Document(pages=pages)


def gold_fields(reference: Path) -> list[FieldIR]:
    ir = decompile(Form.model_validate(json.loads(reference.read_text(encoding="utf-8"))))
    return [f for page in ir.pages[1:-2] for s in page.sections for f in s.fields]


def norm(text: str) -> str:
    return slugify(text).replace("_", " ")


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


LIBRARY_LABELS = [
    f.label
    for s in [*LIBRARY.addressee.values(), *LIBRARY.applicant, *LIBRARY.contact.sections]
    for f in s.fields
]


def score(inv: InventoryIR, gold: Gold, expected: list[FieldIR]) -> dict[str, Any]:
    """Greedy one-to-one label matching, then type, extra-field and flag checks."""
    pairs = sorted(
        (
            (similarity(g.label, p.label), gi, pi)
            for gi, g in enumerate(expected)
            for pi, p in enumerate(inv.fields)
        ),
        reverse=True,
    )
    matched: dict[int, int] = {}
    used: set[int] = set()
    for ratio, gi, pi in pairs:
        if ratio >= MATCH_THRESHOLD and gi not in matched and pi not in used:
            matched[gi] = pi
            used.add(pi)
    extra = [p for pi, p in enumerate(inv.fields) if pi not in used]
    duplicates_library = [
        p
        for p in extra
        if slugify(p.key) in RESERVED_KEYS
        or any(similarity(p.label, label) >= 0.8 for label in LIBRARY_LABELS)
    ]
    same_type = sum(expected[gi].type == inv.fields[pi].type for gi, pi in matched.items())
    flags = [
        inv.applicant.persons == gold.applicant.persons,
        inv.applicant.entities == gold.applicant.entities,
        inv.applicant.proxy == gold.applicant.proxy,
    ]
    addressee_ok = (
        inv.addressee is not None
        and inv.addressee.kind == gold.addressee.kind
        and similarity(inv.addressee.name, gold.addressee.name) >= 0.8
    )
    return {
        "gold_fields": len(expected),
        "predicted_fields": len(inv.fields),
        "matched": len(matched),
        "coverage": len(matched) / len(expected),
        "type_agreement": same_type / len(matched) if matched else 0.0,
        "extra": len(extra),
        "extra_library": len(duplicates_library),
        "applicant_ok": sum(flags),
        "addressee_ok": addressee_ok,
        "title": inv.title,
        "matches": [
            [expected[gi].label, inv.fields[pi].label, expected[gi].type, inv.fields[pi].type]
            for gi, pi in sorted(matched.items())
        ],
        "extra_labels": [f"{p.label} ({p.type})" for p in extra],
    }


def run_one(settings: Settings, model: str, gold: Gold, variant: str, out: Path) -> dict[str, Any]:
    text = document_text(next(DOCS.glob(gold.pdf)))
    expected = gold_fields(next(DOCS.glob(gold.reference)))
    # "loo" leaves the evaluated form out of the few-shot examples, so the model cannot copy
    # the answer; "full" is the production prompt with both references.
    examples = tuple(e for e in EXAMPLES if variant == "full" or e.name != f"ref{gold.name}")
    system, user = inventory_messages(text, examples)
    stem = f"{slugify(model)}-form{gold.name}-{variant}"
    recorder = Recorder(out / "raw", stem)
    config = settings.model_copy(update={"llm_model": model, "llm_timeout_s": 120.0})
    row: dict[str, Any] = {"model": model, "form": gold.name, "variant": variant}
    started = time.perf_counter()
    try:
        result = request_json(
            config, system, user, InventoryIR, INVENTORY_MAX_TOKENS, transport=recorder
        )
    except LLMError as exc:
        elapsed = time.perf_counter() - started
        return row | {"error": str(exc), "elapsed_s": elapsed, "attempts": recorder.count}
    finally:
        recorder.close()
    price_in, price_out = MODELS[model]
    usage = result.usage
    cost = (usage.prompt_tokens * price_in + usage.completion_tokens * price_out) / 1e6
    row |= {
        "elapsed_s": result.elapsed_s,
        "attempts": result.attempts,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "cost_usd": cost,
        **score(result.parsed, gold, expected),
        "answer": result.parsed.model_dump(mode="json"),
    }
    return row


def run_unlabeled(settings: Settings, model: str, form: str, out: Path) -> dict[str, Any]:
    """Production path on a form without a gold standard; fields are kept for manual review."""
    doc = load_document(next(DOCS.glob(f"{form}. */*.[pP][dD][fF]")))
    recorder = Recorder(out / "raw", f"{slugify(model)}-form{form}")
    config = settings.model_copy(update={"llm_model": model, "llm_timeout_s": 120.0})
    row: dict[str, Any] = {"model": model, "form": form, "variant": "unlabeled"}
    started = time.perf_counter()
    try:
        refined = refine(config, doc.linearize(), heuristics.analyze(doc), transport=recorder)
    except LLMError as exc:
        elapsed = time.perf_counter() - started
        return row | {"error": str(exc), "elapsed_s": elapsed, "attempts": recorder.count}
    finally:
        recorder.close()
    elapsed = time.perf_counter() - started
    ir = assemble(refined.title, refined.addressee, refined.applicant, refined.pages)
    built, issues = lint.fix(compiler.build(ir))
    prompt = int(recorder.usage.get("prompt_tokens", 0))
    completion = int(recorder.usage.get("completion_tokens", 0))
    price_in, price_out = MODELS[model]
    return row | {
        "elapsed_s": elapsed,
        "attempts": recorder.count,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cost_usd": (prompt * price_in + completion * price_out) / 1e6,
        "title": refined.title,
        "addressee": refined.addressee.model_dump() if refined.addressee else None,
        "applicant": refined.applicant.model_dump(),
        "lint_errors": [i.code for i in issues if i.severity == "error" and not i.fixed],
        "lint_warnings": [i.code for i in issues if i.severity == "warning" and not i.fixed],
        "lint_fixed": [i.code for i in issues if i.fixed],
        "tabs": len(built.tabs),
        "fields": [
            {
                "page": page.title,
                "section": section.title,
                "key": f.key,
                "label": f.label,
                "type": f.type,
                "required": f.required,
                "options": f.options,
                "show_if": f.show_if.model_dump() if f.show_if else None,
            }
            for page in refined.pages
            for section in page.sections
            for f in section.fields
        ],
    }


def run_pipeline(settings: Settings, model: str, form: str, out: Path) -> dict[str, Any]:
    """Full pipeline.process on the PDF text; refine is wrapped to record usage and its result."""
    doc = load_document(next(DOCS.glob(f"{form}. */*.[pP][dD][fF]")))
    recorder = Recorder(out / "raw", f"{slugify(model)}-pipeline-form{form}")
    config = settings.model_copy(
        update={"llm_model": model, "llm_timeout_s": 120.0, "llm_enabled": True}
    )
    seen: list[heuristics.Analysis] = []

    def recorded(s: Settings, text: str, analysis: heuristics.Analysis) -> heuristics.Analysis:
        result = refine(s, text, analysis, transport=recorder)
        seen.append(result)
        return result

    started = time.perf_counter()
    try:
        built, report = pipeline.process(
            b"", FileKind.PDF, config, read=lambda *_: doc, refine=recorded
        )
    finally:
        recorder.close()
    elapsed = time.perf_counter() - started
    prompt = int(recorder.usage.get("prompt_tokens", 0))
    completion = int(recorder.usage.get("completion_tokens", 0))
    price_in, price_out = MODELS[model]
    subject_tabs = built.tabs[1:-2]
    row: dict[str, Any] = {
        "model": model,
        "form": form,
        "variant": "pipeline",
        "mode": report.mode,
        "elapsed_s": elapsed,
        "llm_ms": report.timings_ms.llm,
        "attempts": recorder.count,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cost_usd": (prompt * price_in + completion * price_out) / 1e6,
        "title": built.title,
        "lint_errors": [i.code for i in report.lint if i.severity == "error" and not i.fixed],
        "lint_warnings": [i.code for i in report.lint if i.severity == "warning" and not i.fixed],
        "subject_pages": [t.title for t in subject_tabs],
        "fields": [
            {
                "page": tab.title,
                "section": q.field.title,
                "key": item.field.techName,
                "label": item.field.title,
                "type": item.field.type,
                "options": [o.name for o in item.field.options],
                "dictionary": item.field.dictionaryName,
                "conditional": bool(item.field.states),
            }
            for tab in subject_tabs
            for q in tab.questions
            for item in q.field.repeatingSectionGrid
        ],
    }
    if seen:
        result = seen[-1]
        row["addressee"] = result.addressee.model_dump() if result.addressee else None
        row["applicant"] = result.applicant.model_dump()
    return row


def table(rows: list[dict[str, Any]]) -> str:
    head = (
        "| Model | Formularz | Wariant | Pokrycie | Zgodność typów | Nadmiarowe (z biblioteki) "
        "| `applicant` | Adresat | Czas [s] | Tokeny wej./wyj. | Koszt [USD] |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [head]
    for r in rows:
        if "error" in r:
            lines.append(
                f"| `{r['model']}` | {r['form']} | {r['variant']} | błąd: {r['error']} "
                f"| | | | | {r['elapsed_s']:.0f} | | |"
            )
            continue
        lines.append(
            f"| `{r['model']}` | {r['form']} | {r['variant']} "
            f"| {r['matched']}/{r['gold_fields']} | {r['type_agreement']:.0%} "
            f"| {r['extra']} ({r['extra_library']}) | {r['applicant_ok']}/3 "
            f"| {'tak' if r['addressee_ok'] else 'nie'} | {r['elapsed_s']:.1f} "
            f"| {r['prompt_tokens']}/{r['completion_tokens']} | {r['cost_usd']:.5f} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default_out = Path(tempfile.gettempdir()) / "formcompiler-compare"
    parser.add_argument("--out", type=Path, default=default_out)
    parser.add_argument("--variants", nargs="+", default=["loo", "full"])
    parser.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    parser.add_argument("--unlabeled", nargs="+", default=[], metavar="FORM")
    parser.add_argument("--pipeline", nargs="+", default=[], metavar="FORM")
    args = parser.parse_args()
    out: Path = args.out
    (out / "raw").mkdir(parents=True, exist_ok=True)
    settings = Settings()
    rows: list[dict[str, Any]] = []
    spent = 0.0
    with (out / "results.jsonl").open("a", encoding="utf-8") as log:
        for form in args.pipeline:
            for model in args.models:
                row = run_pipeline(settings, model, form, out)
                spent += row["cost_usd"]
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                log.flush()
                print(
                    f"{model} form {form}: mode={row['mode']} fields={len(row['fields'])} "
                    f"lint={row['lint_errors']} {row['elapsed_s']:.1f}s",
                    flush=True,
                )
        if args.pipeline:
            print(f"\nkoszt łączny: {spent:.5f} USD; wyniki: {out}")
            return
        for form in args.unlabeled:
            for model in args.models:
                row = run_unlabeled(settings, model, form, out)
                spent += row.get("cost_usd", 0.0)
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                log.flush()
                status = (
                    row.get("error") or f"{len(row['fields'])} fields, lint {row['lint_errors']}"
                )
                print(f"{model} form {form}: {status}", flush=True)
        if args.unlabeled:
            print(f"\nkoszt łączny: {spent:.5f} USD; wyniki: {out}")
            return
        for variant in args.variants:
            for gold in GOLD:
                for model in args.models:
                    if spent >= BUDGET_USD:
                        raise SystemExit(f"budget {BUDGET_USD} USD reached")
                    row = run_one(settings, model, gold, variant, out)
                    spent += row.get("cost_usd", 0.0)
                    log.write(json.dumps(row, ensure_ascii=False) + "\n")
                    log.flush()
                    rows.append(row)
                    status = row.get("error") or f"{row['matched']}/{row['gold_fields']}"
                    print(f"{model} form {gold.name} {variant}: {status}", flush=True)
    print(table(rows))
    print(f"\nkoszt łączny: {spent:.5f} USD; wyniki: {out}")
    (out / "table.md").write_text(table(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
